#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""职场成果叙事引擎 —— 上期承诺闭环核对器.

汇报真正的信用不在本期写了多少数字，而在**上期答应的事这一期有没有交代**。
悄悄消失的承诺比流水账更伤信任，但它恰恰是肉眼最容易漏掉的。

把上一期正文和本期正文放在一起比对，输出四类结论：
  已兑现   上期承诺能在本期找到结果句
  存疑     找到了疑似对应项，需要人确认是不是同一件事
  未提及   本期完全没提 —— 必须补一句交代，或明确写"暂缓/取消，原因 X"
  连续顺延 同一件事连续两期都躺在计划里，说明一直没做成

用法:
  python scripts/promise_reconcile.py --prev 上周周报.md --current 本周周报.md
  python scripts/promise_reconcile.py --prev a.md --current b.md --json

只依赖标准库。退出码: 0 = 正常, 2 = 读文件失败, 3 = 上期没提取到任何承诺。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter

import wordpack

# 词表唯一来源：../wordlists.json（与体检器共用同一份，避免两处定义对不上）。
wordpack.apply(globals())

# 以下三条是切分结构，不是词汇，因此留在代码里
COORD_RE = re.compile(r"与此同时|同时|并且|另外|此外|以及")
DONE_RE = re.compile(r"已完成|已交付|已上线|已发布|已经")

NUM_RE = re.compile(r"\d+(?:\.\d+)?")
BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.、)]|\[[ xX]\])\s*")
PUNCT_RE = re.compile(r"[，。；：、！？“”\"'（）()《》【】\s\-—…]+")


def normalize(s: str) -> str:
    return PUNCT_RE.sub("", s).strip().lower()


def bigrams(s: str) -> Counter:
    return Counter(s[i:i + 2] for i in range(len(s) - 1)) if len(s) > 1 else Counter({s: 1})


def lcs_len(a: str, b: str) -> int:
    """最长连续共同片段长度。中文里 5 字以上的连续重合基本就是同一件具名事项。"""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def similarity(a: str, b: str) -> float:
    """承诺 a 的要点被 b 覆盖了多少。

    不用纯 Dice：承诺通常很短、本期素材通常是一长段，对称指标会被长度稀释，
    实测把已完成的事项误判成"未提及"。以非对称覆盖率为主、Dice 为辅，
    再用最长连续共同片段和共同数字做加成。
    """
    x, y = normalize(a), normalize(b)
    if not x or not y:
        return 0.0
    bx, by = bigrams(x), bigrams(y)
    total_x = sum(bx.values())
    if not total_x:
        return 0.0
    overlap = sum((bx & by).values())
    coverage = overlap / total_x
    dice = 2 * overlap / (total_x + sum(by.values()))
    run = lcs_len(x, y)
    lcs_bonus = 0.25 if run >= 5 else 0.10 if run >= 4 else 0.0
    num_bonus = 0.10 if set(NUM_RE.findall(a)) & set(NUM_RE.findall(b)) else 0.0
    return min(1.0, max(coverage, dice) + lcs_bonus + num_bonus)


def iter_sections(text: str, with_headings: bool = False):
    """产出 (小节标题, 行) —— 标题决定这一行是承诺还是结果。

    with_headings=True 时把标题本身也作为一行产出，让写在标题里的结论
    （如「战役一：排期迁移（9/15 承诺，9/12 交付）」）能充当证据。
    """
    section = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            section = stripped.lstrip("# ").strip()
            if with_headings and section:
                yield section, section
            continue
        yield section, stripped


def is_plan(section: str, line: str) -> bool:
    # 标题行本身：只有「下学期计划」「下周安排」这种以计划词结尾的才是计划区标签。
    # 否则「四、培训（计划 2 次，办成 1 次）」会被误判成计划条目，
    # 既不进证据池也不进承诺池，凭空消失——实测把写了整节的承诺报成"未提及"。
    if line == section:
        return PLAN_HEADING_RE.match(line) is not None
    body = BULLET_RE.sub("", line)
    # 小节同理：只有「下学期计划」「下周安排」这种结尾才算计划区，
    # 否则标题里出现"计划"二字会把整节正文从证据池里抹掉
    if PLAN_HEADING_RE.match(section):
        return True
    return any(re.match(rf"^(.{0,4}?){w}[:：]", body) for w in ("计划", "安排", "打算"))


PROMISE_MIN = 8


def dedupe(items: list[str], threshold: float = 0.6) -> list[str]:
    """去掉彼此高度相似的条目，避免同一条承诺计两次。"""
    kept: list[str] = []
    for it in items:
        if not any(similarity(it, k) >= threshold for k in kept):
            kept.append(it)
    return kept


def extract(text: str, want_plan: bool) -> list[str]:
    """want_plan=True 取承诺；False 取结果证据。

    承诺有两个来源：计划小节的条目，以及正文里的前向语句
    （「下季度我打算把 X 定下来，同时启动 Y」——只认小节会整条漏掉，
    漏掉之后还能输出"全部有据可查"，那是最坏的一种错）。
    证据则连非计划小标题一起扫，因为交付结论常写在标题里。
    """
    items: list[str] = []
    for section, line in iter_sections(text, with_headings=not want_plan):
        in_plan = is_plan(section, line)
        if not want_plan:
            if in_plan:
                continue
            body = BULLET_RE.sub("", line).strip()
            if len(normalize(body)) >= 6:
                items.append(body)
            continue

        if in_plan:
            body = BULLET_RE.sub("", line).strip()
            if len(normalize(body)) >= 6:
                items.append(body)
        elif FUTURE_RE.search(line) and not DONE_RE.search(line):
            # 先按句末切句：同一行里"本季度完成宣讲 6 场。下季度我打算…"不能整行算一条承诺
            for sent in re.split(r"[。；;！!]", line):
                if not FUTURE_RE.search(sent) or DONE_RE.search(sent):
                    continue
                for part in COORD_RE.split(BULLET_RE.sub("", sent)):
                    part = part.strip(" ：:，。")
                    if len(normalize(part)) >= PROMISE_MIN:
                        items.append(part)
    return dedupe(items)


def read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except OSError as e:
        print(f"读取失败：{path} —— {e}", file=sys.stderr)
        sys.exit(2)
    except UnicodeDecodeError:
        with open(path, "rb") as f:
            return f.read().decode("gbk", "ignore")


# 判定参数：由 eval_thresholds.py 在 10 条"有下文"+3 条"没下文"标注样本上标定。
# 绝对阈值不可用——真实匹配最低只有 0.167，而把阈值压到 0.15 会放行大量垃圾；
# 可靠信号是"排序 + 领先幅度"，不是"分数高不高"。改参数请先重跑评测。
FLOOR, LEAD, TRACE = 0.16, 0.16, 0.12
HIGH, LOW = FLOOR, TRACE      # 兼容旧命名



def has_defer(text: str) -> bool:
    return DEFER_RE.search(text) is not None


def reconcile(prev: str, current: str) -> dict:
    promises = extract(prev, want_plan=True)
    done_evidence = extract(current, want_plan=False)
    cur_plan = extract(current, want_plan=True)
    settled, deferred, doubtful, missing, rolled = [], [], [], [], []

    def rank(pool: list[str], promise: str) -> tuple[float, str, float]:
        """返回 (最高分, 命中项, 次高分)。"""
        scored = sorted(((similarity(promise, c), c) for c in pool), reverse=True)
        if not scored:
            return 0.0, "", 0.0
        first, item = scored[0]
        second = scored[1][0] if len(scored) > 1 else 0.0
        return first, item, second

    for p in promises:
        ev_s, ev_best, ev_2 = rank(done_evidence, p)
        rl_s, rl_best, rl_2 = rank(cur_plan, p)
        item = {"promise": p, "score": round(ev_s, 3), "matched": ev_best}
        conf_ev = ev_s >= FLOOR and (ev_s - ev_2) >= LEAD
        conf_rl = rl_s >= FLOOR and (rl_s - rl_2) >= LEAD

        # 分数认得出"话题相关"，认不出"是不是同一件具名事项"：
        # 近邻负样本实测 0.65/0.41/0.37，比合法正样本最低分 0.167 还高，
        # 只能靠对象与文档类型冲突拦，冲突一律交回人工确认。
        reason = wordpack.conflict_reason(p, ev_best, WORDS) if ev_best else None
        reason_rl = wordpack.conflict_reason(p, rl_best, WORDS) if rl_best else None

        if conf_ev and reason:
            item["conflict"] = reason
            doubtful.append(item)
        elif conf_rl and rl_s > ev_s and not reason_rl:
            rolled.append({"promise": p, "current": rl_best, "score": round(rl_s, 3)})
        elif conf_ev and has_defer(ev_best):
            deferred.append(item)
        elif conf_ev:
            if conf_rl and not reason_rl:
                item["also_planned"] = rl_best
            settled.append(item)
        elif ev_s >= TRACE or rl_s >= TRACE:
            if reason:
                item["conflict"] = reason
            doubtful.append(item)
        else:
            missing.append(item)

    return {
        "promises_found": len(promises),
        "settled": settled, "deferred": deferred, "doubtful": doubtful,
        "missing": missing, "rolled": rolled,
    }


def render(r: dict) -> str:
    lines = ["## 上期承诺闭环核对", ""]
    if not r["promises_found"]:
        lines.append("上期正文里没提取到任何计划/待办条目，无法核对。请确认上期文件是否含「下周计划」这类小节。")
        return "\n".join(lines)

    lines.append(f"- 上期承诺 {r['promises_found']} 条，逐条核对结果："
                 f"已兑现 {len(r['settled'])}、有交代未完成 {len(r['deferred'])}、存疑 {len(r['doubtful'])}、"
                 f"**未提及 {len(r['missing'])}**、**连续顺延 {len(r['rolled'])}**")
    lines.append("")
    lines.append("| 上期承诺 | 本期状态 | 依据 / 建议动作 |")
    lines.append("|---|---|---|")

    def cut(s, k=30):
        return s if len(s) <= k else s[:k] + "…"

    for i in r["settled"]:
        note = f"{cut(i['matched'], 34)}（覆盖度 {i['score']}）"
        if i.get("also_planned"):
            note += f"；余量仍在计划：{cut(i['also_planned'], 18)}"
        lines.append(f"| {cut(i['promise'])} | 已兑现 | {note} |")
    for i in r["deferred"]:
        lines.append(f"| {cut(i['promise'])} | **有交代未完成** | {cut(i['matched'], 26)}（{i['score']}）"
                     f"——提到了但没做完，补一个明确时间点，或正式写「取消，原因」 |")
    for i in r["doubtful"]:
        why = f"　⚠ {i['conflict']}" if i.get("conflict") else ""
        lines.append(f"| {cut(i['promise'])} | **存疑** | 疑似对应：{cut(i['matched'], 24)}（{i['score']}）{why} |")
    for i in r["missing"]:
        lines.append(f"| {cut(i['promise'])} | **未提及** | 本期必须补一句交代，或写明「暂缓 / 取消，原因」 |")
    for i in r["rolled"]:
        lines.append(f"| {cut(i['promise'])} | **连续顺延** | 本期计划仍在写：{cut(i['current'], 26)}（{i['score']}）"
                     f"——两期都没做成，要么给时间点要么砍掉 |")

    unresolved = len(r["deferred"]) + len(r["missing"]) + len(r["rolled"])
    pending = len(r["doubtful"])
    lines.append("")
    if not unresolved and not pending:
        lines.append("**结论**：上期承诺全部有据可查。")
    else:
        parts = []
        if unresolved:
            parts.append(f"{unresolved} 条要补交代（未提及最伤信用，有交代未完成次之）")
        if pending:
            parts.append(f"{pending} 条**没查清**，需你确认是不是同一件事")
        lines.append("**结论**：" + "；".join(parts)
                     + "——读者最先问的永远是「上次说的那件事呢」。")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="上期承诺闭环核对")
    ap.add_argument("--prev", required=True, help="上一期正文（含计划小节）")
    ap.add_argument("--current", required=True, help="本期正文")
    ap.add_argument("--profile", default="", help="套用 wordlists.json 里的词表档（school / factory / retail）")
    ap.add_argument("--words", default="", help="自定义词表 JSON 路径，默认用技能自带 wordlists.json")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()
    wordpack.apply(globals(), args.profile, args.words)

    r = reconcile(read(args.prev), read(args.current))
    out = json.dumps(r, ensure_ascii=False, indent=2) if args.json else render(r)
    # 直接写 UTF-8 字节：Windows GBK 控制台下 print 会先吐半截再抛异常
    sys.stdout.buffer.write(out.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()
    return 0 if r["promises_found"] else 3


if __name__ == "__main__":
    sys.exit(main())
