# -*- coding: utf-8 -*-
"""结构校验器：把 create-skill 的 Phase 4 清单变成可执行检查。"""
import re, os, sys, json, subprocess, tempfile
import os
# 从任何工作目录、以任何方式启动都能找到同目录的 wordpack：
# 直接运行时 Python 会加 scripts/ 到 sys.path，但被 import 或以路径运行时不会
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import wordpack

wordpack.use_utf8_console()   # Windows 控制台默认 GBK，打印中文断言会抛 UnicodeEncodeError
ok = True
BACKSLASH = chr(92)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def chk(cond, msg):
    global ok
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        ok = False

raw = open(os.path.join(ROOT, 'SKILL.md'), encoding='utf8').read()
m = re.match(r'^---\n(.*?)\n---\n(.*)$', raw, re.S)
chk(bool(m), "SKILL.md 有 YAML frontmatter")
fm, body = m.group(1), m.group(2)

def field(k):
    mm = re.search(rf'^{re.escape(k)}:\s*(.*)$', fm, re.M)
    return mm.group(1).strip() if mm else ''

name = field('name')
chk(re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+){0,9}', name) is not None, f"name 为 ASCII kebab-case: {name!r}")
chk(len(name) <= 64, "name 长度 <=64")
for k in ['name_en', 'name_zh', 'description', 'description_en', 'description_zh',
          'argument-hint', 'argument-hint-en', 'argument-hint-zh', 'user-invocable']:
    chk(bool(field(k)), f"{k} 非空")
chk(len(field('description')) <= 1024, f"description 长度 {len(field('description'))} <=1024")
chk(field('user-invocable') == 'true', "user-invocable: true")
chk(field('description').strip()[0].isascii(), "description 兼容默认为英文")

lines = raw.count('\n') + 1
chk(lines < 500, f"SKILL.md {lines} 行 <500")
chk(BACKSLASH not in body, "正文无 Windows 反斜杠路径")
for pat in ['待补', '口径', '零虚构', '流水账']:
    chk(pat in body, f"核心概念在正文出现: {pat}")

refs = sorted(set(re.findall(r'\]\(([\w\-./]+?\.(?:md|py|yaml))\)', body)))
for r in refs:
    chk(os.path.exists(os.path.join(ROOT, r)), f"引用文件存在: {r}")
chk(all('/' in r or os.path.dirname(r) == '' for r in refs), "文件引用均为相对路径且一级深度")

try:
    import yaml
except ImportError:
    yaml = None


if yaml is None:
    # 裸环境没有 PyYAML：跳过 metadata 检查并说明原因，其余 130+ 项照常跑。
    # 曾尝试写迷你 YAML 子集解析器，结果连主流的「- id: 与 title: 同级」都对不上
    # ——自造解析器比它想解决的问题更不可靠，删掉。
    print("SKIP  metadata 检查需要 PyYAML，本项跳过（其余检查不受影响；pip install pyyaml 可开启）")
    ex = []
else:
    d = yaml.safe_load(open(os.path.join(ROOT, '.skill-metadata.yaml'), encoding='utf8'))
    ex = d['examples']
    chk(len(ex) >= 4, f"examples 数量 {len(ex)} >=4（每个主要能力一条）")
for e in ex:
    for k in ['id', 'title', 'description', 'prompt']:
        chk(k in e, f"example {e.get('id')} 含字段 {k}")
    for k in ['title', 'description', 'prompt']:
        v = e[k]
        chk(isinstance(v, dict) and v.get('zh') and v.get('en'), f"{e['id']}.{k} 中英齐全")
    chk(re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', e['id']) is not None, f"id kebab-case: {e['id']}")
    ph = re.findall(r'\{\{([^}]*)\}\}', e['prompt']['zh'])
    chk(len(ph) >= 1, f"{e['id']} 有 {len(ph)} 个用户填写占位符")

# ---------- 行为回归：三类不变量 ----------
A = os.path.join(ROOT, 'scripts', 'report_audit.py')
P = os.path.join(ROOT, 'scripts', 'promise_reconcile.py')
GOOD = {'draft-deliverable.md', 'draft-school-admin-rewritten.md', 'draft-raw-notes-report.md',
        'counting-method-ok.md'}
NOTDELIVER = {'draft-inflated.md', 'draft-quantifier-traps.md', 'draft-lowvalue.md',
              'draft-school-admin.md', 'draft-raw-notes.md', 'draft-activity-stack.md',
              'draft-activity-stack-verbs.md'}


def run(cmd):
    """Windows 管道默认 GBK，必须显式 utf-8，否则中文解析不出来。"""
    return subprocess.run([sys.executable, '-B'] + cmd, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', cwd=ROOT)


MIN_ISSUES = {'draft-activity-stack.md': 1,        # 两种措辞的定向探针，各 1 句即达标
              'draft-activity-stack-verbs.md': 1}


def min_issues(name):
    return MIN_ISSUES.get(name, 3)


for name in sorted(GOOD | NOTDELIVER):
    path = os.path.join(ROOT, 'examples', name)
    if not os.path.exists(path):
        chk(False, f"回归用例缺失: {name}")
        continue
    r = run([A, path, '--mode', 'final', '--word-limit', '500'])
    mm = re.search(r'得分：(\d+) / 100，未决问题 (\d+) 条 —— (\S+?)\*', r.stdout)
    if not mm:
        chk(False, f"{name} 解析失败 rc={r.returncode} err={r.stderr[-200:]}")
        continue
    sc, it, verdict = int(mm.group(1)), int(mm.group(2)), mm.group(3)
    rate = float(re.search(r'流水账率（[^）]*）：([\d.]+)%', r.stdout).group(1))
    if name in GOOD:
        chk(it == 0 and rate == 0.0 and verdict == '可交付',
            f"成稿不变量 {name}（{sc}分 未决{it} 流水账{rate}%）")
    else:
        need = min_issues(name)
        chk(it >= need and verdict != '可交付',
            f"问题稿不变量 {name}（{sc}分 未决{it}≥{need}）")

pr = run([P, '--prev', os.path.join(ROOT, 'examples/promise-prev.md'),
          '--current', os.path.join(ROOT, 'examples/promise-current.md'), '--json'])
try:
    j = json.loads(pr.stdout)
    got = {k: len(j[k]) for k in ('settled', 'deferred', 'doubtful', 'missing', 'rolled')}
    want = {'settled': 2, 'deferred': 1, 'doubtful': 0, 'missing': 1, 'rolled': 1}
    chk(got == want, f"承诺闭环五档计数 {got}（期望 {want}）")
except Exception as e:
    chk(False, f"承诺闭环回归无法解析：{e}")

nm = run([P, '--prev', os.path.join(ROOT, 'examples/near-prev.md'),
          '--current', os.path.join(ROOT, 'examples/near-current.md'), '--json'])
try:
    jn = json.loads(nm.stdout)
    got_nm = {k: len(jn[k]) for k in ('settled', 'deferred', 'doubtful', 'missing', 'rolled')}
    chk(got_nm['settled'] == 0 and got_nm['doubtful'] == 5,
        f"近邻负样本：诱饵全被拦下，不得判已兑现 {got_nm}")
except Exception as e:
    chk(False, f"近邻负样本回归无法解析：{e}")
nm_txt = run([P, '--prev', os.path.join(ROOT, 'examples/near-prev.md'),
              '--current', os.path.join(ROOT, 'examples/near-current.md')])
chk('全部有据可查' not in nm_txt.stdout, "结论行不得在没查清时自称'全部有据可查'")

ev = run([os.path.join(ROOT, 'scripts/eval_thresholds.py')])
chk(ev.returncode == 0, "阈值评测：正负样本仍可完全分开（改相似度后必须复跑）")

ck = run([os.path.join(ROOT, 'scripts/eval_checks.py')])
mm = re.search(r'精确率 ([\d.]+)%　召回率 ([\d.]+)%', ck.stdout)
bad = "、".join(re.findall(r'FAIL\s+(\S+)', ck.stdout))
chk(ck.returncode == 0 and mm and float(mm.group(1)) == 100.0 and float(mm.group(2)) == 100.0,
    "检查项双向评测 "
    + (f"精确{mm.group(1)}% 召回{mm.group(2)}%" if mm else "无法解析")
    + ("" if ck.returncode == 0 else f" → 待修：{bad}"))

# ---------- 词表外置 ----------
import json as _json
WL = os.path.join(ROOT, 'wordlists.json')
chk(os.path.exists(WL), "wordlists.json 存在")
try:
    data = _json.loads(open(WL, encoding="utf8").read())
    base = data["base"]
    profs = data.get("profiles", {})
    chk({"office", "school", "factory", "retail"} <= set(profs), f"四个行业词表档齐全：{sorted(profs)}")

    # 契约必须被"违反一次"才算数：静态扫 JSON 挡不住键改名后静默变空词表
    def _bad_pack(name, mutate):
        import json as _j
        d = _j.loads(open(WL, encoding="utf8").read())
        mutate(d["base"])
        fp = os.path.join(tempfile.mkdtemp(), name)
        open(fp, "w", encoding="utf8").write(_j.dumps(d, ensure_ascii=False))
        return run([A, os.path.join(ROOT, "examples/draft-lowvalue.md"),
                    "--mode", "final", "--words", fp])

    r1 = _bad_pack("missing.json", lambda b: b.pop("ACTIVITY_VERBS", None) or b.update(ACTIVITY_VERBS=[]))
    chk(r1.returncode == 2 and "ACTIVITY_VERBS" in (r1.stderr + r1.stdout),
        "坏词表被拒：缺必需词条组时硬报错，不静默退化")
    r2 = _bad_pack("banned.json", lambda b: b.update(CN_NUM_UNITS=b["CN_NUM_UNITS"] + ["步"]))
    chk(r2.returncode == 2 and "步" in (r2.stderr + r2.stdout),
        "坏词表被拒：中文量词混进「步」会让「进一步」误判成数量")
except Exception as e:
    chk(False, f"wordlists.json 解析失败：{e}")

sp = os.path.join(ROOT, "examples/draft-school-profile.md")
a_base = run([A, sp, "--mode", "final"])
a_sch = run([A, sp, "--mode", "final", "--profile", "school"])
chk("[活动堆砌]" not in a_base.stdout and "可交付" in a_base.stdout,
    "base 档：不认教师动词，不误伤")
chk("[活动堆砌]" in a_sch.stdout and "需返工" in a_sch.stdout, "school 档：监考/阅卷/查寝 堆砌被抓出")
bad = run([A, sp, "--mode", "final", "--words", os.path.join(ROOT, "no-such.json")])
chk(bad.returncode == 2 and "词表" in (bad.stderr + bad.stdout), "词表文件缺失时硬报错，不静默回退")

g = run([A, os.path.join(ROOT, "examples/draft-raw-notes.md"), "--mode", "gaps", "--top", "5"])
ask_block = g.stdout.split("先问这几条")[-1].split("## 其余")[0] if "先问这几条" in g.stdout else ""
ask_lines = re.findall(r"^\d+\. \[", ask_block, re.M)
types_asked = re.findall(r"^\d+\. \[([^\]（]+)", ask_block, re.M)
tally = {t: types_asked.count(t) for t in set(types_asked)}
chk(len(ask_lines) == 5, f"gaps 一次只给 5 问（实得 {len(ask_lines)}）")
chk(all(v <= 2 for v in tally.values()), f"同类问题不霸屏 {tally}")
chk("随手记" not in ask_block and "随手记" not in g.stdout.split("## 其余")[-1],
    "素材标题行不当工作项提问")
chk("## 其余" in g.stdout, "被挤出的问题落到自查区，不丢失")

# ---------- 隐私脱敏闭环 ----------
import shutil
pii_src = os.path.join(ROOT, 'examples/draft-pii.md')
if os.path.exists(pii_src):
    before = open(pii_src, encoding='utf8').read()
    with tempfile.TemporaryDirectory() as td:
        work = os.path.join(td, 'draft-pii.md')
        shutil.copy(pii_src, work)
        blocked = run([A, work, '--mode', 'final'])
        chk('[隐私外泄风险]' in blocked.stdout and '可交付' not in blocked.stdout,
            "PII 夹具：含标识符时必须挡住交付")
        rd = run([A, work, '--redact'])
        after = run([A, os.path.join(td, 'draft-pii-脱敏.md'), '--mode', 'final'])
        chk(rd.returncode == 0 and '已脱敏' in rd.stdout and '阻断级 0 项' in after.stdout,
            "PII 夹具：--redact 副本阻断项归零")
        chk(open(pii_src, encoding='utf8').read() == before, "PII 夹具：原文件未被改写")
else:
    chk(False, "缺少隐私回归夹具 examples/draft-pii.md")

st = run([A, os.path.join(ROOT, 'examples/draft-deliverable.md'), '--mode', 'final', '--style', 'review'])
chk('文体缺件' in st.stdout, "--style review 能抓到述职缺「不足与改进」")

# ---------- 控制台编码兜底 ----------
# 教训：sync_skill 在 GBK 控制台打印 ✓/✗ 直接抛 UnicodeEncodeError，
# 而此前每次测试都先 export PYTHONIOENCODING=utf-8，把问题一直遮着。
for name in sorted(os.listdir(os.path.join(ROOT, 'scripts'))):
    if not name.endswith('.py') or name == 'wordpack.py':
        continue
    src = open(os.path.join(ROOT, 'scripts', name), encoding='utf8').read()
    if 'argparse' not in src:
        continue          # 非入口脚本
    chk('use_utf8_console' in src or 'stdout.buffer' in src,
        f"{name} 自带输出编码兜底（不依赖调用方设 PYTHONIOENCODING）")

print("\n结果:", "全部通过" if ok else "存在失败项")
sys.exit(0 if ok else 1)
