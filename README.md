# 职场成果叙事引擎（narrating-work-outcomes）

把零散、口语、流水账式的工作记录，改写成**领导挑不出毛病**的中文职场文书：周报、双周报、月报、季度/学期/年终述职、绩效自评、转正总结、竞聘稿。

它不替你润色文字，而是**逼你把没说清的事补出来**。

## 为什么是脚本，不是提示词

汇报质量的判据是"可核对性"，靠模型自觉会静默放水——一份全是形容词的稿子照样能被夸"写得不错"。所以核心检查写成了两个只依赖标准库的 Python 脚本，结论可复现、可回归。

四条铁律，优先级高于"写得好看"：

1. **动作必须落到结果** —— `动作 → 对象 → 结果 → 影响`，追到说不出"所以呢"为止
2. **数字必须带口径** —— 分子/分母、时间窗、对比基准；"约/余/左右"包装的估算**不算数字**
3. **零虚构** —— 绝不编造数字、人名、收益。缺的写 `{{待补：具体缺什么}}`，宁可留空不可填空话
4. **不带第三方隐私** —— 同事真名、学号、手机号、薪资不进正文；汇报会被转发和存档，写进去收不回来

## 两个脚本

```bash
# 体检器：写之前找空位，写之后评分（17 项检查）
python scripts/report_audit.py 素材.md --mode gaps --profile school
python scripts/report_audit.py 成稿.md --mode final --style review

# 出脱敏副本（不改原文件）
python scripts/report_audit.py 述职稿.md --redact

# 闭环器：上期承诺 vs 本期正文，逐条给五档结论
python scripts/promise_reconcile.py --prev 上期.md --current 本期.md
```

`gaps` 输出分两段：「先问这几条」只放必须由你回答的事，「其余可自查」收着能自己改的——同一句合成一问，同类最多占两格，素材标题和"我写不出来"这类元抱怨不占提问名额。

`final` 的交付门槛是**得分 ≥75、流水账率 <20%、未决问题 0 条**。分数够但还挂着问题不算过。

## 承诺对账为什么值得单独做

汇报信用不取决于本期写了多少数字，而取决于**上期答应的事这期有没有交代**。悄悄消失的承诺最容易在述职现场被问住，也是人眼最难发现的。

每条上期承诺只给一个结论：已兑现 / 有交代未完成 / 存疑 / 未提及 / 连续顺延。判定用**排序 + 领先幅度**，不用绝对分数（真实匹配的分值可低至 0.167，把阈值压到那儿会放行大量垃圾）；再叠加**对象与文档类型冲突否决**——"机械学院 vs 外国语学院""对照表 vs 办法"这类近邻诱饵实测拿 0.29–0.65，比真匹配还高，只有内容冲突能拦住。

## 行业词表

`wordlists.json` 是**唯一词表来源**，代码不内置中文词条，也没有静默回退——文件损坏会当场报错而不是悄悄降级。内置 `office` / `school` / `factory` / `retail` 四档，profile 只写差异：

```json
{ "profiles": { "我的单位": {
    "add": { "ACTIVITY_VERBS": ["巡棚", "起苗"] },
    "add_units": ["亩", "茬"],
    "remove": { "CLICHE": ["沉淀"] } } } }
```

阈值不外置：`STACK_MIN`、`FLOOR/LEAD` 由两个评测标定，改了必须复跑。

## 测试

```bash
python scripts/validate_skill.py     # 结构 + 行为，一条命令跑完
python scripts/eval_checks.py        # 检查项双向评测：精确率 / 召回率
python scripts/eval_thresholds.py    # 对账阈值的正负样本可分性
```

42 条逐句标注样本要求双向达标（该报的必须报，**不该报的绝不许报**），另有 11 份稿件不变量、隐私脱敏闭环、词表契约负向测试、近邻诱饵零误判。

多条问题稿按"预期不命中"登记为**已知局限**（生僻动词绕过堆砌、A 级/95 分记法不识别）。哪天它们命中了，评测会失败提醒改标签——**宁可写明做不到，也不为了跑分把阈值调歪**。

## 能力边界

- 只输出可直接粘贴的 Markdown 正文；要 `.docx`/`.pptx`/`.xlsx` 成品请用对应技能
- 不管法定公文（GB/T 9704 的通知/请示/函/纪要）
- **保证结构和口径不塌，不能保证你说的是真话**——用编造数字写一份无懈可击的汇报，是能拿满分的
- 词表型检查换生僻说法就能绕过；"没做成但拦住了损失"这类零数字高价值事项，工具看不见，只能靠人问

## 安装

QwenWork 加载路径（把整个目录放进去即可）：

```
Windows      %USERPROFILE%\.qwenworkcn\skills\narrating-work-outcomes\
macOS/Linux  ~/.qwenworkcn/skills/narrating-work-outcomes/
```

要求 Python 3.10+，运行不联网。核心功能零第三方依赖；只有 `validate_skill.py` 的 metadata 检查段需要 PyYAML，没装会自动跳过该项（其余 130+ 项照常），从仓库根目录或任意工作目录运行均可。

## 打不开仓库 / 克隆失败

国内网络访问 GitHub 经常是**间歇性**的——同一台机器十几分钟内三条通道表现都不一样（实测：`raw.githubusercontent.com` 完全不通，`github.com` 反复连接重置，而 ZIP 下载和 API 正常）。所以先别怀疑代码。

**最省事：不用 git。** 装这个技能并不需要克隆。浏览器打开

```
https://github.com/huanglihui123456789-web/narrating-work-outcomes/archive/refs/heads/main.zip
```

下载解压，把里面的 `narrating-work-outcomes-main` 改名成 `narrating-work-outcomes`，放进上面的技能目录即可。这条路只需要能打开网页。

**要持续更新再配 SSH over 443**（GitHub 官方逃生通道，绕开常被堵的 22 端口）。在 `~/.ssh/config` 里加：

```
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

之后 `git clone git@github.com:huanglihui123456789-web/narrating-work-outcomes.git` 走的就是 443。

**先试一次手机热点。** 很多"用不了"其实只是当前网络对 GitHub 的路由坏了，换个出口就好。

### 关于第三方加速镜像——请用前先校验

ghproxy 一类加速站能救急，但要清楚两件事：

1. 它返回的是**别人转发的字节**。这个仓库里的东西会被 Qoder 当成技能**加载执行**（`scripts/*.py`、`wordlists.json` 都参与判定），所以一条被篡改的词条就能让检查结论静默变坏——这类问题不会报错，只会给出错误答案。
2. 因此：**只用镜像下载，永远不要经由镜像推送**；下载后核对提交号是否与官网一致：

```bash
git log -1 --format=%H          # 本地
# 与 https://github.com/huanglihui123456789-web/narrating-work-outcomes/commits/main 顶部那条对比
```

SHA 不一致就不要用。ZIP 下载同理：解压后核对最新提交的短号。

## 布局

```
SKILL.md              技能正文（铁律、七步流程、文体规则、边界）
audience-matrix.md    五种文体的读者、篇幅、结构、禁忌、开头模板
frameworks.md         改写公式、前后对照、无数据岗位的替代量化五法
wordlists.json        唯一词表来源
scripts/
  report_audit.py         体检器（gaps 提问 / final 评分 / --redact 脱敏）
  promise_reconcile.py    两期承诺对账
  wordpack.py             词表加载、派生正则、契约校验
  eval_checks.py          检查项双向评测
  eval_thresholds.py      阈值可分性评测
  validate_skill.py       结构 + 行为一把跑完
  sync_skill.py           开发副本 → 运行副本，带漂移检测
examples/             回归夹具（含故意写坏的问题稿）
```

## 许可

MIT。词表、框架文档和测试样本同样可自由使用、修改、再分发，商用也可以，不需要授权。

一点请求而非要求：如果你调整了词表或阈值，欢迎把误报/漏报的真实样本回灌进
`scripts/eval_checks.py` 再提 PR。这个工具的可靠性几乎全部来自那份双向标注——
只调阈值不补样本，它会安静地变差，而分数看起来还是满的。
