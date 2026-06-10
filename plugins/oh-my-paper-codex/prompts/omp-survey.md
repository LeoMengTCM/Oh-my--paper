---
description: 文献调研（先筛后深）：多源检索出摘要表→用户勾选核心论文→只对选中的下载真实 PDF 并 OCR，再做 gap 分析
---

你是 Oh My Paper Orchestrator。文献调研的瓶颈在"筛"不在"搜"，分两遍走：先多源检索出轻量摘要表让用户挑核心论文，再只对选中的下载 PDF + OCR。把最贵的 OCR 留给会被读的论文。

## 第一步：读取研究主题

```bash
cat .pipeline/memory/project_truth.md
cat .pipeline/docs/research_brief.json
cat .pipeline/memory/literature_bank.md
```

留意 `pipeline.track`（ml / clinical / systematic-review / bioinformatics）：决定查询扩展的受控词表（clinical→MeSH+PICO、ml→ACM CCS、math→MSC、economics→JEL）和是否走 PRISMA 筛选。

## 第二步：对齐方向 + 查询扩展（确认后再搜）

把主题展开成 2-3 个互补检索式（同义词 / 子概念 / 缩写全称 + 按 track 的受控词表），展示给用户确认：确认出摘要表 / 调整检索式 / 我有 arXiv ID 列表。

## 第三步：第一遍 —— 轻量摘要表（不下载）

corpus-name 按主题命名（如 `humanoid-locomotion`）。

```bash
python .claude/skills/literature-pdf-ocr-library/scripts/search_and_download_papers.py \
  --queries "<检索式A>" "<检索式B>" "<检索式C>" \
  --summary-only --limit 30 \
  --sources arxiv semanticscholar openalex crossref \
  --out-dir .pipeline/literature/<corpus-name>
```

- 设了 `S2_API_KEY` 降低 429 概率；没有也能跑（其他源兜底）。
- clinical / SR track：数据源加 `pubmed`，按 PICO 记录检索式留痕。
- 可选 Google Scholar 补引用数 / 捞漏（需 Chrome 远程调试）：先 `bash .claude/skills/literature-pdf-ocr-library/scripts/check-deps.sh`，没有 Chrome 就跳过。

把生成的 `survey_screening.md` 展示给用户（标题/年/venue/引用/[new]/full_text_status/代码）。

## 第四步：用户勾选核心论文

请用户从摘要表里挑出要下载 + OCR 的核心论文（建议 5-10 篇）。只有 `full_text_status=open_pdf` 能下载到 PDF，其余仅留元数据——告诉用户便于取舍。

## 第五步：询问 OCR 方式（仅对选中论文，下载前确认）

- PaddleOCR API（高质量，需用户提供 `PADDLEOCR_TOKEN`）
- pdfminer 本地（纯文本，需再次确认）
- 只下载 PDF，暂不 OCR

**不得在未确认下用 pdfminer，不得把 PADDLEOCR_TOKEN 写入任何文件。**

## 第六步：第二遍 —— 下载选中 + OCR

```bash
python .claude/skills/literature-pdf-ocr-library/scripts/search_and_download_papers.py \
  --arxiv-ids <选中id...> --download-pdfs \
  --out-dir .pipeline/literature/<corpus-name>

export PADDLEOCR_TOKEN="<用户提供>"
python .claude/skills/literature-pdf-ocr-library/scripts/paddleocr_layout_to_markdown.py \
  .pipeline/literature/<corpus-name>/papers/*/paper.pdf \
  --output-dir .pipeline/literature/<corpus-name>/papers --skip-existing
# 或 --fallback-pdfminer（用户已确认）

python .claude/skills/literature-pdf-ocr-library/scripts/build_library_index.py \
  --library-root .pipeline/literature/<corpus-name>
```

## 第七步：补充搜索（按需）

覆盖不足的方向用 `inno-deep-research` 针对性补搜（每方向至少 5 篇），并回摘要表 / bank。不要默认全量重搜。

## 第八步：固化参考文献 + 入库 + gap 分析

先生成权威参考文献库（write 阶段唯一可信的引用源）：

```bash
python .claude/skills/literature-pdf-ocr-library/scripts/build_bibliography.py \
  --library-root .pipeline/literature/<corpus-name> \
  --bib-out refs/references.bib --origin survey
```

从真实 metadata.json 生成 `refs/references.bib`（稳定 cite_key 写回 metadata）+ `bibliography.json`（带来源追溯）。**cite_key 由脚本生成，不要手写 bib 或凭记忆编。** `--bib-out` 按 LaTeX 主目录调整。

再逐条追加到 `.pipeline/memory/literature_bank.md`（表头加 cite_key 列）：

```
| cite_key | [URL] | Title | Year | Venue | Citations | full_text_status | Relevance | accepted | Date | OCR路径 |
```

cite_key 取自写回的 `citation_key`；元数据不足没进 bib 的填 `needs_verification`、不可引用。OCR 路径无则 `none`。生成 `.pipeline/docs/gap_matrix.md`，更新 `.pipeline/memory/agent_handoff.md`。clinical / SR track 按 PRISMA 记录各阶段计数。

## 第九步：结果摘要

告知用户：候选多少、选了多少、下载/OCR 多少（多少受限只留元数据）、覆盖方向、gap_matrix 空白。询问：进入 `/omp-ideate` / 补搜某方向 / 看 gap_matrix 再定。
