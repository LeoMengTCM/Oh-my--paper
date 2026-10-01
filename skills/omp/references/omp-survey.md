---
description: 文献调研（先筛后深）：多源检索出摘要表（可加 CNKI 中文文献）→用户勾选核心论文→只对选中的下载真实 PDF 并 OCR，再做 gap 分析
---

OMP 项目先读取实际 skills 目录下 `omp/SKILL.md`，运行 `omp/scripts/workflow.mjs` 检查当前阶段、依赖和产物后再执行本入口。单次任务与已授权全流程分别按原范围执行。


沿用当前会话已明确的意图、参数和授权；下文的确认步骤仅用于尚未决定的研究判断或范围变化。已有明确下一步时继续执行。


你是 Oh My Paper Orchestrator。文献调研的瓶颈在"筛"不在"搜"，分两遍走：先多源检索出轻量摘要表让用户挑核心论文，再只对选中的下载 PDF + OCR。把最贵的 OCR 留给会被读的论文。

## 第零步：系统综述路由（优先于下方通用流程）

先读 `research_brief.json` 的 `pipeline.track`。若为 `systematic-review`，从实际加载的 skills 目录读取 `systematic-review/references/rct-pairwise-profile.md`，按其入口规则选择 `exploratory-search` 或 `formal-review`。

- exploratory-search：可使用下方精选阅读流程，但所有结果标为探索，不产生正式 PRISMA 纳入计数。
- formal-review：核对具体方案版本的研究者批准及真实注册状态，再执行 experiment 阶段的正式检索子任务。记录完整策略、命中/取回数与 partial 状态；当前工具不能完整取回时明确缺口或使用用户合法导出，不调用不存在的分页命令。
- **formal-review 不执行下面的通用步骤**：不用 `--limit 30` 或挑 5–10 篇替代完整筛选，不按引用数、核心期刊或全文权限确定资格；全文未取得单列。结束后交接正式筛选，不进入 gap/idea 循环。

## 第一步：读取研究主题

```bash
cat .pipeline/memory/project_truth.md
cat .pipeline/docs/research_brief.json
cat .pipeline/memory/literature_bank.md
```

留意 `pipeline.track`（ml / clinical / systematic-review / bioinformatics）：决定查询扩展的受控词表（clinical→MeSH+PICO、ml→ACM CCS、math→MSC、economics→JEL）和是否走 PRISMA 筛选。

## 第二步：沿用已确定方向并展开查询

把已确定主题展开成互补检索式（同义词、子概念、缩写全称与适用受控词表），简要说明并执行已授权的公开检索；研究范围有实质歧义时才询问。CNKI 等需要账户的来源按实际权限处理，不能冒称检索过。

## 第三步：第一遍 —— 轻量摘要表（不下载）

corpus-name 按主题命名（如 `humanoid-locomotion`）。

```bash
python "$OMP_SKILLS/literature-pdf-ocr-library/scripts/search_and_download_papers.py" \
  --queries "<检索式A>" "<检索式B>" "<检索式C>" \
  --summary-only --limit 30 \
  --sources arxiv semanticscholar openalex crossref \
  --out-dir .pipeline/literature/<corpus-name>
```

- 设了 `S2_API_KEY` 降低 429 概率；没有也能跑（其他源兜底）。
- clinical / SR track：数据源加 `pubmed`，按 PICO 记录检索式留痕。
- 可选 Google Scholar 补引用数 / 捞漏（需 Chrome 远程调试）：先 `bash "$OMP_SKILLS/literature-pdf-ocr-library/scripts/check-deps.sh"`，没有 Chrome 就跳过。

### 3b. 中文文献（用户选了"加 CNKI"才做）

先 `node "$OMP_SKILLS/cnki-search/scripts/cnki.mjs" status` 自检。**退出码 2 表示需要用户处理**（Chrome 没开远程调试 / 没开知网标签）——停下把 `hint` 告诉用户，等他弄好再继续；不要假装查过了，也不要改用 curl 硬抓。

```bash
node "$OMP_SKILLS/cnki-search/scripts/cnki.mjs" advanced \
  --query "<检索式A>" --source 北大核心 CSSCI --from-year <起始年> --sort citations
node "$OMP_SKILLS/cnki-search/scripts/cnki.mjs" pages --action next   # 需要多页时逐页取
node "$OMP_SKILLS/cnki-search/scripts/cnki.mjs" journal --name "<刊名>"  # 查北大核心/CSSCI/CSCD 收录
```

**排序一定要显式指定**：CNKI 跨检索保留上次排序，不传 `--sort` 可能拿到按发表时间排的结果（全是当天网络首发），对调研没用。取回后核对 `activeSort` 是不是你要的。

把 `papers[]` 并进 `survey_screening.md`，数据源列标 `cnki`；`full_text_status` 按实际状态填：没下的填 `needs_institution`（全文多数要机构权限），**下载归档成功后填 `institution_pdf`**，两种情况都别默认写 `open_pdf`。撞到滑块验证码会返回 `{"error": "captcha"}` 且退出码 2——停下让用户在 Chrome 里手动完成拼图，等他回话再继续。

把生成的 `survey_screening.md` 展示给用户（标题/年/venue/引用/[new]/full_text_status/代码）。

## 第四步：用户勾选核心论文

请用户从摘要表里挑出要下载 + OCR 的核心论文（建议 5-10 篇）。只有 `full_text_status=open_pdf` 能下载到 PDF，其余仅留元数据——告诉用户便于取舍。

CNKI 来源的行是例外：能否下全文取决于用户在 Chrome 里的登录态与机构权限，选了就会去试（见第六步 6b），试失败按元数据保留。一并告诉用户，让他们知道选 CNKI 行是在赌权限。

## 第五步：使用已授权的全文读取方式

- PaddleOCR API（高质量，需用户提供 `PADDLEOCR_TOKEN`）
- 已有 JATS/XML/文本层或本地 pdfminer：按实际方式标记，可直接用于已授权阅读
- 只下载 PDF，暂不 OCR

不要反复询问本地读取方式。付费调用或向外部 OCR 上传材料需要符合已有授权；确实缺授权时再说明具体请求。不得把 PADDLEOCR_TOKEN 写入任何文件。

## 第六步：第二遍 —— 下载选中 + OCR

```bash
python "$OMP_SKILLS/literature-pdf-ocr-library/scripts/search_and_download_papers.py" \
  --arxiv-ids <选中id...> --download-pdfs \
  --out-dir .pipeline/literature/<corpus-name>

export PADDLEOCR_TOKEN="<用户提供>"
python "$OMP_SKILLS/literature-pdf-ocr-library/scripts/paddleocr_layout_to_markdown.py" \
  .pipeline/literature/<corpus-name>/papers/*/paper.pdf \
  --output-dir .pipeline/literature/<corpus-name>/papers --skip-existing
# 或 --fallback-pdfminer（用户已确认）

python "$OMP_SKILLS/literature-pdf-ocr-library/scripts/build_library_index.py" \
  --library-root .pipeline/literature/<corpus-name>
```

### 6b. CNKI 选中论文的下载（与上面并行，各走各的）

CNKI 全文下不了走 `--arxiv-ids`（那是开放获取那条链），单独用 cnki-search：

```bash
node "$OMP_SKILLS/cnki-search/scripts/cnki.mjs" detail --url "<论文url>" > /tmp/omp-meta.json
node "$OMP_SKILLS/cnki-search/scripts/cnki.mjs" download --format pdf
node "$OMP_SKILLS/cnki-search/scripts/cnki.mjs" collect \
  --title "<论文标题>" --into .pipeline/literature/<corpus-name>/papers \
  --meta /tmp/omp-meta.json
```

`download` 不带 `--url` 时会回到 `detail` 刚用过的标签页，两条要连着跑。

失败一律退出码 2，按 `error` 分四种：`not_logged_in` / `captcha`（登录、手动过拼图后重跑）、`record_only`（**只有题录、没有全文**，页面上连下载区都没有，登录或换权限都没用）、`no_download_link`（该文献确实未提供全文）。放弃就按元数据保留，`full_text_status` 标 `needs_institution`，**不要伪称拿到了全文**。归档后的 PDF 和开放获取论文跑同一套 OCR 脚本。**CAJ 不是 PDF**（`KDH` 私有格式），OCR 脚本读不了，只能留档；PDF 与 CAJ 同时存在时 `collect` 优先归档 PDF。

`collect` 会写出 `metadata.json`，这一步不能省：`build_library_index.py` / `build_bibliography.py` 都按 `papers/*/metadata.json` 遍历，缺了就报 0 篇且退出码 0。`--meta` 才有年份/作者/期刊；`full_text_status` 写 `institution_pdf`，**不要写成 `open_pdf`**。

`download` 只触发不等待，返回 `status: downloading` 时文件还没落盘（PDF 约 4–5 秒，CAJ 更久），先等几秒再 `collect`。`collect` 匹配不到或有歧义时以退出码 2 报错，**不会替你猜**——按它列出的实际文件名改用 `--file "<文件名>"` 重跑，别盲目重试 `--title`。

## 第七步：补充搜索（按需）

覆盖不足的方向用 `inno-deep-research` 针对性补搜（每方向至少 5 篇），并回摘要表 / bank。不要默认全量重搜。中文文献不足的方向用 cnki-search 补，别拿英文库的结果硬凑中文覆盖。

## 第八步：固化参考文献 + 入库 + gap 分析

先生成权威参考文献库（write 阶段唯一可信的引用源）：

```bash
python "$OMP_SKILLS/literature-pdf-ocr-library/scripts/build_bibliography.py" \
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

核对报告、可追溯书目、已有综述重合、代表性原始研究、实际全文阅读范围及未决问题，不能靠篇数或一句“已完成”通过。
将真实文件路径写入 survey 任务的 `artifacts`，将核查范围、结果和局限写入 `completionSummary`，再更新状态与 project_truth.md。
重跑 workflow preflight：用户已要求 OMP 全流程时，读取 ideate 工作流并在本轮产出基于证据的候选方向比较，停在用户选择方向处；不要只说“下一步我将收敛选题”。
用户仅授权本轮 survey 时，交付报告并说明具体下一任务，不擅自超范围。正式系统综述分支依然交接筛选，不转入候选题目循环。
