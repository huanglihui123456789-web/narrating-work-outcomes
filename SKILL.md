---
name: narrating-work-outcomes
name_en: Work Outcome Narrator
name_zh: 职场成果叙事引擎
description: Turn scattered work logs, chat records, todo exports and raw notes into outcome-focused Chinese workplace documents - weekly/biweekly reports, monthly summaries, quarterly/semester/year-end reviews (shuzhi), performance self-assessments, probation summaries and promotion pitches. Ships with two stdlib scripts: an auditor that catches action-without-result sentences, missing numbers, fake precision, unstated metric calibers, unowned plans, leaked personal identifiers and per-genre structural rules (--style weekly/monthly/review/self-review/pitch), plus a reconciler that diffs last period's commitments against this period's text to expose dropped and repeatedly-slipping items. Use when the user asks to 写周报 / 双周报 / 月报 / 月度总结 / 季度述职 / 学期总结 / 年终总结 / 阶段小结 / 年度考核 / 民主评议 / 绩效自评 / KPI复盘 / OKR打分 / 转正总结 / 竞聘稿 / 汇报材料 / 给领导汇报, says 像流水账 / 说不清自己干了什么, or wants to check 上期承诺有没有兑现. Does not cover statutory official-document formats (GB/T 9704 公文), outbound marketing copy, or docx/pptx/xlsx file conversion.
description_en: Turn scattered work logs, chat records, todo exports and raw notes into outcome-focused Chinese workplace documents - weekly reports, monthly reports, quarterly reviews, performance self-assessments, probation summaries and promotion pitches. An auditor catches action-without-result sentences, missing numbers, fake precision, unstated calibers, unowned plans and per-genre structural rules; a reconciler diffs last period's commitments against this one. Use when the user asks to write a weekly/monthly report, quarterly review, self-assessment or promotion pitch, says their draft reads like a laundry list, or wants to check whether last period's promises were kept.
description_zh: 把零散的工作流水、聊天记录、待办导出、语音转文字转成"以结果为中心"的中文职场文书：周报、双周报、月报、季度述职、学期总结、年终总结、绩效自评、转正总结、竞聘稿。自带两个脚本：体检器专抓流水账句、缺数字、伪精确、缺口径、计划没责任人、正文漏了学号手机号，并按文体硬规则查缺件；闭环器把上期承诺和本期正文对账，抓出悄悄消失的承诺和连续两期没做成的事。当用户说"写周报""双周报""月度总结""述职""学期总结""年终总结""阶段小结""年度考核""民主评议""绩效自评""KPI复盘""OKR打分""转正总结""竞聘""汇报材料""给领导汇报"，抱怨"像流水账""干了很多但说不出来"，或想确认"上期答应的事这期怎么没提"时使用。
argument-hint: Paste raw work notes or attach a file, and say which document type you need and who will read it
argument-hint-en: Paste raw work notes or attach a file, and say which document type you need and who will read it
argument-hint-zh: 贴上零散工作记录或附上文件，并说明要写哪种文体、给谁看
user-invocable: true
---

# 职场成果叙事引擎

## 这个技能解决什么

普通人写工作汇报的真实困境不是"不会写字"，而是**做了三分，写成三分流水账，领导听成一分**。

本技能做三件事：把动作翻译成结果，把结果逼出口径，把口径配给正确的读者。并且用一个脚本把这三步变成可验证的检查，而不是靠感觉。

## 四条铁律

任何输出都必须遵守，优先级高于"写得好看"。

**1. 动作必须落到结果。** 用四要素公式改写：`动作 → 对象 → 结果 → 影响`。

> 推进了客户系统对接 → 客户系统对接完成上线，月结对账工时从 42 小时降到 6 小时

**2. 数字必须带口径。** 每个数字至少交代清"分子/分母 + 时间窗"中的一个缺失项，有对比就写明对比基准。孤零零的百分比一律不合格。

用"约 / 余 / 左右 / 以上"包装的估算**不算数字**。确实只能估的时候，写成"估算：数字 + 算法"，不要让它伪装成实测值。

> 效率提升 30% → 单人日均处理量从 12 单提到 16 单（7 月整月 vs 4 月整月口径）

**3. 零虚构。** 绝不编造数字、人名、部门、收益比例、完成时间。缺的信息写成 `{{待补：具体缺什么}}` 并集中列进《待补清单》。**宁可留空，不可填空话**——填了"大幅提升"，这份报告就废了。

**4. 不带第三方隐私。** 汇报是会被转发、截图、存档的东西，写进去的标识符收不回来。三类绝不进正文：

- **第三方真名**——改成角色："某学院联络人""参与评审的 6 位老师"，而不是"张主任、李老师"
- **可定位的编号**——学号、手机号、身份证、工号、薪资数字。要说明进度就写人数与事项
- **个案化的困境描述**——"5 名申请绿色通道的学生，1 名材料待补"可以；带姓名加低保/病情/家庭情况的个案不行，那属于另一份内部台账，不该出现在汇报里

体检器会把前两类当**阻断项**（有它们就不算可交付），第三类只提示。`--redact` 能一键掩码前两类。

## 触发与边界

**触发**：用户要写周报、**双周报**、月报、**月度总结**、季度/学期/**年终**述职、**学期总结**、**阶段小结**、**年度考核**、**民主评议**、绩效自评、KPI/OKR 复盘与打分、转正总结、竞聘演讲稿、项目复盘汇报、**汇报材料**、**给领导/老板汇报**、向上申请资源、学生情况汇总、家长沟通记录；**或拿着稿子问"这个能直接发吗""里面有别人名字要不要紧""帮我脱敏"**；或抱怨"像流水账""不知道怎么体现价值"；或丢来一堆零散记录说"帮我整理成汇报"。

**不适用，请转交**：

- 要 `.docx` / `.pptx` / `.xlsx` 成品文件 → 用 `docx` / `pptx` / `xlsx` 技能（本技能只产出可直接粘贴的正文）
- 对外发布的公众号、小红书、抖音文案 → 用 `musea-smart-writer`
- 法定公文（通知、请示、报告、函、纪要，须符合 GB/T 9704 格式）→ 不在本技能范围，本技能只管"工作汇报类"文体
- 纯会议逐字稿清洗 → 不适用；但"纪要转成决议 + 责任人 + 跟进项"属于本技能范围

## 工作流

复制这份清单跟踪进度：

```
- [ ] Step 1 定位：文体 + 读者 + 篇幅
- [ ] Step 2 采集：从素材抽"结果候选"
- [ ] Step 3 体检：gaps 模式 → 一次性反问 ≤5 题
- [ ] Step 4 组装：按文体选框架
- [ ] Step 5 承诺闭环：有上期就核对，没有就跳过
- [ ] Step 6 终稿体检：final 模式，不达标回改（≤2 轮）
- [ ] Step 7 输出：成稿 + 待补清单 + 承诺核对表
```

### Step 1 定位

必须先确认**给谁看**和**多长**。用户没说就别猜着写，直接用该文体默认值（见 [audience-matrix.md](audience-matrix.md)），并在交付时注明用了默认值。

定了文体就在后续两次体检里带上 `--style`（weekly / monthly / review / self-review / pitch），脚本会自动套用该文体的字数上限和结构硬规则——缺必备小节属于硬性不合格，不是建议。

### Step 2 采集结果候选

素材通常是碎片：聊天截图、待办导出、git/系统日志、Excel 台账、语音转文字。逐条判断每句话属于哪一类：

| 类型 | 处理 |
|---|---|
| 有动作有结果有数 | 直接进正文，最高优先级 |
| 有动作有结果没数 | 进正文，数字位标 `{{待补}}` |
| 只有动作（"参与了""推进了"） | 必须问出结果，问不出则降级为一句背景 |
| 纯过程描述（"开了个会"） | 删掉，除非会议本身产生了决议 |

### Step 3 体检 + 反问（不要跳过）

```bash
python scripts/report_audit.py <素材或初稿.md> --mode gaps [--top 5]
```

输出分两段。**「先问这几条」**只放必须由用户回答的事（状态未核实、没产出、没口径、没责任人）；**「其余 N 处可自查」**收着 agent 自己能改的（残留待办框、套话、篇幅、隐私、文体缺件）——把后者塞进提问，只会挤掉真正该问的那几句。

三条已固化的规则：

- **同一句合成一问**。一句烂话常同时踩中"没数字 + 太空泛 + 没产出"，拆开问会白占三个名额。
- **同类最多占 2 格**。状态未核实权重最高，不设上限它会霸屏，把"这季度到底少花了多少钱"这种值钱问题挤到自查区。
- **素材首行的标题不当工作项**。"Q3 随手记（没整理）"里的"整理"在动词表里，会被追问"这件事的产出物是什么"。

gaps 模式按口语素材调校，"弄完""催了两次""我一个个教的"这类写法都能识别；它会优先逼你去核实状态，因为素材阶段最致命的问题不是缺数字，而是**你自己都不知道这件事成没成**。

脚本按类型排好了序，但**排序不等于问法**。有一条脚本永远排不出来：本期有没有"没做成、但避免了损失"的事（延期、砍需求、拦截故障）——它没有产出物、没有数字，在检查器眼里和流水账一样。所以拿到清单后按这个口径问，最多 5 题：

1. 影响最大那条结果缺的数字（"这次改版覆盖了多少用户？"）
2. 有数字但没口径的（"这个 30% 是跟谁比的？哪个时间窗？"）
3. 报了风险但没责任人/下一步的
4. **有没有"没做成但拦住了"的事**——这类最容易漏，却最能体现判断力
5. 下期计划的验收点

用户答"不知道/没统计"→ 用 `{{待补}}` 占位，或改用替代量化（见 [frameworks.md](frameworks.md) 的"无数据量化五法"），**不要**用"明显提升""一定程度上"糊过去。

### Step 4 组装

按文体选框架，公式和样例见 [frameworks.md](frameworks.md)。通用原则：**结果前置**，本期最重要的一条占最多字，别按时间顺序平铺。

述职（review）与竞聘（pitch）里的"判断规则/教训"句（STAR-L 的 L）不带数字是合法的，体检器在这两种文体下豁免它；其他文体不豁免——别拿这条当免检金牌往周报里塞感想。

### Step 5 上期承诺闭环

汇报信用不取决于本期写了多少数字，而取决于**上期答应的事这期有没有交代**。悄悄消失的承诺比流水账更伤信任，也正是肉眼最容易漏的。用户能提供上一期就跑这一步：

```bash
python scripts/promise_reconcile.py --prev <上一期.md> --current <本期.md>
```

三个实现事实值得知道，否则你会误信它的结论：

- **承诺有两个来源**：计划小节的条目，以及正文里的前向语句（"下季度我打算把 X 定下来，同时启动 Y"）。只认小节会整条漏掉，漏掉之后它照样输出"全部有据可查"——那是最坏的一种错。
- **判定看排序与领先幅度，不看绝对分数**：真实匹配的分值可以低到 0.17，把绝对阈值压到那儿会放行大量垃圾。参数由 `scripts/eval_thresholds.py` 在带标注样本上标定（top-1 命中 10/10，正负样本可完全分开）。**改相似度算法后必须复跑该评测**。
- **分数认得出"话题相关"，认不出"是不是同一件具名事项"**：机械学院 vs 外国语学院、对照表 vs 办法、手册 vs 通知——这类近邻诱饵实测拿 0.29–0.65，比合法正样本最低分 0.167 还高。所以有一道**对象／文档类型冲突否决**：命中冲突一律降级为存疑，绝不自称已兑现。存疑多于零时，结论行会说"没查清"而不是"全部有据可查"。

每条上期承诺只给一个结论，五类处置各不相同（小标题同样被当作证据扫描，把交付结论写在标题里不算漏交代）：

| 结论 | 处置 |
|---|---|
| 已兑现 | 不用动；若标注「余量仍在计划」，把那点尾巴的时间也写上 |
| 存疑 | 相似度不够，机器不替人认。人工确认是否同一件事，确认后提到结果小节 |
| **有交代未完成** | 提到了但没做完（推迟/暂缓/还没开始）。补一个明确时间点，或正式写「取消 + 原因」 |
| **未提及** | 本期完全没这句话。必须补交代——这一档最伤信用 |
| **连续顺延** | 上期写进计划、本期还躺在计划里且没有更强的完成证据。要么给死线要么砍掉 |

没提供上期时跳过这步，但要提醒一句：下期开始带上上期原文，就能做闭环核对。

### Step 6 终稿体检（反馈闭环）

```bash
python scripts/report_audit.py <成稿.md> --mode final --style <文体> [--word-limit <目标字数>]
```

- **得分 ≥ 75、流水账率 < 20%、且未决问题 0 条** → 可交付
- **隐私阻断项不为 0 时先处理它**（改写或 `--redact`），再谈分数——发出去的身份证号收不回来，这不是文风问题
- 未决问题不为 0 时，哪怕得分 100 也不算过——超篇幅、口径缺失这类问题不会拉低分数，但会让读者卡住
- **出现「文体缺件」直接不合格**，它不是文风问题而是结构残缺
- 否则回到 Step 3，针对扣分项补数据或改写，最多 2 轮
- 两轮后仍卡在同一个缺失数据 → 停止追问，把它明确列进《待补清单》，照常交付并告诉用户"补上这个数，这段就成立"

### Step 7 输出

产出成稿正文（Markdown，可直接粘贴进 OA/邮件/飞书钉钉），正文之外附两样东西：《待补清单》标注每条补上后能替换哪一句；《承诺核对表》（若做过 Step 5）让用户一眼看到上期欠了什么。

## 常见误判与修正

| 症状 | 处理 |
|---|---|
| "我这份工作没数据"（行政、教务、客服、运维、后勤） | 用替代量化五法：计数、时间、差错、范围、反馈。见 frameworks.md |
| 只会写"约 120 人""300 余人" | 伪精确。给准确数并标计数来源；确实只能估，写成"估算：数字 + 算法" |
| "效果良好""反响热烈""反馈不错" | 空泛评价。换成可核对状态：多少人、满意度几个数、被谁引用、退回几次 |
| "零事故""未发生问题"却没说多久 | 负向指标必须带时间窗：连续 N 天 / 本月 / 自 X 月起 |
| 坏消息不敢写 | 四件套：事实 → 影响 → 已采取 → 需要谁决策。只报事实不带方案＝甩锅 |
| 团队成果写成个人成果 | 措辞分级：主导 / 牵头 / 参与 / 支持，越界一次就会被同事和领导同时扣分 |
| AI 套话味重（赋能、抓手、闭环、沉淀、聚焦） | final 模式按命中次数扣分，替换为具体动词 + 宾语 |
| 待办框 `[ ]` 还留在正文里 | 成稿不该有勾选符号。已完成的改写成结果句；未完成的别放结果小节 |
| 只说"翻倍""节省 20 万" | 比例和收益都要有基数：从多少到多少、统计区间哪一段 |
| 一句里并列一堆活动（开会 5 次，沟通 12 人，处理邮件 30 封…） | 活动堆砌。逗号串起的长句会被当成一句而蒙混过关，现在按子句配对：并列 ≥3 个动作且零产出即拦下。要么每项补结果，要么合并成一句真结论 |
| 上期说过的事这期没下文 | 走 Step 5 承诺闭环，用 promise_reconcile.py 对账，别靠记忆 |
| 正文里有同事真名、学号、手机号、薪资 | 隐私外泄风险。标识符是阻断项；改成角色化说法，或 `--redact` 出脱敏副本 |
| 自评写"超出预期"，但通篇只有"按期完成" | 等级与证据不符。补超额证据（提前几天、从多少降到多少、被谁沿用），或把等级降下来——二选一，别指望评委替你选 |
| 篇幅超标 | 砍过程描述和影响分析，保留结果行 |

final 模式共检查十七项：状态未核实、流水账率、活动堆砌、量化密度、模糊量词、伪精确、空泛评价、负向指标缺时间窗、比例无基数、收益缺口径、残留待办框、未完成混进成果、风险无下文、计划无责任/时限、套话密度、隐私外泄风险、等级与证据不符；外加篇幅与文体硬规则（`--style`）。

**等级与证据不符只在 `--style self-review` 下启用**，且按维度小节独立判定——不能用别的维度的硬证据替本维度背书。三种都算不符：称"超出预期"却没有超额证据（虚高）、称"达成"而同段出现缺口/延期（隐瞒，最伤信任）、称"未达成"却有超额证据（低报，校准会上换不到同情只会少拿）。

### 检查的固有上限

这些检查绝大多数是词表型的，**换生僻词就能绕过**（"本周飞了 5 趟校区，跑了 3 个部门"不会触发活动堆砌）。不要为了跑分去把阈值往下压：`STACK_MIN` 降到 2 就能抓住它，但会误伤 frameworks.md 亲手推荐的计数法（"受理报修 237 单，走访宿舍 6 间"正好两个活动）。**误报比漏报更贵**——用户会照着误报把正确的写法改坏。

评测里有一条"局限-生僻动词绕过"按**预期不命中**登记：哪天它命中了，评测会失败，提醒你把它改回正常用例，而不是让这条限制悄悄失效。

## 参考文件

- [audience-matrix.md](audience-matrix.md) — 五种文体的读者、关心点、篇幅、结构、禁忌、开头模板
- [frameworks.md](frameworks.md) — 改写公式、6 组前后对照、无数据量化五法、坏消息与争功措辞规范
- [wordlists.json](wordlists.json) — 唯一词表来源；改词、加行业档都在这里，不在 .py 里

三组"原稿 → 成稿"对照，兼作体检脚本的回归用例：

- [examples/draft-lowvalue.md](examples/draft-lowvalue.md) → [examples/draft-deliverable.md](examples/draft-deliverable.md)：企业职场
- [examples/draft-school-admin.md](examples/draft-school-admin.md) → [examples/draft-school-admin-rewritten.md](examples/draft-school-admin-rewritten.md)：学校行政
- [examples/draft-raw-notes.md](examples/draft-raw-notes.md) → [examples/draft-raw-notes-report.md](examples/draft-raw-notes-report.md)：未整理的微信/待办混合记录

**问题稿**，各自锁死一个真实翻过车的分支：

- [examples/draft-inflated.md](examples/draft-inflated.md)：全是"约 120 人 / 300 余人 / 效果良好 / 未发生安全事故"的句子——它曾拿 100 分可交付
- [examples/draft-quantifier-traps.md](examples/draft-quantifier-traps.md)：中文量词与名词性动词陷阱（5 项整改、12 节课、3 起投诉、"学生反馈不错"）
- [examples/draft-activity-stack.md](examples/draft-activity-stack.md)：活动堆砌，一句逗号长句躲过全部检查，也曾拿 100 分可交付

反证夹具，防止检查过头：

- [examples/counting-method-ok.md](examples/counting-method-ok.md)：frameworks.md 推荐的"计数法"写法（受理报修 237 单），必须仍然可交付

对账夹具三对：

- [examples/promise-prev.md](examples/promise-prev.md) → [examples/promise-current.md](examples/promise-current.md)
- [examples/near-prev.md](examples/near-prev.md) → [examples/near-current.md](examples/near-current.md)：**全是诱饵**的本期稿——每条都像兑现，其实对象或文体都不是那件事，五条必须一律判存疑
- [examples/draft-pii.md](examples/draft-pii.md)：含学号/手机/薪资/真名的稿子，必须挡住交付，且 `--redact` 后阻断项归零、原文件不被改写

改词表或算法后跑一条命令复核全部结构与行为：

```bash
python scripts/validate_skill.py
```

它除了查 frontmatter、双语齐全、行数、引用完整性，还会实跑十一份稿件的不变量（成稿须未决 0 条且流水账率 0%；问题稿须达到各自门槛且不得判可交付），另有四组单独断言：承诺闭环五档精确计数、`--style` 硬规则生效、行业词表差分成立、隐私脱敏闭环（含"原文件不得被改写"）。最后强制两个评测达标：对账阈值的正负样本可分性、检查项双向评测（23 条样本）的精确率与召回率必须都是 100%。盯的是不变量不是分数——分数会随词表增删漂移，不变量不会。

## 脚本

```bash
# 单份稿件体检（gaps=写之前找空位，final=写之后评分）
python scripts/report_audit.py <文件.md> --mode gaps            # 默认一次给 5 问
python scripts/report_audit.py <文件.md> --mode gaps --top 8    # 素材很乱时放宽提问数
python scripts/report_audit.py <文件.md> --mode final --style weekly
python scripts/report_audit.py <文件.md> --mode final --style review --word-limit 2500
python scripts/report_audit.py <文件.md> --mode gaps --json      # 需要程序化处理时

# 两期对账：上期承诺 vs 本期正文
python scripts/promise_reconcile.py --prev <上一期.md> --current <本期.md>

# 换行业词表档（体检器与对账器共用同一份），或用单位自己的词表
python scripts/report_audit.py 周报.md --mode final --profile school
python scripts/report_audit.py 周报.md --mode final --words ./我的词表.json

# 出脱敏副本（原文件不动）：掩码手机/身份证/学号/薪资/称谓姓名
python scripts/report_audit.py 述职稿.md --redact

# 维护件（不日常调用）：改算法或词表后必须复跑
python scripts/eval_thresholds.py     # 对账阈值：正负样本可分性
python scripts/eval_checks.py         # 体检检查项：双向精确率/召回率
python scripts/validate_skill.py      # 结构 + 行为 + 词表 + 隐私，一把跑完
python scripts/sync_skill.py --check  # 开发副本与运行副本有没有分叉
python scripts/sync_skill.py          # 同步过去并在目标处复跑校验
```

**两份副本为什么会分叉**：编辑发生在你的目录，加载却发生在 `~/.qwenworkcn/skills/`。改完不同步，症状要过很久才显形——你会发现"我明明改了，它怎么还这么说"。所以**以运行副本为准出成果，以开发副本做修改，每次改完跑一次 `sync_skill.py`**。同步器不会静默删文件：目标里多出来的东西会先备份再移走，需要你显式加 `--prune`。

体检器只管一份稿件，闭环器只管两期对账，两者都不联网。只依赖标准库，Python 3.10+。

## 自定义词表

`wordlists.json` 是**唯一**词表来源，代码里不内置中文词条，也**没有静默回退**——文件缺失或写坏会直接报错退出。这是刻意的：一旦留一份"代码里的备用词表"，两份定义迟早对不上，而那时检查结论会静默变错，比崩溃难查得多。

内置四档：`office`（默认）、`school`（教师/教务/辅导员）、`factory`（车间/品质/设备）、`retail`（门店/餐饮）。用法是**只写差异**：

```json
{
  "profiles": {
    "我的单位": {
      "add": { "ACTIVITY_VERBS": ["巡棚", "起苗"], "RISK_SIGNALS": ["药害"] },
      "add_units": ["亩", "茬"],
      "remove": { "CLICHE": ["沉淀"] }
    }
  }
}
```

单位自己的词表建议另存一个文件用 `--words` 传入，不要改技能自带的那份，否则升级时会互相覆盖。

**两类东西不要放进词表**：一是阈值（`STACK_MIN`、`FLOOR/LEAD/TRACE`、评分权重），它们由两个评测标定，改了必须重跑 `eval_checks.py` 与 `eval_thresholds.py`；二是往 `CN_NUM_UNITS` 里加"步""半"这类词——中文没有词边界，"进一步""下一步""半天"会被误咬成数量，这个坑实测踩过，校验器里有断言守着。

词表有契约，**坏词表会被当场拒绝**而不是静默退化：必需词组缺失、`DOC_TYPE_FAMILIES` 出现空族、中文量词混进"步/半"，都会以退出码 2 报出具体键名。这么设计是因为真出过事故——一个键改了名，加载器按新名取不到值，词表静默变空，检查项从此不再响，而所有测试看起来还是绿的。

## 输出语言

正文默认中文简体。禁止把本技能内部术语（"流水账率""量化密度""口径缺失""待补条目"）写进用户要交给领导的正文——体检结论只出现在附页和对话里。
