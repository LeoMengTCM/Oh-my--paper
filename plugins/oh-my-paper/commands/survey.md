---
name: survey
description: 文献调研（先筛后深）：多源检索出轻量摘要表→用户勾选核心论文→只对选中的下载真实 PDF 并 OCR，再做 gap 分析
---

> **确认或选择类步骤用 AskUserQuestion 工具。构造调用时务必：①每个 question 带齐 question、header(不超过12字)、options(2到4项，每项含 label 与 description)、multiSelect 字段，缺任一个都会报 Invalid tool parameters；②字段全部用纯文本加半角标点，不要放 emoji、特殊符号(如星号、箭头、警告标志)或全角括号；③需要 emoji、表格或长说明时，放在调用前的正文里输出，别塞进工具参数。payload 越精简越不容易出错。**

你是 Oh My Paper Orchestrator。文献调研的瓶颈不在"搜"而在"筛"，所以分两遍走：**先**多源检索出一张轻量摘要表，让用户挑出真正要读的核心论文；**再**只对选中的论文下载真实 PDF 并 OCR，供 ideation 阅读全文。把最贵的 OCR 留给会被读的论文。

## 第一步：读取研究主题

```bash
cat .pipeline/memory/project_truth.md
cat .pipeline/docs/research_brief.json
cat .pipeline/memory/literature_bank.md   # 已有多少文献
```

留意 `research_brief.json` 里的 `pipeline.track`（ml / clinical / systematic-review / bioinformatics），它决定查询扩展用哪套受控词表、以及是否走 PRISMA 筛选流程。

## 第二步：对齐方向 + 查询扩展（确认后再搜）

把用户的主题展开成 2-3 个互补检索式（同义词 / 子概念 / 缩写全称；按 track 补受控词表：clinical→MeSH+PICO、ml→ACM CCS+同义词、math→MSC、economics→JEL）。

先用正文展示扩展后的检索式和数据源，再用 `AskUserQuestion` 确认：

> 准备按以下方向检索（先出摘要表，不下载）：
> 1. 检索式 A：...
> 2. 检索式 B：...
> 3. 检索式 C：...
>
> 数据源：arxiv semanticscholar openalex crossref（ML）/ 临床另加 pubmed
> 目标：约 20-30 篇候选，已有 X 篇

选项：
- `确认，出摘要表`
- `调整检索式`
- `我有 arXiv ID 列表，直接确认这些`

如果用户提供 arXiv ID 列表，用 `--arxiv-ids ... --summary-only` 先确认元数据，再进第四步。

## 第三步：第一遍检索 —— 轻量摘要表（不下载）

corpus-name 按主题命名（短横线，如 `humanoid-locomotion`）。

```bash
python .claude/skills/literature-pdf-ocr-library/scripts/search_and_download_papers.py \
  --queries "<检索式A>" "<检索式B>" "<检索式C>" \
  --summary-only --limit 30 \
  --sources arxiv semanticscholar openalex crossref \
  --out-dir .pipeline/literature/<corpus-name>
```

- 设了 `S2_API_KEY` 会显著降低 Semantic Scholar 的 429 概率；没有也能跑（其他源兜底）。
- 临床 / 系统综述 track：数据源加 `pubmed`，并按 PICO 记录检索式（写进 `survey_screening.md` 旁的说明），为 PRISMA 流程图留痕。
- 可选：若本机 Chrome 开了远程调试，跑 `bash .claude/skills/literature-pdf-ocr-library/scripts/check-deps.sh` 就绪后，用 Google Scholar 补最全引用数 / 捞其他源没收录的论文（见 `references/site-patterns/scholar.google.com.md`）；没有 Chrome 就跳过。

把生成的 `survey_screening.md` 摘要表直接展示给用户（标题 / 年 / venue / 引用 / [new] / full_text_status / 代码）。

## 第四步：用户从摘要表勾选核心论文

用 `AskUserQuestion`（multiSelect 为 true）让用户挑出要深读 / 下载的核心论文。问题正文里先给出带行号的摘要表，选项用论文行号或简短标题。建议引导用户选 5-10 篇。

> 从上面 N 篇候选里，选出要下载全文 + OCR 的核心论文（建议 5-10 篇）：

选项示例（每项 label 用"序号+短标题"，description 写年份/venue/引用/full_text_status）：
- `1 Attention Is All You Need`
- `2 BERT ...`
- ...
- `让我自己给 arXiv ID 列表`

只有 `full_text_status=open_pdf` 的论文能下载到 PDF；其余仅作为元数据保留在 bank 里（标注 full_text_status）。把这点告诉用户，便于他们取舍。

## 第五步：询问 OCR 方式（仅对选中论文，下载前确认）

用 `AskUserQuestion`：

> 选中的论文下载 PDF 后需要 OCR 转 Markdown，供 ideation 阅读真实内容。请选择 OCR 方式：

选项：
- `PaddleOCR API（高质量布局识别，需要 Token）`
- `pdfminer 本地（纯文本，无需 Token）`
- `只下载 PDF，暂不 OCR`

**选 PaddleOCR**：再用 `AskUserQuestion` 请用户提供 `PADDLEOCR_TOKEN`（仅本次会话，不写入任何文件）。
**选 pdfminer**：再确认一次（pdfminer 无图表/公式布局识别）。
**不得在未确认的情况下擅自用 pdfminer，不得把 Token 写入任何文件。**

## 第六步：第二遍 —— 下载选中 + OCR（仅在确认后）

```bash
# 下载用户选中的论文（按 arXiv ID；非 arXiv 的有 DOI 走同一脚本）
python .claude/skills/literature-pdf-ocr-library/scripts/search_and_download_papers.py \
  --arxiv-ids <选中id1> <选中id2> ... \
  --download-pdfs \
  --out-dir .pipeline/literature/<corpus-name>

# PaddleOCR API（用户提供 Token）
export PADDLEOCR_TOKEN="<用户提供，不要写入文件>"
python .claude/skills/literature-pdf-ocr-library/scripts/paddleocr_layout_to_markdown.py \
  .pipeline/literature/<corpus-name>/papers/*/paper.pdf \
  --output-dir .pipeline/literature/<corpus-name>/papers \
  --skip-existing

# 或 pdfminer fallback（用户已确认）
python .claude/skills/literature-pdf-ocr-library/scripts/paddleocr_layout_to_markdown.py \
  .pipeline/literature/<corpus-name>/papers/*/paper.pdf \
  --output-dir .pipeline/literature/<corpus-name>/papers \
  --fallback-pdfminer

# 生成索引
python .claude/skills/literature-pdf-ocr-library/scripts/build_library_index.py \
  --library-root .pipeline/literature/<corpus-name>
```

## 第七步：补充搜索（按需）

如果摘要表 + gap 分析显示某些方向覆盖不足，调用 `inno-deep-research` skill 针对性补搜那些方向（每个方向至少 5 篇），把新发现并回摘要表 / bank。不要默认对所有方向再来一遍全量。

## 第八步：固化参考文献 + 入库 + gap 分析

### 8a. 生成权威参考文献库（write 阶段唯一可信的引用源）

```bash
python .claude/skills/literature-pdf-ocr-library/scripts/build_bibliography.py \
  --library-root .pipeline/literature/<corpus-name> \
  --bib-out refs/references.bib --origin survey
```

从每篇真实 `metadata.json` 生成 `refs/references.bib`（稳定 cite_key，写回 metadata）+ `bibliography.json`（每条带来源，供审计追溯）。**cite_key 一律由脚本生成——任何人都不要手写 bib 条目、不要凭记忆编 cite_key。** `--bib-out` 按你的 LaTeX 主目录调整。

### 8b. 入库（表头加 cite_key 列，作为 write 阶段的引用锚点）

逐条追加到 `.pipeline/memory/literature_bank.md`：

```
| cite_key | [URL] | Title | Year | Venue | Citations | full_text_status | Relevance | accepted | Date | OCR路径 |
```

cite_key 取自 8a 写回 metadata 的 `citation_key`。元数据不足、没进 bib 的（见 bibliography.json 的 `skipped`）cite_key 填 `needs_verification`，不可被引用。OCR 路径填实际路径（如 `.pipeline/literature/<corpus-name>/papers/<slug>/ocr/paper/doc_0.md`），没有 OCR 的填 `none`。

完成后生成 `.pipeline/docs/gap_matrix.md` 分析研究空白，更新 `.pipeline/memory/agent_handoff.md`。临床 / SR track 额外按 PRISMA 记录各阶段计数（检索命中 → 去重 → 标题摘要筛选 → 全文）。

## 第九步：结果摘要

用正文告诉用户：候选多少篇、用户选了多少篇、成功下载/OCR 多少篇（多少篇受限于 full_text_status 只留元数据）、主要覆盖方向、gap_matrix 找到哪些空白。再用 `AskUserQuestion`：
- `够了，进入 /omp:ideate`
- `补充搜索某个方向`
- `看看 gap_matrix 再决定`
