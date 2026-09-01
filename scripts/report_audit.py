#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""职场成果叙事引擎 —— 稿件体检器.

两种模式：
  gaps  : 扫素材/初稿，找出"可量化却没量化"的空位、只有动作没有结果的流水账、
          报了问题却没下文的漏报。产出一份可直接抛给用户的《待补清单》。
  final : 扫成稿，给出可诊断的评分与逐条修改点（流水账率 / 量化密度 / 口径完整度 /
          套话密度 / 篇幅）。

用法:
  python scripts/report_audit.py <file> --mode gaps
  python scripts/report_audit.py <file> --mode final --word-limit 800

只依赖标准库。输出 UTF-8。
退出码: 0 = 正常, 2 = 读文件失败。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata

import wordpack

# 词表唯一来源是上级目录的 wordlists.json，本文件不再内置中文词条。
# 之所以不留内置回退：两份词表迟早对不上，而那时检查结论会静默变错。
wordpack.apply(globals())










PLAN_PREFIX_RE = re.compile(r"^\s*(?:[一二三四五六七八九十下本月季]|后续|下一步|近期)?\s*"
                            r"(?:周|月|季|年)?\s*(?:计划|安排|规划|待办|打算)\s*[:：]\s*")


# 目标声明行：讲的是"打算做什么"，不能拿成果标准去要产出
TARGET_PREFIX_RE = re.compile(r"^\s*(考核)?目标(?:值|指标)?\s*[:：]")

# 负向指标的时间窗：引导词 + 区间，或句内直接给出时长（"无差错运行 90 天"本身就是区间）
WINDOW_RE = re.compile(
    r"(连续|自|截至|本月|本周|本季|全年|过去|近|今年以来|此后|以来)[^，。；]{0,8}(\d+\s*)?"
    r"(天|日|周|月|年|次|季)"
    r"|(\d+|一|两|三|四|五|六|七|八|九|十)\s*(天|日|周|个月|月|年|季度)(?:内|以内|里|间)?")


PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％)")

# 伪精确：看着像数字，其实是估的。汇报里必须给准确数，或标明"估算 + 算法"。
PSEUDO_PRECISION_RE = re.compile(
    r"(?<![已预约])(?:约|大约|约莫|将近)\s*\d[\d.]*(?!\s*[/月])|"   # 约 120 人（排除"已约 8/30"）
    r"\d[\d.]*\s*(?:余|多)(?![数目数])|"      # 300 余人
    r"\d[\d.]*\s*(?:左右|以上|以下)|"         # 2 天左右
    r"十来|好几|数十|上百")                   # 十来个人

# 只说比例不说基数，等于没说
RATIO_NO_BASE_RE = re.compile(r"减半|翻倍|翻番|腰斩|番一倍|[一二两三四五六七八九十]+\s*成(?!交)")
SAVE_RE = re.compile(r"(?:节省|省了|省下|节约|压缩|降低|减少)\D{0,8}?\d")
MONEY_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:万元|亿元|元)")

# Markdown 待办符号：成稿里残留说明这件事根本没做完
TODO_PENDING_RE = re.compile(r"^\s*[-*]?\s*\[[ ]\]")
TODO_DONE_RE = re.compile(r"^\s*[-*]?\s*\[[xX]\]")
RESULT_SECTION_WORDS = ["结果", "成绩", "交付", "产出", "完成", "亮点", "业绩"]

# STAR-L 的 L：判断规则/教训类句子本就不该带数字。述职与竞聘文体下豁免"动作无结果"，
# 否则会把这类稿子里最有价值的一行判成流水账。
LEARNING_RE = re.compile(r"判断规则|我的判断|规则是|教训是|我学到|下次同类|反思")

# 文体硬规则：缺必备小节 = 硬性不合格，不靠模型自觉
# 每项 = (人话说明, 匹配正则)
STYLE_RULES = {
    "weekly": {
        "limit": 500,
        "required": [("结果小节", r"结果|交付|产出|完成"),
                     ("下期计划", r"计划|下一步|下周|待办")],
        "forbidden": [("方法论/成长反思类章节（周报不放，挪到述职）", r"方法论|经验沉淀|复盘思考|个人成长|心得")]},
    "monthly": {
        "limit": 1500,
        "required": [("目标达成度回看", r"目标|KPI|OKR|达成|完成率"),
                     ("对比轴（同比/环比/对目标）", r"同比|环比|较上月|上月|完成率|达成|目标值")],
        "forbidden": []},
    "review": {
        "limit": 2500,
        "required": [("带数字的代表战役", r"\d"),
                     ("不足与改进（不写这条整篇可信度打折）", r"不足|反思|改进|没做好|遗憾|教训")],
        "forbidden": [("目录式长篇背景", r"目录|第一章|背景综述")]},
    "self-review": {
        "limit": 1000,
        "required": [("达成率/完成率", r"达成率|完成率|达成|超额"),
                     ("目标与实际的对照", r"目标|指标|实际")],
        "forbidden": [("情绪化诉求（校准会上帮不了你）", r"加班很多|很辛苦|尽了全力|不容易|任劳任怨")]},
    "pitch": {
        "limit": 3500,
        "required": [("做成过的量化证据", r"\d"),
                     ("上任后的具体动作", r"上任|第一周|首月|前三十|30\s*天|90\s*天|我会先|接下来我")],
        "forbidden": [("空表态", r"努力学习|积极配合|不辜负|尽力而为|不负众望")]},
}

SENT_SPLIT = re.compile(r"[。！？!?；;\n]+")


def cn_len(text: str) -> int:
    """非空白字符数（中文按字计，英文按字符计，近似稿长）。"""
    return len(re.sub(r"\s+", "", text))


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text) if len(s.strip()) >= 4]


def split_blocks(text: str) -> list[tuple[str, str]]:
    """按空行切段，并携带每段所属的小节标题。

    标题本身既是分隔符也是上下文：「## 下周计划」之下的条目本就不该有结果，
    必须知道它属于哪个小节才能正确判断。
    """
    blocks: list[tuple[str, str]] = []
    section = ""
    buf: list[str] = []

    def flush() -> None:
        if buf:
            blocks.append((section, "\n".join(buf)))
            buf.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith("#"):
            flush()
            section = stripped.lstrip("# ").strip()
            continue
        buf.append(stripped)
    flush()
    return blocks


def has_any(sentence: str, words: list[str]) -> bool:
    return any(w in sentence for w in words)


# 子句层分析：句末标点会把"开会 5 次，沟通 12 人，处理邮件 30 封…"当成一句，
# 于是整句只要有数字就免检。并列活动子句达 STACK_MIN 且零结果子句 = 活动堆砌。
#
# 不要改用"数数字个数"当信号：实测那样会把「起点：128 间教室靠 4 张手工表拼接，
# 开学前需 4 个人投 6 个工作日」这种带基线的合法背景打成堆砌——惩罚量化表达，方向反了。
# 所以用一份专供堆砌检测的活动动词表：它们描述"出席与经手"，不描述产出，不会误伤结果句。
CLAUSE_SPLIT = re.compile(r"[，、,]")
STACK_MIN = 3


def clause_profile(sentence: str, action_words: list[str]) -> tuple[int, int]:
    """返回 (活动子句数, 结果子句数)。"""
    acts = results = 0
    pool = action_words + ACTIVITY_VERBS
    for c in CLAUSE_SPLIT.split(sentence):
        c = c.strip()
        if len(c) < 3:
            continue
        if has_any(c, pool):
            acts += 1
        if has_any(c, RESULT_SIGNALS):
            results += 1
    return acts, results


# ---------------------------------------------------------------- 隐私脱敏 ---

def _keep_edges(s: str, head: int = 2, tail: int = 2) -> str:
    body = max(len(s) - head - tail, 1)
    return s[:head] + "*" * body + (s[-tail:] if tail else "")


def _mask_mail(m) -> str:
    name, _, domain = m.group(0).partition("@")
    return (name[0] + "***@" + domain) if domain else "***"


PII_BLOCKING = [
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
     lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:]),
    ("身份证号", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), lambda m: _keep_edges(m.group(0))),
    ("银行卡号", re.compile(r"(?<!\d)\d{16,19}(?!\d)"), lambda m: _keep_edges(m.group(0))),
    ("邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), _mask_mail),
    ("学号", re.compile(r"(学号[:：]?\s*)(\d{6,12})"), lambda m: m.group(1) + _keep_edges(m.group(2))),
    ("薪资数字", re.compile(r"(薪资|工资|年薪|月薪|绩效奖|津贴|待遇)([^，。；\n]{0,6}?)(\d+(?:\.\d+)?\s*(?:万|千)?\s*元?)"),
     lambda m: m.group(1) + m.group(2) + "〔略〕"),
]

# 只提示、不阻断：称谓正则难免误伤（"三位老师""王主任办公室"），
# 但把第三方真名写进交给领导的稿子本身就是风险，所以允许脱敏。
PII_WARN_ONLY = [
    ("第三方称谓姓名",
     re.compile(r"[张王李赵刘陈杨黄周吴徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤]"
                r"(老师|主任|经理|院长|处长|科长|组长|师傅|工程师|同学)(?![生室务])"),
     lambda m: "某" + m.group(1)),
    ("敏感事项", re.compile(r"低保|家庭困难|特困|单亲|残疾|心理(健康|问题|测评)|传染病|资助名单|助学贷款"), None),
]


def find_pii(text: str) -> list[tuple[str, str, bool]]:
    """返回 [(类型, 命中片段, 是否阻断交付)]。"""
    hits = []
    for name, pat, _ in PII_BLOCKING:
        hits += [(name, m.group(0)[:24], True) for m in pat.finditer(text)]
    for name, pat, _ in PII_WARN_ONLY:
        hits += [(name, m.group(0), False) for m in pat.finditer(text)]
    return hits


def redact_text(text: str) -> tuple[str, int]:
    """掩码标识符与称谓姓名；敏感事项只提示不改写。返回 (新文本, 替换处数)。"""
    n = 0
    for _, pat, mask in PII_BLOCKING + PII_WARN_ONLY:
        if mask is None:
            continue

        def _sub(m, _mask=mask):
            nonlocal n
            n += 1
            return _mask(m)

        text = pat.sub(_sub, text)
    return text, n


def doc_title(text: str) -> str:
    """识别素材首行的标题（不是工作项）。

    素材第一行常是"Q3 随手记（没整理）"。它不是待汇报的事，按工作项检查会用
    "整理/记"这类动词去问用户"这件事的产出物是什么"，白占一个提问名额。
    判据不能用"含数字就不是标题"——"Q3" 里有 3，而"本周完成档案移交 412 份"
    既是短行又是真工作项。改用标题词表（随手记/清单/草稿…），单位可自加。
    """
    words = globals().get("DOC_TITLE_WORDS") or []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if len(s) > 24 or re.search(r"[。！？!?；;]", s):
            return ""
        return s if any(w in s for w in words) else ""
    return ""


# ------------------------------------------------------------------ 核心逻辑 ---

def _strong_evidence(block: str):
    """超额证据。"完成率 62%" 不算超额——把它当证据会反过来指责一个诚实
    自评未达成的人"低报"，恰好惩罚了最诚实的写法。"""
    for m in EVID_STRONG_RE.finditer(block):
        if m.group(0) in ("达成率", "完成率"):
            pct = re.search(rf"{m.group(0)}[^0-9%]{{0,6}}(\d+(?:\.\d+)?)\s*[%％]", block)
            if pct and float(pct.group(1)) >= 100:
                return m
            continue
        return m
    return None


def rating_issues(text: str) -> list[dict]:
    """自评等级与证据是否相称——按维度小节独立判定。

    不能用别的维度的硬证据替本维度背书，所以逐 block 看。只在绩效自评文体下启用：
    述职、周报里也常出现"达成"，套上去就是误伤。
    """
    out = []
    for section, block in split_blocks(text):
        strong_claim = RATING_STRONG_RE.search(block)
        meet_claim = RATING_MEET_RE.search(block)
        miss_claim = RATING_MISS_RE.search(block)
        ev_strong = _strong_evidence(block)
        ev_miss = EVID_MISS_RE.search(block)
        where = (section or block).strip()[:34]
        if strong_claim and not ev_strong:
            out.append({"type": "等级与证据不符", "text": where,
                        "ask": f"本维度自评「{strong_claim.group(0)}」，但通篇没有超额证据"
                               f"（提前多少、从多少降到多少、被谁沿用）。要么补证据，要么下调等级。"})
        elif meet_claim and ev_miss:
            out.append({"type": "等级与证据不符", "text": where,
                        "ask": f"本维度自评「{meet_claim.group(0)}」，但同段出现「{ev_miss.group(0)}」。"
                               f"未完成的部分写进不足与改进，比在校准会上被当场指出好得多。"})
        elif miss_claim and ev_strong:
            out.append({"type": "等级与证据不符", "text": where,
                        "ask": f"自评「{miss_claim.group(0)}」但本段有「{ev_strong.group(0)}」这类超额证据，"
                               f"可能是低报。绩效校准上过度谦虚换不到同情，只会少拿应得的。"})
    return out


def is_meta_complaint(s: str) -> bool:
    """这句话是在抱怨"写不出来"，还是在讲一件工作？

    词表堵不住同构说法：收了「说不出来」，人写「写不出来」就又漏，
    还会白占一个提问名额、问出一个用户答不出的问题。
    所以用结构判据（动词 + 不 + 出/来），短语表只兜"不知道写啥"这类不规则说法。

    护栏：句中含工作量信息（数字或 份/个/数/人/次/元…）时**不算**元抱怨。
    "我说不出准确份数"是真缺口，必须继续追问——没护栏的话结构判据会把漏报伪装成干净。
    """
    if re.search(r"\d|[份个数人次元条间]", s):
        return False
    if has_any(s, globals().get("META_COMMENT_WORDS") or []):
        return True
    return META_COMPLAINT_RE.search(s) is not None


def audit(text: str, mode: str, word_limit: int, style: str = "") -> dict:
    title = doc_title(text)
    sents = [s for s in split_sentences(text) if s != title]
    report: dict = {
        "mode": mode,
        "style": style or None,
        "word_count": cn_len(text),
        "sentence_count": len(sents),
        "issues": [],
        "metrics": {},
    }

    action_only, quantified, vague_hits, risk_dangling, plan_loose, unverified = [], [], [], [], [], []
    pseudo_hits, praise_hits, neg_hits = [], [], []
    ratio_hits, save_hits, todo_hits, todo_in_result, stacked = [], [], [], [], []
    money_hits = []
    meta_skipped = []
    target_skipped = 0
    deliverable_sents = 0
    # gaps 模式跑在口语素材上，汇报体动词几乎不出现，必须放宽动作识别
    action_words = ACTION_VERBS + COLLOQUIAL_ACTIONS if mode == "gaps" else ACTION_VERBS

    for section, block in split_blocks(text):
        # 只看小节标题：扫整段正文会让"后续可复用"这类结果描述把整段误判成计划区
        section_is_plan = has_any(section, PLAN_SECTION_WORDS)

        for line in block.split("\n"):
            # 风险是否"有下文"按**行**判定：真实素材常整篇不空行，按段落判会让
            # 全文共享一个 followup，一处"已办理"就替所有风险背书（实测风险集体哑火）。
            line_has_followup = has_any(line, FOLLOWUP_SIGNALS)
            for s in split_sentences(line):
                if s == title:
                    continue          # 素材标题不是工作项
                if TARGET_PREFIX_RE.match(s):
                    target_skipped += 1
                    continue          # "目标：完成月度检查"讲的是还没做的事，别拿成果标准要求它
                if is_meta_complaint(s):
                    meta_skipped.append(s)
                    continue          # 对"写汇报"本身的抱怨，不是待汇报的事
                # 只认小节标题或句首前缀，避免正文里一个"待办"就把整句当计划条目
                is_plan = section_is_plan or PLAN_PREFIX_RE.match(s) is not None
                is_action = has_any(s, action_words)
                is_result = has_any(s, RESULT_SIGNALS)
                has_num = bool(NUM_RE.search(s) or CN_NUM_RE.search(s))

                if TODO_PENDING_RE.match(s) or TODO_DONE_RE.match(s):
                    todo_hits.append(s)
                    if has_any(section, RESULT_SECTION_WORDS) and TODO_PENDING_RE.match(s):
                        todo_in_result.append(s)
                if RATIO_NO_BASE_RE.search(s) and not has_any(s, BASELINE_WORDS):
                    ratio_hits.append((RATIO_NO_BASE_RE.search(s).group(0), s))
                if SAVE_RE.search(s) and not has_any(s, BASELINE_WORDS):
                    save_hits.append(s)          # 声称省了钱/工时 → 要基数
                elif MONEY_RE.search(s) and not has_any(s, PERIOD_WORDS):
                    money_hits.append(s)         # 只是金额事实 → 要统计区间，话术不同

                if mode == "gaps" and has_any(s, UNVERIFIED_MARKERS):
                    unverified.append(s)

                if is_plan:
                    # 计划条目不要求结果，但必须能被验收：有时间点或责任人
                    # 剥掉「下周计划：」这类周期前缀，防止周期标签冒充完成时限
                    s_body = PLAN_PREFIX_RE.sub("", s)
                    if is_action and not (has_any(s_body, DEADLINE_SIGNALS) or has_any(s_body, OWNER_SIGNALS)):
                        plan_loose.append(s)
                elif style in ("review", "pitch") and LEARNING_RE.search(s):
                    pass              # STAR-L 的 L 行：给的是判断规则，不是待兑现的动作
                else:
                    deliverable_sents += 1
                    acts, results = clause_profile(s, action_words)
                    if acts >= STACK_MIN and results == 0:
                        stacked.append((acts, s))   # 堆砌句不吃"有数字即达标"的豁免
                    elif is_action and not (is_result or has_num):
                        action_only.append(s)

                if has_num:
                    quantified.append(s)
                    if PERCENT_RE.search(s) and not has_any(s, CALIBER_WORDS):
                        report["issues"].append({
                            "type": "口径缺失",
                            "text": s,
                            "ask": "这个数字的分子/分母和时间窗是什么？跟谁比？",
                        })
                for v in VAGUE_QUANTIFIERS:
                    if v in s:
                        vague_hits.append((v, s))
                for pm in PSEUDO_PRECISION_RE.finditer(s):
                    pseudo_hits.append((pm.group(0).strip(), s))
                for w in VAGUE_PRAISE:
                    if w in s:
                        praise_hits.append((w, s))
                        break
                for w in NEGATIVE_METRICS:
                    if w in s and not WINDOW_RE.search(s):
                        neg_hits.append((w, s))
                        break
                # 风险是否漏报按行判定；先剥掉"零投诉/无差错"这类否定式成绩，它们不是风险
                if has_any(RISK_NEG_RE.sub("", s), RISK_SIGNALS) and not line_has_followup:
                    risk_dangling.append(s)

    denom = max(deliverable_sents, 1)
    total = max(len(sents), 1)
    metrics = report["metrics"]
    # 堆砌句是最典型的流水账，计入分子
    metrics["流水账率"] = round((len(action_only) + len(stacked)) / denom * 100, 1)
    metrics["量化密度"] = round(len(quantified) / total * 100, 1)
    metrics["活动堆砌数"] = len(stacked)
    metrics["元抱怨跳过数"] = len(meta_skipped)
    metrics["目标行跳过数"] = target_skipped
    report["meta_skipped"] = meta_skipped
    metrics["模糊量词数"] = len(vague_hits)
    metrics["风险漏报数"] = len(risk_dangling)
    metrics["计划条目裸奔数"] = len(plan_loose)
    metrics["状态未证实数"] = len(unverified)
    metrics["伪精确数"] = len(pseudo_hits)
    metrics["空泛评价数"] = len(praise_hits)
    metrics["负向指标缺时间窗数"] = len(neg_hits)
    metrics["比例无基数数"] = len(ratio_hits)
    metrics["收益缺口径数"] = len(save_hits)
    metrics["金额缺区间数"] = len(money_hits)
    metrics["残留待办符号数"] = len(todo_hits)
    metrics["未完成混进成果数"] = len(todo_in_result)
    metrics["套话命中数"] = sum(1 for c in CLICHE if c in text)
    report["word_count_target"] = word_limit

    for s in unverified:
        report["issues"].insert(0, {
            "type": "状态未证实",
            "text": s,
            "ask": "这里有「应该/好像/反正」，说明你自己都没核实。这件事到底成没成？汇报里不能出现没核实的状态。",
        })
    for v, s in vague_hits:
        report["issues"].append({
            "type": "缺具体数字",
            "text": s,
            "ask": f"「{v}」能不能换成具体数？拿不到的话，写清楚为什么拿不到、用什么替代口径。",
        })
    for acts, s in stacked:
        report["issues"].append({
            "type": "活动堆砌",
            "text": s,
            "ask": f"这句并列了 {acts} 个动作，一个产出都没有。要么每项补上结果，"
                   f"要么合并成一句真正有价值的结论——这几件事里哪件真的改变了什么？",
        })
    for w, s in pseudo_hits:
        report["issues"].append({
            "type": "伪精确",
            "text": s,
            "ask": f"「{w}」是估的还是查出来的？能给准确数就给准确数；确实只能估，就写成「估算：数字 + 算法」，别让它看起来像实测。",
        })
    for w, s in praise_hits:
        report["issues"].append({
            "type": "空泛评价",
            "text": s,
            "ask": f"「{w}」是你的结论，不是证据。换成可核对状态：多少人参加、满意度几个数、被谁引用、退回几次。",
        })
    for w, s in neg_hits:
        report["issues"].append({
            "type": "负向指标缺时间窗",
            "text": s,
            "ask": f"「{w}」要说清统计区间——连续多少天、本月还是全年？没区间的「没出事」读者不会信。",
        })
    for s in todo_in_result:
        report["issues"].append({
            "type": "未完成混进成果",
            "text": s,
            "ask": "这条还没打勾却出现在结果小节里。挪到「进行中/风险」，或写明做到哪一步、卡在谁那里。",
        })
    for s in todo_hits:
        report["issues"].append({
            "type": "残留待办符号",
            "text": s,
            "ask": "交给领导的正文里不该有 [ ] / [x]。已完成的改写成结果句，未完成的写成带时限的推进项。",
        })
    for w, s in ratio_hits:
        report["issues"].append({
            "type": "比例无基数",
            "text": s,
            "ask": f"「{w}」的基数是多少？「成本翻倍」要写成「从 X 到 2X」，否则读者无法判断大小。",
        })
    for s in save_hits:
        report["issues"].append({
            "type": "收益缺口径",
            "text": s,
            "ask": "省下来的钱/工时要有来源：原来是多高的基数、统计区间哪一段、按什么口径算的。",
        })
    for s in money_hits:
        report["issues"].append({
            "type": "金额缺统计区间",
            "text": s,
            "ask": "这笔金额说清统计区间（几月到几月）和口径（发放/到账/申请）；"
                   "如果是和上期比，给出上期数。",
        })
    for s in action_only:
        if mode == "gaps":
            report["issues"].append({
                "type": "结果未确认",
                "text": s,
                "ask": "这件事的产出物是什么？（一份表 / 一个数 / 一件被解决的事）没有产出的事不用写进汇报。",
            })
        else:
            report["issues"].append({
                "type": "动作无结果",
                "text": s,
                "ask": "这件事最后怎么样了？省了多少时间/钱/人力，或者避免了什么损失？",
            })
    for s in risk_dangling:
        report["issues"].append({
            "type": "问题没下文",
            "text": s,
            "ask": "这个问题谁负责、下一步做什么、需要谁决策？",
        })
    for s in plan_loose:
        report["issues"].append({
            "type": "计划缺责任/时限",
            "text": s,
            "ask": "这条计划到什么时候算完成、谁负责？没有验收点的计划下周期没法交代。",
        })

    if style:
        rules = STYLE_RULES.get(style)
        if rules is None:
            report["issues"].append({"type": "文体未知", "text": style,
                                     "ask": f"支持的文体：{'/'.join(STYLE_RULES)}"})
        else:
            if not word_limit:
                word_limit = rules["limit"]
            for label, pat in rules["required"]:
                if not re.search(pat, text):
                    report["issues"].append({
                        "type": "文体缺件",
                        "text": f"（全文）",
                        "ask": f"作为「{style}」稿，缺{label}。这一项缺失会让读者直接怀疑稿子的完整性。",
                    })
            for label, pat in rules["forbidden"]:
                bad = re.search(pat, text)
                if bad:
                    report["issues"].append({
                        "type": "文体越界",
                        "text": f"命中「{bad.group(0)}」",
                        "ask": f"作为「{style}」稿不该有{label}。",
                    })

    rating_hits = rating_issues(text) if style == "self-review" else []
    metrics["等级与证据不符数"] = len(rating_hits)
    report["issues"].extend(rating_hits)

    pii = find_pii(text)
    pii_block = [h for h in pii if h[2]]
    pii_warn = [h for h in pii if not h[2]]
    metrics["隐私阻断项数"] = len(pii_block)
    metrics["隐私提示项数"] = len(pii_warn)
    report["pii"] = {"block": pii_block, "warn": pii_warn}
    for name, frag, _ in pii_block:
        report["issues"].append({
            "type": "隐私外泄风险",
            "text": frag,
            "ask": f"交给领导的正文里不该有「{name}」。用 `--redact` 出一份脱敏副本，"
                   f"或改成群体化描述（如「17 个学院联络人」而不是逐个点名）。",
        })

    if mode == "final":
        # 评分：满分 100，逐项扣分
        score = 100.0
        score -= min(35.0, metrics["流水账率"] * 0.7)
        score -= min(25.0, metrics["活动堆砌数"] * 12)
        score -= min(24.0, metrics["等级与证据不符数"] * 12)
        score -= max(0.0, 15.0 - metrics["量化密度"])
        score -= min(20.0, metrics["模糊量词数"] * 2.5)
        score -= min(15.0, metrics["风险漏报数"] * 5)
        score -= min(15.0, metrics["套话命中数"] * 3)
        score -= min(8.0, metrics["计划条目裸奔数"] * 4)
        score -= min(12.0, metrics["伪精确数"] * 3)
        score -= min(16.0, metrics["空泛评价数"] * 4)
        score -= min(9.0, metrics["负向指标缺时间窗数"] * 3)
        score -= min(12.0, metrics["比例无基数数"] * 4)
        score -= min(12.0, metrics["收益缺口径数"] * 3)
        score -= min(10.0, metrics["残留待办符号数"] * 2.5)
        score -= min(20.0, metrics["未完成混进成果数"] * 10)
        score -= min(36.0, sum(1 for i in report["issues"] if i["type"] == "文体缺件") * 12)
        if word_limit:
            over = cn_len(text) - word_limit
            if over > 0:
                score -= min(10.0, over / word_limit * 20)
                report["issues"].append({
                    "type": "超篇幅",
                    "text": f"当前 {cn_len(text)} 字，超出目标 {word_limit} 字",
                    "ask": "砍掉过程描述，只保留结果和影响。",
                })
        metrics["得分"] = int(max(0.0, score))
        metrics["未决问题数"] = len(report["issues"])
        metrics["判定"] = (
            "可交付"
            if metrics["得分"] >= 75 and metrics["流水账率"] < 20 and metrics["未决问题数"] == 0
            else "需返工"
        )
    else:
        metrics["待补条目"] = len(report["issues"])
        metrics["未决问题数"] = len(report["issues"])

    return report


# 提问优先级：把问题分成「必须问用户」和「自己能改」两类。
# ask 类才占提问名额；fix 类塞进提问只会挤掉真正该问的事。
ISSUE_IMPACT = {
    "状态未证实": ("ask", 95),        # 作者自己都不知道成没成，后面一切都不成立
    "未完成混进成果": ("ask", 90),
    "等级与证据不符": ("ask", 88),   # 要么补证据要么改等级，机器不能替用户决定
    "结果未确认": ("ask", 80),
    "动作无结果": ("ask", 80),
    "收益缺口径": ("ask", 75),
    "金额缺统计区间": ("ask", 72),
    "口径缺失": ("ask", 75),
    "比例无基数": ("ask", 70),
    "问题没下文": ("ask", 65),
    "伪精确": ("ask", 60),
    "活动堆砌": ("ask", 55),
    "缺具体数字": ("ask", 50),
    "空泛评价": ("ask", 45),
    "计划缺责任/时限": ("ask", 40),
    "负向指标缺时间窗": ("fix", 30),
    "残留待办符号": ("fix", 20),
    "超篇幅": ("fix", 15),
    "隐私外泄风险": ("fix", 10),      # 该改写，不该拿去问用户
    "文体缺件": ("fix", 10),
    "文体越界": ("fix", 5),
    "文体未知": ("fix", 5),
}


PER_TYPE_CAP = 2   # 同一类问题最多占几个提问名额


def prioritize(issues: list[dict], top: int) -> tuple[list[dict], list[dict]]:
    """按句归并，只让 ask 类占提问名额，其余归入自查区。

    同一句常同时踩中"没数字 + 太空泛 + 没产出"，必须合成一问；
    否则一句烂话吃掉三个名额，真正该问的事反而没人问。
    同一类问题最多占 2 格：状态未核实权重最高，不设上限会让它霸屏，
    把"这季度少花了多少钱"这种真正值钱的提问挤到自查区。
    """
    by_key: dict[str, dict] = {}
    fixes: list[dict] = []
    for it in issues:
        kind, weight = ISSUE_IMPACT.get(it["type"], ("ask", 30))
        if kind == "fix":
            fixes.append(it)
            continue
        key = re.sub(r"\s+", "", it["text"])[:60]
        cur = by_key.get(key)
        if cur is None or weight > cur["weight"]:
            merged = dict(it)
            merged["weight"] = weight
            also = set(cur["also"]) if cur else set()
            merged["also"] = sorted(also | {it["type"]})
            by_key[key] = merged
        else:
            cur["also"] = sorted({*cur["also"], it["type"]})
    ranked = sorted(by_key.values(), key=lambda x: -x["weight"])

    asks: list[dict] = []
    rest: list[dict] = []
    per_type: dict[str, int] = {}
    for item in ranked:
        if len(asks) < top:
            t = item["type"]
            if per_type.get(t, 0) < PER_TYPE_CAP:
                per_type[t] = per_type.get(t, 0) + 1
                asks.append(item)
                continue
        rest.append(item)
    return asks, rest + fixes


def render(report: dict) -> str:
    m = report["metrics"]
    lines = []
    lines.append("## 稿件体检报告")
    lines.append("")
    lines.append(f"- 篇幅：{report['word_count']} 字 / {report['sentence_count']} 句")
    lines.append(f"- 状态未核实（出现应该/好像/反正）：{m['状态未证实数']} 处")
    lines.append(f"- 流水账率（只有动作没有结果的句子占比）：{m['流水账率']}%")
    if m.get("活动堆砌数"):
        lines.append(f"- 其中活动堆砌句（一句并列≥3 个动作零产出）：{m['活动堆砌数']} 句")
    if m.get("等级与证据不符数"):
        lines.append(f"- 自评等级与证据不符的维度：{m['等级与证据不符数']} 处")
    if m.get("元抱怨跳过数"):
        lines.append(f"- 跳过的元抱怨句（不是工作项，占提问名额没意义）：{m['元抱怨跳过数']} 句")
    if m.get("目标行跳过数"):
        lines.append(f"- 跳过的目标声明行（讲打算做什么，不要求产出）：{m['目标行跳过数']} 行")
    lines.append(f"- 量化密度（带数字的句子占比）：{m['量化密度']}%")
    lines.append(f"- 模糊量词命中：{m['模糊量词数']} 处")
    lines.append(f"- 伪精确（约/余/左右）：{m['伪精确数']} 处")
    lines.append(f"- 空泛评价（效果良好类）：{m['空泛评价数']} 处")
    lines.append(f"- 说「没出事」却没给时间窗：{m['负向指标缺时间窗数']} 处")
    lines.append(f"- 比例没基数（翻倍/四成）：{m['比例无基数数']} 处")
    lines.append(f"- 省的钱/工时没口径：{m['收益缺口径数']} 处")
    if m.get("金额缺区间数"):
        lines.append(f"- 金额没给统计区间：{m['金额缺区间数']} 处")
    lines.append(f"- 残留待办框：{m['残留待办符号数']} 处（其中混在成果里的 {m['未完成混进成果数']} 处）")
    lines.append(f"- 报了问题没下文的段落：{m['风险漏报数']} 处")
    lines.append(f"- 无时限也无责任人的计划条目：{m['计划条目裸奔数']} 处")
    lines.append(f"- 套话命中：{m['套话命中数']} 处")
    if m.get("隐私提示项数") or m.get("隐私阻断项数"):
        lines.append(f"- 隐私：阻断级 {m['隐私阻断项数']} 项，提示级 {m['隐私提示项数']} 项")
    if report["mode"] == "final":
        lines.append(f"- **得分：{m['得分']} / 100，未决问题 {m['未决问题数']} 条 —— {m['判定']}**")
    else:
        lines.append(f"- 待补条目：{m['待补条目']} 条")

    if not report["issues"]:
        lines.append("")
        lines.append("未发现结构性问题。")
        return _append_pii_notes(lines, report)

    lines.append("")
    if report["mode"] == "gaps":
        top = report.get("top", 5)
        asks, rest = prioritize(report["issues"], top)
        lines.append(f"## 先问这几条（一次问完，别挤牙膏）")
        for i, it in enumerate(asks, 1):
            text = it["text"] if len(it["text"]) <= 60 else it["text"][:60] + "…"
            extra = [x for x in it.get("also", []) if x != it["type"]]
            tag = it["type"] + (f"（同时：{'、'.join(extra)}）" if extra else "")
            lines.append(f"{i}. [{tag}] {text}")
            lines.append(f"   → {it['ask']}")
        if rest:
            lines.append("")
            lines.append(f"## 其余 {len(rest)} 处可自查（不必问用户）")
            for it in rest[:15]:
                text = it["text"] if len(it["text"]) <= 46 else it["text"][:46] + "…"
                lines.append(f"- [{it['type']}] {text}")
            if len(rest) > 15:
                lines.append(f"- …另有 {len(rest) - 15} 处同类")
        return _append_pii_notes(lines, report)

    lines.append("## 逐条修改点")
    seen = set()
    idx = 0
    for it in report["issues"]:
        key = (it["type"], it["text"], it["ask"])
        if key in seen:
            continue
        seen.add(key)
        idx += 1
        text = it["text"] if len(it["text"]) <= 60 else it["text"][:60] + "…"
        lines.append(f"{idx}. [{it['type']}] {text}")
        lines.append(f"   → {it['ask']}")
        if idx >= 25:
            lines.append(f"…（其余 {len(report['issues']) - idx} 条同类问题略）")
            break
    return _append_pii_notes(lines, report)


def _append_pii_notes(lines: list[str], report: dict) -> str:
    warn = (report.get("pii") or {}).get("warn") or []
    if warn:
        lines.append("")
        lines.append("## 隐私提示（不挡交付，自行判断）")
        for name, frag, _ in warn[:12]:
            tip = ("交给领导前考虑改成「某主任」「17 个学院联络人」这类群体化说法；"
                   "要一键掩码就加 --redact") if name == "第三方称谓姓名" else \
                 "涉及学生困境的描述，只说人数和事项，别写成能被对号入座的个案"
            lines.append(f"- [{name}] {frag} —— {tip}")
        if len(warn) > 12:
            lines.append(f"- …另有 {len(warn) - 12} 处同类")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="职场成果稿体检")
    ap.add_argument("file", help="待检查的 .md/.txt 文件路径")
    ap.add_argument("--mode", choices=["gaps", "final"], default="gaps",
                    help="gaps=找待补空位（写稿前）；final=成稿评分（写稿后）")
    ap.add_argument("--word-limit", type=int, default=0, help="目标字数，0 表示不限（给了 --style 时按文体默认上限）")
    ap.add_argument("--style", choices=sorted(STYLE_RULES), default="",
                    help="按文体套硬规则：weekly/monthly/review/self-review/pitch")
    ap.add_argument("--profile", default="", help="套用 wordlists.json 里的词表档（school / factory / retail）")
    ap.add_argument("--words", default="", help="自定义词表 JSON 路径，默认用技能自带 wordlists.json")
    ap.add_argument("--top", type=int, default=5,
                    help="gaps 模式一次给出的提问数（按影响面排序、同句归并），默认 5")
    ap.add_argument("--redact", action="store_true",
                    help="另存一份脱敏副本 <原名>-脱敏.md，不改写原文件")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    args = ap.parse_args()
    wordpack.apply(globals(), args.profile, args.words)

    try:
        with open(args.file, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except OSError as e:
        print(f"读取失败：{args.file} —— {e}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        with open(args.file, "rb") as f:
            text = f.read().decode("gbk", "ignore")

    if not text.strip():
        print("文件为空，没有可检查的内容。", file=sys.stderr)
        return 2

    if args.redact:
        new, n = redact_text(text)
        out_path = args.file.rsplit(".", 1)[0] + "-脱敏.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(new)
        left = [h for h in find_pii(new) if not h[2] and h[0] == "敏感事项"]
        msg = (f"已脱敏 {n} 处 → {out_path}（原文件未改动）\n"
               + (f"仍剩 {len(left)} 处敏感事项只提示不改写，需你手动改成群体化说法\n" if left else "")
               + "下一步：对副本再跑一次 --mode final 确认干净。\n")
        sys.stdout.buffer.write(msg.encode("utf-8"))
        sys.stdout.buffer.flush()
        return 0

    report = audit(text, args.mode, args.word_limit, args.style)
    report["top"] = max(args.top, 1)
    out = json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report)
    # 直接写 UTF-8 字节：Windows GBK 控制台下 print 会先吐半截再抛异常
    sys.stdout.buffer.write(out.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
