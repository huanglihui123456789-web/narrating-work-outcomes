#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能同步器：开发副本 → 运行副本，并验证一致性.

本技能存在两份是正常的：一份在你自己的目录里编辑，一份装在
~/.qwenworkcn/skills/ 下才会被真正加载。不正常的是两份悄悄分叉——
你改的和你用的不是同一份，而症状要很久以后才看得出来。

用法:
  python scripts/sync_skill.py --check                 # 只比对，有漂移则退出码 1
  python scripts/sync_skill.py                         # 开发副本 → 运行副本，并在目标处复跑校验
  python scripts/sync_skill.py --to <路径>             # 指定目标
  python scripts/sync_skill.py --prune                # 同时清掉目标里多出的文件（先备份，不直接删）

不改用户家目录以外的东西；不做不可恢复删除。
"""

from __future__ import annotations

import argparse
import datetime as dt
import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".git", ".idea"}


def src_root() -> Path:
    """本脚本所在技能目录 = 开发副本根。"""
    return Path(__file__).resolve().parent.parent


def dest_default() -> Path:
    name = src_root().name
    return Path.home() / ".qwenworkcn" / "skills" / name


def walk(root: Path) -> set[str]:
    out = set()
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (SKIP_DIRS & set(p.parts)):
            out.add(str(p.relative_to(root)).replace("\\", "/"))
    return out


def compare(a: Path, b: Path) -> tuple[list[str], list[str], list[str]]:
    """返回 (仅左边有, 仅右边有, 内容不同)。"""
    fa, fb = walk(a), walk(b)
    only_a = sorted(fa - fb)
    only_b = sorted(fb - fa)
    diff = [r for r in sorted(fa & fb)
            if not filecmp.cmp(str(a / r), str(b / r), shallow=False)]
    return only_a, only_b, diff


def report(only_src, only_dst, diff, src: Path, dst: Path) -> bool:
    same = not (only_src or only_dst or diff)
    print(f"开发副本 {src}\n运行副本 {dst}")
    if same:
        print("✓ 两份完全一致")
        return True
    for f in only_src:
        print(f"  仅开发副本有: {f}")
    for f in only_dst:
        print(f"  仅运行副本有: {f}")
    for f in diff:
        print(f"  内容不一致:   {f}")
    print("✗ 存在漂移：你改的可能不是你在用的那份")
    return False


import os
# 从任何工作目录、以任何方式启动都能找到同目录的 wordpack：
# 直接运行时 Python 会加 scripts/ 到 sys.path，但被 import 或以路径运行时不会
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import wordpack


def main() -> int:
    wordpack.use_utf8_console()
    ap = argparse.ArgumentParser(description="技能同步与漂移检测")
    ap.add_argument("--to", default="", help="目标目录，默认 ~/.qwenworkcn/skills/<技能名>")
    ap.add_argument("--check", action="store_true", help="只比对不写入")
    ap.add_argument("--prune", action="store_true",
                    help="同步时清掉目标里多出的文件（移动到备份目录，不删除）")
    args = ap.parse_args()

    src = src_root()
    dst = Path(args.to) if args.to else dest_default()
    if not dst.exists():
        print(f"目标不存在：{dst}\n先确认技能装在哪，或用 --to 指定。", file=sys.stderr)
        return 2

    only_src, only_dst, diff = compare(src, dst)
    if args.check:
        return 0 if report(only_src, only_dst, diff, src, dst) else 1
    if not (only_src or only_dst or diff):
        report([], [], [], src, dst)
        print("无需同步。")
        return 0

    for rel in only_src + diff:
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, target)
        print(f"覆盖 {rel}" if rel in diff else f"新增 {rel}")

    if only_dst:
        if args.prune:
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = dst.parent / f"{dst.name}.stale-{stamp}"
            for rel in only_dst:
                dest = backup / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dst / rel), str(dest))
                print(f"移走多余文件 {rel} → {dest}")
            print(f"多余文件已备份到 {backup}（未删除，可自行清理）")
        else:
            print("目标里有开发副本没有的文件，未处理。加 --prune 可把它们移到备份目录。")

    still = compare(src, dst)
    if any(still):
        report(*still, src, dst)
        return 1
    print("✓ 同步后两份一致")

    v = subprocess.run([sys.executable, "-B", str(dst / "scripts" / "validate_skill.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = (v.stdout or "").strip().split("\n")[-1] if v.stdout else v.stderr[:200]
    print(f"在运行副本里复跑校验：{tail}")
    return 0 if v.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
