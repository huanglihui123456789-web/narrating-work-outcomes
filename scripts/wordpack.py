#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""词表加载器：report_audit 与 promise_reconcile 共用的词汇来源.

设计约束（都是踩出来的）：
  * wordlists.json 是**唯一**词表来源，本模块不内置任何中文词条。
    找不到或解析失败就直接报错退出——绝不静默回退到"代码里的另一份词表"，
    那种两份定义对不上的情况早晚会出现。
  * 路径按本文件位置解析，不按当前工作目录：脚本可能从任意目录被调用。
  * 只外置词条，不外置阈值。STACK_MIN 之外的评分权重与 FLOOR/LEAD 由
    scripts/eval_checks.py 与 eval_thresholds.py 标定，改它们必须重跑评测。
  * profiles 只写差异（add / remove / add_units / add_cn_units），
    避免每个单位抄一份全量词表、从此再也合不动上游更新。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "wordlists.json"

# 词表键 → 是否参与派生正则
LIST_KEYS = (
    "ACTION_VERBS", "RESULT_SIGNALS", "VAGUE_QUANTIFIERS", "COLLOQUIAL_ACTIONS",
    "UNVERIFIED_MARKERS", "RISK_SIGNALS", "FOLLOWUP_SIGNALS", "PLAN_SECTION_WORDS",
    "DEADLINE_SIGNALS", "OWNER_SIGNALS", "VAGUE_PRAISE", "NEGATIVE_METRICS",
    "CLICHE", "ACTIVITY_VERBS", "CALIBER_WORDS", "BASELINE_WORDS",
    "PLAN_WORDS", "DEFER_WORDS", "DEFER_VERBS", "FUTURE_MARKERS",
    "NUM_UNITS", "CN_NUM_UNITS", "ENTITY_SUFFIXES", "ENTITY_STOP_PREFIX",
    "ENTITY_NOISE_PREFIX", "DOC_TITLE_WORDS", "META_COMMENT_WORDS",
    "META_COMMENT_VERBS", "META_COMMENT_TAILS", "PERIOD_WORDS",
    "RATING_STRONG", "RATING_MEET", "RATING_MISS", "EVID_STRONG", "EVID_MISS",
)

# DOC_TYPE_FAMILIES 是嵌套列表（同族算一件事），单独取出、不参与 LIST_KEYS 的扁平处理
STRUCTURED_KEYS = ("DOC_TYPE_FAMILIES",)


class WordPackError(RuntimeError):
    pass


def _die(msg: str) -> None:
    raise WordPackError(msg)


def _alt(words) -> str:
    """转义并按长度倒序拼接：长词必须排前面，否则"人次"会被"人"先吃掉。"""
    return "|".join(re.escape(str(w)) for w in sorted(set(words), key=len, reverse=True))


def load(profile: str = "", path: str = "") -> dict:
    p = Path(path) if path else DEFAULT_PATH
    if not p.exists():
        _die(f"找不到词表文件 {p}\n词表是本工具的唯一事实源，不做内置回退。请恢复 wordlists.json 或先用 --words 指定路径。")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _die(f"词表 {p} 解析失败：{e}")
    if not isinstance(data, dict) or "base" not in data:
        _die(f"词表 {p} 缺少 base 段")

    w = {k: list(data["base"].get(k, [])) for k in LIST_KEYS}
    for k in STRUCTURED_KEYS:
        w[k] = [list(f) for f in data["base"].get(k, [])]
    if profile:
        profiles = data.get("profiles", {})
        if profile not in profiles:
            _die(f"没有名为 {profile!r} 的词表档，可选：{'、'.join(sorted(profiles)) or '（无）'}")
        _merge(w, profiles[profile])
    return w


def _merge(w: dict, diff: dict) -> None:
    for k, add in (diff.get("add") or {}).items():
        if k not in w:
            _die(f"词表档引用了未知词组 {k!r}（可用：{'、'.join(LIST_KEYS)}）")
        w[k] = w[k] + [x for x in add if x not in w[k]]
    for k, rem in (diff.get("remove") or {}).items():
        if k not in w:
            _die(f"词表档引用了未知词组 {k!r}")
        w[k] = [x for x in w[k] if x not in rem]
    # 量词单列出来，避免"往中文量词里加 步"重新引入"进一步"误咬
    w["NUM_UNITS"] = w["NUM_UNITS"] + [x for x in (diff.get("add_units") or []) if x not in w["NUM_UNITS"]]
    w["CN_NUM_UNITS"] = w["CN_NUM_UNITS"] + [x for x in (diff.get("add_cn_units") or []) if x not in w["CN_NUM_UNITS"]]


# 词表契约：注入 globals 之后，缺键/空表必须当场炸，不能静默退化。
# 这两类事故都真发生过：键改名后词表变空（检查项静默失效）、派生名漏注入（NameError）。
REQUIRED_NONEMPTY = (
    "ACTION_VERBS", "RESULT_SIGNALS", "VAGUE_QUANTIFIERS", "VAGUE_PRAISE",
    "UNVERIFIED_MARKERS", "RISK_SIGNALS", "FOLLOWUP_SIGNALS", "PLAN_SECTION_WORDS",
    "DEADLINE_SIGNALS", "OWNER_SIGNALS", "NEGATIVE_METRICS", "CLICHE",
    "ACTIVITY_VERBS", "CALIBER_WORDS", "BASELINE_WORDS", "PLAN_WORDS",
    "DEFER_WORDS", "DEFER_VERBS", "FUTURE_MARKERS", "NUM_UNITS", "CN_NUM_UNITS",
    "ENTITY_SUFFIXES", "DOC_TYPE_FAMILIES", "DOC_TITLE_WORDS", "META_COMMENT_WORDS",
    "RATING_STRONG", "RATING_MEET", "RATING_MISS", "EVID_STRONG", "EVID_MISS",
    "META_COMMENT_VERBS", "META_COMMENT_TAILS", "PERIOD_WORDS",
)
OPTIONAL_KEYS = ("COLLOQUIAL_ACTIONS", "ENTITY_STOP_PREFIX", "ENTITY_NOISE_PREFIX")
DERIVED_NAMES = ("NUM_RE", "CN_NUM_RE", "DEFER_RE", "FUTURE_RE",
                 "PLAN_HEADING_RE", "RISK_NEG_RE", "META_COMPLAINT_RE",
                 "RATING_STRONG_RE", "RATING_MEET_RE", "RATING_MISS_RE",
                 "EVID_STRONG_RE", "EVID_MISS_RE")

# 中文数字量词里的已知陷阱：中文没有词边界，含"步/半"会把"进一步提高""下一步"
# "半天"误咬成数量。阿拉伯数字侧不受此限。
CN_BANNED_UNITS = ("步", "半")


def validate(w: dict) -> None:
    empty = [k for k in REQUIRED_NONEMPTY if not w.get(k)]
    if empty:
        _die(f"词表缺少必需的词条组：{'、'.join(empty)}。"
             f"缺失会让对应检查静默失效，请检查 wordlists.json 是否被改坏或键名拼错。")
    absent = [k for k in OPTIONAL_KEYS if k not in w]
    if absent:
        _die(f"词表缺少可选组（可以为空，但键必须存在）：{'、'.join(absent)}")
    bad = [u for u in w.get("CN_NUM_UNITS") or [] if u in CN_BANNED_UNITS]
    if bad:
        _die(f"CN_NUM_UNITS 不能含 {'、'.join(bad)}："
             f"中文无词边界，「进一步」「下一步」会被误判成数量。")
    for fam in w.get("DOC_TYPE_FAMILIES") or []:
        if not isinstance(fam, list) or not fam:
            _die("DOC_TYPE_FAMILIES 每一项必须是非空列表（同族算同一件事）")


def compile_derived(w: dict) -> dict:
    """由词条派生出需要编译的正则。结构留在调用方，这里只产出数据。"""
    validate(w)
    out = dict(w)
    out["NUM_RE"] = re.compile(rf"\d+(?:\.\d+)?\s*(?:{_alt(w['NUM_UNITS'])})")
    out["CN_NUM_RE"] = re.compile(rf"(?:[一二两三四五六七八九十]+)\s*(?:{_alt(w['CN_NUM_UNITS'])})")
    out["DEFER_RE"] = re.compile(
        rf"[未没]\s*(?:能|被|及)?\s*(?:{_alt(w['DEFER_VERBS'])})|{_alt(w['DEFER_WORDS'])}")
    out["FUTURE_RE"] = re.compile(_alt(w["FUTURE_MARKERS"]))
    # 计划区标签由 PLAN_WORDS 驱动：单位想加"下学期展望"这类说法，只改词表就生效
    out["META_COMPLAINT_RE"] = re.compile(_alt(w["META_COMMENT_VERBS"]) + _alt(w["META_COMMENT_TAILS"]))
    out["PLAN_HEADING_RE"] = re.compile(rf"^.*?(?:{_alt(w['PLAN_WORDS'])})\s*[:：]?\s*$")
    for key in ("RATING_STRONG", "RATING_MEET", "RATING_MISS", "EVID_STRONG", "EVID_MISS"):
        out[f"{key}_RE"] = re.compile(_alt(w[key]))
    out["RISK_NEG_RE"] = re.compile(
        r"[零无未没]\s*(?:发生|出现|发现|存在)?\s*(?:重大|安全|责任|重复)?\s*"
        r"(?:事故|投诉|差错|故障|返工|流失|隐患|延误|问题|延期|复现)"
        r"|杜绝[^，。；\s]{0,4}|防患于未燃"
        # 「问题」进了风险词表，就必须排除"解决/整改问题"这类成果说法，
        # 否则"解决问题 12 个"会被当成没闭环的风险
        r"|(?:解决|整改|修复|处理|消除|克服)(?:了|完|毕)?[^，。；\s]{0,5}问题")
    return out


def entity_tags(text: str, suffixes, stops, noise_prefixes=()) -> set:
    """抽出「机械学院」「B 楼」这类具名对象。

    三处坑：
      * 中英混排常带空格（"B 楼"），不先去空白就匹配不到。
      * 剔噪必须按**整词**从头部剥，不能按字符。按字符会把专名啃掉：
        "实验楼" 剔成 "验楼"，两个不同写法反而对不上。
      * 剥完为空或只剩数字的不是具名对象（"给 17 个学院""两个学院"），
        否则会把数量差异当成对象差异。
    """
    if not suffixes:
        return set()
    compact = re.sub(r"\s+", "", text)
    pat = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9]{1,4})(" + _alt(suffixes) + r")")
    noise = sorted({p for p in noise_prefixes if p}, key=len, reverse=True)
    out = set()
    for m in pat.finditer(compact):
        prefix = m.group(1)
        changed = True
        while changed and len(prefix) > 1:
            changed = False
            for w in noise:
                if prefix.startswith(w) and len(prefix) > len(w):
                    prefix = prefix[len(w):]
                    changed = True
        if not prefix or prefix.isdigit() or prefix in stops:
            continue
        if any(prefix.endswith(s) for s in stops):
            continue
        out.add(prefix + m.group(2))
    return out


def doc_families(text: str, families) -> set:
    """文档类型归族。同族（系统/平台、办法/制度/细则）视为同一件事。"""
    out = set()
    for i, fam in enumerate(families):
        if any(word in text for word in fam):
            out.add(i)
    return out


def conflict_reason(a: str, b: str, w: dict):
    """两段说的是不是同一件事？给出人话理由，判不出就返回 None。

    先判文档类型，再判对象：前者更稳（手册≠通知），后者容易被数量词带偏。
    """
    suffixes = w.get("ENTITY_SUFFIXES") or []
    stops = w.get("ENTITY_STOP_PREFIX") or []
    noise = w.get("ENTITY_NOISE_PREFIX") or []
    fams = w.get("DOC_TYPE_FAMILIES") or []
    ca, cb = re.sub(r"\s+", "", a), re.sub(r"\s+", "", b)

    fa, fb = doc_families(ca, fams), doc_families(cb, fams)
    if fa and fb and not (fa & fb):
        wa = "、".join(sorted({x for i in fa for x in fams[i] if x in ca}))
        wb = "、".join(sorted({x for i in fb for x in fams[i] if x in cb}))
        return f"文档类型不同：{wa} ≠ {wb}"

    ea = entity_tags(ca, suffixes, stops, noise)
    eb = entity_tags(cb, suffixes, stops, noise)
    if ea and eb and not (ea & eb):
        return f"对象不同：{'、'.join(sorted(ea))} ≠ {'、'.join(sorted(eb))}"
    return None


def apply(target_globals: dict, profile: str = "", path: str = "") -> str:
    """把词表注入模块 globals()，返回实际生效的词表档名。"""
    try:
        w = load(profile, path)
        derived = compile_derived(w)
        missing = [n for n in DERIVED_NAMES if n not in derived]
        if missing:
            _die(f"派生正则未全部产出：{'、'.join(missing)}。"
                 f"若新增了 DERIVED_NAMES，请同时在 compile_derived 里构造它。")
        derived["WORDS"] = w
        target_globals.update(derived)
    except WordPackError as e:
        print(f"词表错误：{e}", file=sys.stderr)
        sys.exit(2)
    return profile or "base"
