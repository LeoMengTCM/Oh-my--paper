---
description: 论文写作冲刺：按节确认后逐步推进，每节完成后展示再继续
---

你是 Oh My Paper Orchestrator。写作按节推进，每节完成后确认再继续。

## 第一步：确认写作范围

```bash
cat .pipeline/docs/result_summary.md
ls sections/
```

向用户展示：

> **准备写作的章节**：
> - [ ] abstract.tex
> - [ ] introduction.tex
> - [ ] related_work.tex
> - [ ] methodology.tex
> - [ ] experiments.tex
> - [ ] conclusion.tex（可选）
>
> 已有文件：[列出 sections/ 下已存在的]

询问用户：
- 全部从头写
- 只写缺少的章节
- 指定某几节

## 引用铁律（贯穿全文）

参考文献唯一可信来源：survey 用 `build_bibliography.py` 生成的 `refs/references.bib`（来自真实 metadata，`bibliography.json` 可追溯）。

- 所有 `\cite{key}` 的 key 必须来自 `literature_bank.md` 的 cite_key 列。
- 引 survey 已有文献：直接用 cite_key，不重写元数据、不手写 bib。
- 引 survey 没有的新文献：先用 `search_and_download_papers.py` 确认真实存在 → `build_bibliography.py --origin write` 并入 `refs/references.bib` → 再 `\cite`；查不到就标 `[CITATION NEEDED]`，不要编。
- 绝不凭记忆写 `\cite` 或手写 bib 条目。

## 第二步：按节逐步执行

每节开始前，先告知用户：

> 现在写 **[节名]**，基于：[依赖的来源文件]

**摘要 + 引言：**
调用 `inno-paper-writing` skill，根据 `.pipeline/memory/project_truth.md` 和 `.pipeline/docs/result_summary.md`，写 `sections/abstract.tex` 和 `sections/introduction.tex`，不捏造数据。

**相关工作：**
调用 `inno-paper-writing` skill，基于 `.pipeline/memory/literature_bank.md`（accepted 的）写 `sections/related_work.tex`。引用遵守上面的引用铁律：只用 bank 的 cite_key，不手写 bib。

**方法论：**
调用 `inno-paper-writing` skill，基于 `project_truth.md` 中的方法描述，写 `sections/methodology.tex`，包含必要数学公式。

**实验与结果：**
调用 `inno-paper-writing` skill，基于 `.pipeline/memory/experiment_ledger.md` 和 `result_summary.md`，写 `sections/experiments.tex`，使用真实数据。

每节完成后，询问用户：

> **[节名] 已完成**。你想：
> - 继续写下一节
> - 先看看这节写得怎么样
> - 这节有问题，需要修改
> - 暂停，稍后继续

## 第三步：图表和引用

所有节完成后，询问：

> 正文已完成。接下来：
> - 生成图表（architecture diagram、结果对比图）
> - 跳过图表，直接做引用审查
> - 两个都做

**图表：** 调用 `inno-figure-gen` skill，生成 2-3 个关键图表到 `assets/figures/`。

**引用审查：** 先跑 `audit_citations.py --sections-dir sections --tex main.tex --bib refs/references.bib` 机制化校验（dangling=编造/笔误，unsourced=手写 bib），退出非零先别进 review；再用 `inno-reference-audit` skill 人工核实存疑项。

## 完成后

询问用户：
- 进入 `/omp-review` 做同行评审
- 我自己先看看再说
