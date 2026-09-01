#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阈值评测：给 promise_reconcile 的相似度一个可证伪的依据.

对账器的 HIGH/LOW 两个阈值不能靠手感调。本脚本用带标注的检索样本回答三个问题：
  1. 每条承诺能否在候选里把正确的那句排到第一（top-1 命中率）
  2. 正样本的最低分与负样本的最高分之间是否存在可分间隙
  3. 若存在间隙，HIGH 该取多少；若不存在，直说"当前指标分不开"，不要假装能分

用法:
  python scripts/eval_thresholds.py
  python scripts/eval_thresholds.py --sweep

退出码: 0 = 存在可分间隙, 1 = 无间隙（需要改算法而不是调阈值）。
"""

from __future__ import annotations

import argparse
import sys

from promise_reconcile import similarity
from wordpack import conflict_reason, load

# 每条 = (上期承诺, 正确候选句, [干扰候选句])
# 样本全部来自真实使用与探针，包含几个曾经判错 hard case
CASES = [
    (
        "9/15 前完成教务排期系统数据迁移，由我牵头。",
        "战役一：教务排期系统数据迁移（9/15 承诺，9/12 交付）",
        ["热水系统改造方案已评审通过，10/8 下发施工单。",
         "排期规则文档更新至第 3 版，覆盖 12 类例外情形。",
         "受理师生教务咨询 1204 人次。"],
    ),
    (
        "9/15 前完成教务排期系统数据迁移，由我牵头。",
        "排期系统迁移这事总算弄完了，前后折腾了一个多月，导数据的时候发现重复课程 316 条",
        ["两个学院本学期线上请假单 1043 单。",
         "宿舍调整通知已发，涉及 214 人。",
         "场地已锁定，讲师确认 2 人。"],
    ),
    (
        "组织一次全校辅导员业务培训。",
        "辅导员培训本来要搞的，后来跟迎新场地冲突了，就推迟了，下季度再说吧",
        ["报销流程的问题已经反馈给财务。",
         "受理师生教务咨询 1204 人次。",
         "走访宿舍 6 间。"],
    ),
    (
        "推动 3 个学院开通线上请假审批流程。",
        "请假审批推动了两个学院开通，还有一个学院说他们系统要换，暂时先不上",
        ["新生政策宣讲完成，覆盖 600 名家长。",
         "与 17 个学院交叉核对新生名单，锁定信息不一致 23 条。",
         "并发参数过低已调参，连续 2 日无复现。"],
    ),
    (
        "完成宿舍调整通知发放，覆盖 3 个学院。",
        "宿舍调整通知已发，涉及 214 人，各学院已完成签收。",
        ["8/26 10:00 按时向分院报送报到率。",
         "绿色通道材料缺 1 份低保证。",
         "排期编制耗时从 6 个工作日降到 1 个工作日。"],
    ),
    (
        "把学生事务常见问题整理成一本 FAQ 手册，发给各学院。",
        "FAQ 手册还没开始弄",
        ["制单差错由 4 笔降至 0。",
         "两个学院本学期线上请假单 1043 单。",
         "讲师确认 2 人。"],
    ),
    (
        "启动困难学生绿色通道材料收集。",
        "继续推进困难学生绿色通道材料收集，9/2 前收齐。",
        ["8/26 10:00 前报送分院报到率。",
         "宿舍调整通知已发。",
         "排期规则文档更新至第 3 版。"],
    ),
    (
        "上线排期冲突自动检测功能。",
        "排期冲突自动检测暂缓，等厂商 10 月改版后再上线，由我与厂商对接。",
        ["热水系统改造方案已评审通过。",
         "受理群内操作咨询 64 次。",
         "覆盖新学期课程 2148 门。"],
    ),
    (
        "更新实验楼安全标识并做一次消防通道排查。",
        "更新实验楼安全标识完成，消防通道排查出 3 处占用并当日清理。",
        ["走访宿舍 6 间。",
         "参加评审 3 场。",
         "输出纪要 5 份。"],
    ),
    (
        "3 月第 2 周办完全校辅导员业务培训。",
        "培训到场 34/36 人，缺席 2 人已约补训，材料归档为部门标准件。",
        ["受理报修 237 单，涉及 11 栋宿舍楼。",
         "平均办结时长从 3.5 天压到 1.2 天。",
         "1 页操作指引已被 17 个学院自发沿用。"],
    ),
]


# 负样本：上期承诺、本期确实没提（只有干扰项）。用来验证规则不会把无匹配判成有下文
NO_MATCH = [
    ("把学生事务常见问题整理成一本 FAQ 手册，发给各学院。",
     ["宿舍调整通知已发，涉及 214 人。", "并发参数过低已调参，连续 2 日无复现。",
      "受理师生教务咨询 1204 人次。"]),
    ("更新实验楼安全标识并做一次消防通道排查。",
     ["两个学院本学期线上请假单 1043 单。", "排期编制耗时从 6 个工作日降到 1 个工作日。",
      "培训到场 34/36 人。"]),
    ("3 月第 2 周办完全校辅导员业务培训。",
     ["走访宿舍 6 间，参加评审 3 场。", "制单差错由 4 笔降至 0。",
      "排期规则文档更新至第 3 版。"]),
]


def best_two(promise: str, cands: list[str]) -> tuple[float, float, str]:
    scored = sorted(((similarity(promise, c), c) for c in cands), reverse=True)
    first = scored[0][0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    return first, second, scored[0][1]


NEAR_MISS = [
    ("推动机械学院开通线上请假审批流程。", "外国语学院已接入线上请假审批，办结 812 单（统计区间 3 月至 6 月）。"),
    ("修订学分认定与免休修课程对照表。", "完成学分认定办法修订，已发文执行。"),
    ("把 FAQ 手册发给 17 个学院。", "把重修通知发给 12 个学院，签收 12/12。"),
    ("完成实验楼安全标识更新并做一次消防通道排查。", "B 楼安全出口标识已更新并通过验收。"),
    ("建立学籍异动线上办理流程。", "学籍异动纸质表格已归档 411 份。"),
]


def evaluate(sweep: bool) -> int:
    words = load()
    pos_top1, pos_lead, neg_lead, near_leak = 0, [], [], []
    for promise, truth, distractors in CASES:
        first, second, picked = best_two(promise, [truth] + distractors)
        pos_top1 += (picked == truth)
        pos_lead.append((first, first - second))
    for promise, distractors in NO_MATCH:
        first, second, picked = best_two(promise, distractors)
        neg_lead.append((first, first - second))
    near_scores = []
    for promise, decoy in NEAR_MISS:
        near_scores.append(similarity(promise, decoy))
        if not conflict_reason(promise, decoy, words):
            near_leak.append((promise, decoy, near_scores[-1]))

    n = len(CASES)
    print(f"\n样本：{n} 条有下文 + {len(NO_MATCH)} 条完全没提 + {len(NEAR_MISS)} 条近邻诱饵")
    print(f"top-1 排序命中：{pos_top1}/{n} = {pos_top1 / n * 100:.0f}%")
    print(f"有下文：最低总分 {min(s for s, _ in pos_lead):.3f}"
          f"　最低领先幅度 {min(m for _, m in pos_lead):.3f}")
    print(f"完全没提：最高总分 {max(s for s, _ in neg_lead):.3f}"
          f"　最高领先幅度 {max(m for _, m in neg_lead):.3f}")
    print(f"近邻诱饵：分数 {min(near_scores):.3f}–{max(near_scores):.3f}，与正样本重叠"
          f" → 只能靠冲突判定拦，已拦 {len(NEAR_MISS) - len(near_leak)}/{len(NEAR_MISS)}")
    for p, d, s in near_leak:
        print(f"    漏网 {s:.2f}: {p[:18]} ↔ {d[:22]}")

    best_rule = None
    floor = 0.10
    while floor <= 0.60:
        margin = 0.0
        while margin <= 0.40:
            ok_pos = sum(1 for s, m in pos_lead if s >= floor and m >= margin)
            ok_neg = sum(1 for s, m in neg_lead if not (s >= floor and m >= margin))
            if ok_pos == len(pos_lead) and ok_neg == len(neg_lead):
                # 取最保守的一条：底线分最高，其次领先幅度最大
                if best_rule is None or (floor, margin) > best_rule:
                    best_rule = (floor, margin)
            margin += 0.02
        floor += 0.02

    from promise_reconcile import FLOOR, LEAD
    ship_pos = sum(1 for s, m in pos_lead if s >= FLOOR and m >= LEAD)
    ship_neg = sum(1 for s, m in neg_lead if s >= FLOOR and m >= LEAD)
    print(f"出厂参数 FLOOR={FLOOR} LEAD={LEAD}："
          f"有下文 {ship_pos}/{len(pos_lead)} 判对，完全没提误放行 {ship_neg}/{len(neg_lead)}")

    if best_rule is None:
        print("\n无解：分数+领先幅度分不开「有下文」与「完全没提」，需要改相似度算法。")
        return 1
    if near_leak:
        print("\n近邻诱饵有漏网：冲突判定失效，会被误判成已兑现。")
        return 1
    if ship_neg:
        print("\n出厂参数放行了本该判「没提」的样本：调 FLOOR/LEAD 后重跑本评测。")
        return 1

    print(f"\n最保守可分规则：总分 ≥ {best_rule[0]:.2f} 且领先次优 ≥ {best_rule[1]:.2f}；"
          f"近邻诱饵只能靠对象/文档类型冲突否决拦住")
    if sweep:
        for (s, mg), (promise, _, _) in zip(pos_lead, CASES):
            print(f"   {s:.3f} 领先 {mg:.3f}  {promise[:30]}")
    return 0


import wordpack


def main() -> int:
    wordpack.use_utf8_console()
    ap = argparse.ArgumentParser(description="对账器阈值评测")
    ap.add_argument("--sweep", action="store_true", help="打印每条样本的领先幅度明细")
    args = ap.parse_args()
    return evaluate(args.sweep)


if __name__ == "__main__":
    sys.exit(main())
