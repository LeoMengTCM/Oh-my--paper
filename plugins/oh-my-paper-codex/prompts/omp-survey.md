---
description: 文献调研（先筛后深）：多源检索出摘要表（可加 CNKI 中文文献）→用户勾选核心论文→只对选中的下载真实 PDF 并 OCR，再做 gap 分析
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

把主题展开成 2-3 个互补检索式（同义词 / 子概念 / 缩写全称 + 按 track 的受控词表），展示给用户确认：确认出摘要表 / 要中文文献加 CNKI / 调整检索式 / 我有 arXiv ID 列表。主题涉及中文期刊、学位论文或国内临床实践时，主动建议加 CNKI。

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

### 3b. 中文文献（用户选了"加 CNKI"才做）

先 `node .claude/skills/cnki-search/scripts/cnki.mjs status` 自检。**退出码 2 表示需要用户处理**（Chrome 没开远程调试 / 没开知网标签）——停下把 `hint` 告诉用户，等他弄好再继续；不要假装查过了，也不要改用 curl 硬抓。

```bash
node .claude/skills/cnki-search/scripts/cnki.mjs advanced \
  --query "<检索式A>" --source 北大核心 CSSCI --from-year <起始年> --sort citations
node .claude/skills/cnki-search/scripts/cnki.mjs pages --action next   # 需要多页时逐页取
node .claude/skills/cnki-search/scripts/cnki.mjs journal --name "<刊名>"  # 查北大核心/CSSCI/CSCD 收录
```

**排序一定要显式指定**：CNKI 跨检索保留上次排序，不传 `--sort` 可能拿到按发表时间排的结果（全是当天网络首发），对调研没用。取回后核对 `activeSort` 是不是你要的。

把 `papers[]` 并进 `survey_screening.md`，数据源列标 `cnki`；全文要机构权限，`full_text_status` 一般填 `needs_institution`，别默认写 `open_pdf`。撞到滑块验证码会返回 `{"error": "captcha"}` 且退出码 2——停下让用户在 Chrome 里手动完成拼图，等他回话再继续。

把生成的 `survey_screening.md` 展示给用户（标题/年/venue/引用/[new]/full_text_status/代码）。

## 第四步：用户勾选核心论文

请用户从摘要表里挑出要下载 + OCR 的核心论文（建议 5-10 篇）。只有 `full_text_status=open_pdf` 能下载到 PDF，其余仅留元数据——告诉用户便于取舍。

CNKI 来源的行是例外：能否下全文取决于用户在 Chrome 里的登录态与机构权限，选了就会去试（见第六步 6b），试失败按元数据保留。一并告诉用户，让他们知道选 CNKI 行是在赌权限。

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

### 6b. CNKI 选中论文的下载（与上面并行，各走各的）

CNKI 全文下不了走 `--arxiv-ids`（那是开放获取那条链），单独用 cnki-search：

```bash
node .claude/skills/cnki-search/scripts/cnki.mjs detail --url "<论文url>"
node .claude/skills/cnki-search/scripts/cnki.mjs download --format pdf
node .claude/skills/cnki-search/scripts/cnki.mjs collect \
  --title "<论文标题>" --into .pipeline/literature/<corpus-name>/papers
```

返回 `not_logged_in` / `captcha` / `no_download_link` 时按 `hint` 处理：登录、手动过拼图，或放弃。放弃就按元数据保留，`full_text_status` 标 `needs_institution`，**不要伪称拿到了全文**。归档后的 PDF 和开放获取论文跑同一套 OCR 脚本。**CAJ 不是 PDF**，OCR 脚本读不了，只能留档。

## 第七步：补充搜索（按需）

覆盖不足的方向用 `inno-deep-research` 针对性补搜（每方向至少 5 篇），并回摘要表 / bank。不要默认全量重搜。中文文献不足的方向用 cnki-search 补，别拿英文库的结果硬凑中文覆盖。

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

cite_key 取自写回的 `citation_key`；元数据不足没进 bib 的填 `needs_verification`、不可引用。OCR 路径无则 `none`。

CNKI 来源的行：只有 PDF 归档进 `papers/<slug>/` 并生成了 `metadata.json` 的才进 `references.bib`；没有全文的中文文献 cite_key 填 `needs_verification`，在 bank 里保留但不可引用。GB/T 7714 引用串（`cnki.mjs export --mode gbt`）不能直接当 BibTeX 用。

生成 `.pipeline/docs/gap_matrix.md`，更新 `.pipeline/memory/agent_handoff.md`。clinical / SR track 按 PRISMA 记录各阶段计数。

## 第九步：结果摘要

告知用户：候选多少、选了多少、下载/OCR 多少（多少受限只留元数据）、覆盖方向、gap_matrix 空白。询问：进入 `/omp-ideate` / 补搜某方向 / 看 gap_matrix 再定。
