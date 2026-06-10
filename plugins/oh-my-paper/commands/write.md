---
name: write
description: 论文写作冲刺：按节确认后逐步推进，每节完成后展示再继续
---

> **确认或选择类步骤用 AskUserQuestion 工具。构造调用时务必：①每个 question 带齐 question、header(不超过12字)、options(2到4项，每项含 label 与 description)、multiSelect 字段，缺任一个都会报 Invalid tool parameters；②字段全部用纯文本加半角标点，不要放 emoji、特殊符号(如星号、箭头、警告标志)或全角括号；③需要 emoji、表格或长说明时，放在调用前的正文里输出，别塞进工具参数。payload 越精简越不容易出错。**

你是 Oh My Paper Orchestrator。写作按节推进，每节完成后确认再继续。

## 第一步：确认写作范围

先确定 LaTeX 工作区根目录：优先 `paper/`（README 推荐布局），若 `sections/` 直接在项目根目录则用根目录。下文的 `sections/`、`refs/`、`main.tex` 都相对这个根。

```bash
ls paper/sections sections 2>/dev/null
cat .pipeline/memory/result_summary.md
cat .pipeline/memory/experiment_ledger.md
cat .pipeline/memory/figure_ledger.md   # 实验期攒下的图素材清单
```

用 `AskUserQuestion` 展示：

> **准备写作的章节**：
> - [ ] abstract.tex
> - [ ] introduction.tex
> - [ ] related_work.tex
> - [ ] methodology.tex
> - [ ] experiments.tex
> - [ ] conclusion.tex（可选）
>
> 已有文件：[列出 sections/ 下已存在的]

选项：
- `全部从头写`
- `只写缺少的章节`
- `指定某几节`

## 引用铁律（贯穿所有章节）

参考文献只有一个可信来源：survey 阶段由 `build_bibliography.py` 生成的 `refs/references.bib`（每条都来自真实 metadata，可在 `bibliography.json` 追溯）。

- **所有 `\cite{key}` 的 key 必须来自 `literature_bank.md` 的 cite_key 列**（一一对应 `references.bib` 的条目）。
- **引用 survey 已有文献**：直接用它的 cite_key，元数据已在 `references.bib`——不要重写作者/年份/DOI，不要手写 bib 条目。
- **需要 survey 没有的新文献**：先确认真实存在再引——
  1. 用检索脚本拿真实元数据：`search_and_download_papers.py --query "..." --summary-only`（或 `--arxiv-ids`）下到一个 corpus；
  2. `build_bibliography.py --library-root <corpus> --bib-out refs/references.bib --origin write` 并入（自动生成 cite_key）；
  3. 再 `\cite` 这个新 cite_key。
  查不到就**不要引**，用 `[CITATION NEEDED]` 标注并告诉用户。
- **绝不凭记忆写 `\cite` 或手写 bib 条目**——AI 生成的引用约 40% 是错的。第三步会用 `audit_citations.py` 抓悬空引用和无来源 bib 条目。

## 篇幅与完整性铁律（贯穿所有章节）

**LLM 写论文的默认毛病是写得太短：把几个月的工作量压缩成几句话。** 这里的纪律是反向的——按下限写足，删减留给 review 阶段：

| 章节 | 字数下限（英文词） | 完整性要求 |
|------|------------------|-----------|
| abstract | 150–250 | 问题、方法、关键数字结果、意义，一样不缺 |
| introduction | ≥800 | 完整论证链；每个贡献点单独成段，不是一行列表 |
| related_work | ≥600 | 覆盖 literature_bank 全部 accepted 文献的主题簇，逐簇比较 |
| methodology | ≥1500 | 写到可复现：每个公式、每个设计选择的理由、实现细节与超参数表 |
| experiments | ≥1500 | **逐条覆盖 experiment_ledger 的每个实验**：setup、主结果、每个消融、失败分析各自成小节，配图配表 |
| conclusion | ≥200 | 结论 + 局限性 + future work |

- 下限是底线不是目标；拿不准详略时，往详细写。
- **禁止压缩工作量**：三个消融不能合写成一句"ablations confirm our design"；每个实验都值得完整段落（动机 → 设置 → 数字 → 解读）。
- 每节写完跑 `wc -w sections/<节>.tex`（或 texcount），把字数连同下限一起报给用户；低于下限要么扩写，要么向用户说明理由。

## 第二步：按节逐步执行

每节开始前，先告知用户：

> 现在写 **[节名]**，基于：[依赖的来源文件]

然后调用 Codex：

**摘要 + 引言：**

调用 `inno-paper-writing` skill，根据 `.pipeline/memory/project_truth.md` 和 `.pipeline/memory/result_summary.md`，写 `sections/abstract.tex` 和 `sections/introduction.tex`，不捏造数据。

**相关工作：**

调用 `inno-paper-writing` skill，基于 `.pipeline/memory/literature_bank.md`（accepted 的）写 `sections/related_work.tex`。引用严格遵守上面的"引用铁律"：只用 bank 里的 cite_key，不手写 bib。

**方法论：**

调用 `inno-paper-writing` skill，基于 `project_truth.md` 中的方法描述，写 `sections/methodology.tex`，包含必要数学公式。

**实验与结果：**

调用 `inno-paper-writing` skill，基于 `.pipeline/memory/experiment_ledger.md` 和 `result_summary.md`，写 `sections/experiments.tex`，使用真实数据。**写之前先把 experiment_ledger 逐条列成清单，每条对应正文一个小节或段落；写完逐条打勾核对，一条都不许漏。**图用 `\ref` 引用 figure_ledger 里规划的图（图的组装在第三步）。

每节完成后，先报字数（`wc -w`，对照篇幅铁律的下限），再用 `AskUserQuestion` 询问：

> **[节名] 已完成**。你想：

选项：
- `继续写下一节`
- `先看看这节写得怎么样`
- `这节有问题，让 Codex 修改`
- `暂停，稍后继续`

## 第三步：图表和引用

所有节完成后，用 `AskUserQuestion` 询问：

> 正文已完成。接下来：

选项：
- `组装论文图（多面板大图）+ 引用审查`
- `只做图`
- `只做引用审查`

**图表（组装，不是从零画）：**

发表级的图是多面板大图：一张主结果图常由 (a)(b)(c)(d) 四个子图拼成。素材应已在实验阶段攒在 `figure_ledger.md` 里——这一步做的是**编排与拼装**：

1. 读 `figure_ledger.md`，按"拟用章节/面板"列把子图分组成大图方案（如：图2 = (a) 训练曲线 (b) 消融对比 (c) 超参敏感性 (d) 样例可视化），先把方案展示给用户。
2. 用绘图脚本拼面板（matplotlib subplots 重绘，或 LaTeX `subfigure` 排版），输出到 `assets/figures/`；统一字号、配色、图例。
3. 概念图 / 架构图 / 流程示意（不含数据的）才用 `inno-figure-gen` 生成。**带数据的图一律来自实验期的绘图脚本，禁止用图像生成模型画。**
4. 核对：正文每个主要结果至少一张图；每张图都被 `\ref` 且 caption 自含（逐面板说明）；ledger 里规划的图没有遗漏。
5. **发现缺图**：列出缺什么（哪个实验、哪种图），回 `/omp:experiment` 用现成的 `<名>.csv` + `plot_<名>.py` 补画——不要现编数据。

**引用审查：**

先跑审计脚本（机制化校验），再让 `inno-reference-audit` skill 人工核实存疑项：

```bash
python .claude/skills/literature-pdf-ocr-library/scripts/audit_citations.py \
  --sections-dir sections --tex main.tex --bib refs/references.bib
```

- dangling（`\cite` 的 key 不在 bib）：补 survey 的 cite_key，或按引用铁律确认新文献后入库
- unsourced（bib 条目无来源）：有人手写了 bib——删掉或按铁律重新确认入库

脚本退出非零就先别进 review。

## 第四步：完整性核对（进入 review 前的门）

把下面的核对表逐项检查并展示结果给用户：

- [ ] **工作量覆盖**：experiment_ledger 每一条都能在 experiments.tex 里指出对应小节/段落（列对照表）
- [ ] **图覆盖**：figure_ledger 里状态非 unused 的图都被 `\ref`；每个主要结果至少一张图
- [ ] **篇幅达标**：各节字数 vs 铁律下限（列表格：节 / 字数 / 下限 / 达标与否）
- [ ] **贡献一致**：abstract、introduction、conclusion 三处的贡献点说法一致
- [ ] **数字一致**：正文引用的关键数字与 result_summary.md 一致

有任何一项不过，先回对应步骤补齐再继续。

## 完成后

用 `AskUserQuestion` 询问：
- `进入 /omp:review 做同行评审`
- `我自己先看看再说`
