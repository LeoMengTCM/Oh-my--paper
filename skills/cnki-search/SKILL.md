---
id: cnki-search
name: cnki-search
version: 1.0.0
description: |-
  Search and mine CNKI (中国知网) from a logged-in Chrome via the repo's CDP proxy: keyword and advanced search, screening-table extraction, pagination and sorting, paper detail metadata, GB/T 7714 / RIS / EndNote export, journal lookup and indexing status, PDF/CAJ download triggering. Use when a survey or literature review needs Chinese-language literature — 中文文献检索, 知网, CNKI, 核心期刊, 北大核心, CSSCI, CSCD, 中文期刊, 学位论文, 期刊收录查询. Requires Chrome running with remote debugging and a logged-in CNKI session; without it the skill reports the precondition and stops. Do not use for English-language retrieval (use literature-pdf-ocr-library) or for scraping CNKI without a user-owned logged-in session.
stages:
  - "survey"
primaryIntent: research
intents:
  - "research"
capabilities:
  - "search-retrieval"
domains:
  - "general"
keywords:
  - "cnki-search"
  - "cnki"
  - "知网"
  - "中国知网"
  - "中文文献"
  - "中文期刊"
  - "核心期刊"
  - "北大核心"
  - "cssci"
  - "cscd"
  - "学位论文"
  - "期刊收录"
  - "gbt 7714"
  - "paper search"
  - "literature search"
  - "文献检索"
source: builtin
status: verified
handoffQuestionMode: partial
privateMaterialSafety: moderate
upstream:
  repo: cookjohn/cnki-skills
  path: skills/
  revision: 20d65f660456daf53ad0f7c74494ac3b829b925f
  license: none-declared
---

# CNKI Search（中国知网检索）

从用户**自己开着远程调试、且已登录**的 Chrome 里操作 CNKI，拿到检索结果与论文元数据。
不做请求伪造、不绕验证码——CNKI 没有公开 API，登录态是唯一的正路。

上游是 [cookjohn/cnki-skills](https://github.com/cookjohn/cnki-skills) 的 10 个 chrome-devtools MCP
技能。本仓库把它并成一个技能，DOM 选择器与取数逻辑原样保留，只把传输层换成自己已有的
`literature-pdf-ocr-library/scripts/cdp-proxy.mjs`，不再依赖额外 MCP。

## 前置条件（缺一不可）

1. Chrome 以 `--remote-debugging-port=9222` 启动；
2. Chrome 里已登录 CNKI 账号（下载全文才需要，检索一般不需要）；
3. CDP proxy 就绪——`bash .claude/skills/literature-pdf-ocr-library/scripts/check-deps.sh`
   会检查并自动拉起（`cnki.mjs` 也会在首次调用时自己拉起）。

先跑 `node .claude/skills/cnki-search/scripts/cnki.mjs status` 看环境。**退出码 2 表示
"需要用户处理"**（Chrome 没开 / 没登录 / 撞验证码），此时停下告诉用户，别重试。

**滑块验证码**：CNKI 用腾讯滑块（"拖动下方拼图完成验证"），程序解不了。检测到就停下，
让用户在 Chrome 里手动完成，等他回话再继续。别快速连续翻页，会更容易触发。

## 命令

脚本路径以 `.claude/skills/cnki-search/scripts/cnki.mjs` 为例（下文简写 `cnki.mjs`），
输出一律是 JSON。

```bash
# 环境自检
node cnki.mjs status

# 基础检索（返回 total/page/papers 与 activeSort，papers 带 url 与 exportId）
node cnki.mjs search --query "深度学习"
node cnki.mjs search --query "深度学习" --sort citations   # 检索完直接排序

# 高级检索：字段 + 来源类别 + 年份 + 作者 + 期刊
node cnki.mjs advanced --query "脓毒症" --source CSSCI 北大核心 --from-year 2020 --to-year 2025 --sort citations
node cnki.mjs advanced --query "脓毒症" --field TI --query2 "早期预警" --field2 KY --logic AND
node cnki.mjs advanced --query "机器学习" --author "周志华" --journal "计算机学报"

# 对当前结果页：重解析 / 翻页 / 排序
node cnki.mjs parse
node cnki.mjs pages --action next
node cnki.mjs sort --by citations        # relevance date citations downloads comprehensive

# 单篇详情（摘要 / 作者 / 单位 / 关键词 / 基金 / 分类号 / DOI / ISSN）
node cnki.mjs detail --url "https://kns.cnki.net/kcms2/article/abstract?v=..."

# 导出引用：结果页批量（--indices 选篇）或详情页单篇
node cnki.mjs export --indices 1,3,5 --mode gbt --out .pipeline/literature/<corpus>/cnki_export.json

# 期刊检索与收录情况（北大核心 / CSSCI / CSCD / SCI / EI）
node cnki.mjs journal --name "计算机学报"

# 触发全文下载（需要登录），再把文件归档进语料库
node cnki.mjs download --format pdf
node cnki.mjs collect --title "<论文标题>" --into .pipeline/literature/<corpus>/papers
```

字段代码：`SU` 主题、`TI` 篇名、`KY` 关键词、`TKA` 篇关摘、`AB` 摘要、`AU` 作者、`FT` 全文。
来源类别：`SCI` `EI` `北大核心` `CSSCI` `CSCD`（可多选）。

**排序状态是跨检索保留的**（CNKI 页面行为）。一次 `search` 可能沿用上次的排序——
默认那次实测落在"发表时间"，结果全是当天网络首发。所以每个结果里都带 `activeSort` /
`activeSortDirection`，以它为准；想要相关度或被引就显式传 `--sort`。

排查取数为空时用 `CNKI_DEBUG_JS=1` 打出实际发到页面的脚本——proxy 只会回 "Uncaught"，
看不出哪行错。常见坑（reject 被吞成空对象、模板字符串反斜杠被吃掉、排序匹配方式）
都记在 `references/site-patterns/cnki.net.md` 的「实测踩到的坑」。这套选择器已于
2026-09-10 在真实浏览器 + 已登录机构账号下逐条复验。

## 在 survey 里的用法

CNKI 是**中文文献的补充源**，不是 arxiv/openalex 那类 API 源的替代。典型用法：

1. `search` / `advanced` 拿到结果页；
2. 用 `parse` 的 `papers` 数组给 `survey_screening.md` 补上中文候选行（标注来源 `cnki`）；
3. 用户勾选核心论文后，`detail` 补全元数据，`export` 出 GB/T 7714 引用串；
4. 要全文的，`download` 触发下载，`collect` 把 PDF 归档到
   `.pipeline/literature/<corpus>/papers/<slug>/paper.pdf`，再交给
   `literature-pdf-ocr-library` 的 OCR 脚本。

**全文中断点**：CNKI 的 PDF/CAJ 多数要机构权限，且 CAJ 不是标准 PDF、OCR 脚本读不了。
拿不到就按元数据保留在 bank 里，`full_text_status` 标 `needs_institution`，不要伪造来源。

## 与 `literature-pdf-ocr-library` 的分工

| 场景 | 用哪个 |
|------|--------|
| arXiv / S2 / OpenAlex / Crossref / PubMed 检索 | `literature-pdf-ocr-library` |
| 中文期刊、学位论文、知网独有的中文文献 | 本技能 |
| 期刊级别、收录数据库（北大核心/CSSCI）判断 | 本技能 `journal` |
| 有开放 PDF 的下载 + OCR 成 Markdown | `literature-pdf-ocr-library` |
| 只对登录用户开放的知网全文 | 本技能 `download` + `collect`，再交给 OCR 脚本 |

两边产出的元数据都写回同一张 `literature_bank.md` / `survey_screening.md`，cite_key 一律
由 `build_bibliography.py` 生成，**不要手写 bib 条目**。

## 参考文档

- `references/site-patterns/cnki.net.md` —— 已验证的 URL 与 DOM 选择器表、页面结构、验证码判定
- `references/workflows.md` —— 10 个上游工作流的完整步骤与踩坑记录

## 限制

- ❌ 不要在没有 Chrome 登录态的情况下改用 curl / WebFetch 抓 CNKI（会拿到验证码页或空页）
- ❌ 不要尝试自动解滑块验证码
- ❌ 不要把用户的知网账号、cookie、token 写进任何文件
- ❌ 不要宣称拿到了实际没下载成功的全文
- ✅ 撞到验证码、未登录、权限不足时，如实返回状态并让用户处理
