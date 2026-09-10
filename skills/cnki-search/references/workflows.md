# CNKI 工作流

上游 [cookjohn/cnki-skills](https://github.com/cookjohn/cnki-skills) 把 CNKI 拆成 10 个
chrome-devtools MCP 技能。本仓库合并为一个技能，每个上游技能对应 `cnki.mjs` 的一个
子命令。下表是映射，后面是各工作流的完整步骤。

| 上游技能 | 本仓库对应 | 说明 |
|---------|-----------|------|
| `cnki-search` | `cnki.mjs search` | 关键词检索，一次调用返回结果表 |
| `cnki-advanced-search` | `cnki.mjs advanced` | 字段 + 来源类别 + 年份 + 作者 + 期刊 |
| `cnki-parse-results` | `cnki.mjs parse` | 重解析当前结果页 |
| `cnki-navigate-pages` | `cnki.mjs pages` / `sort` | 翻页与排序 |
| `cnki-paper-detail` | `cnki.mjs detail` | 单篇完整元数据 |
| `cnki-download` | `cnki.mjs download` | 触发 PDF/CAJ 下载 |
| `cnki-export` | `cnki.mjs export` | 引用导出（批量 / 单篇） |
| `cnki-journal-search` | `cnki.mjs journal` | 期刊检索 |
| `cnki-journal-index` | `cnki.mjs journal` | 收录情况（返回 `bodyText` 供解析） |
| `cnki-journal-toc` | `cnki.mjs toc` | 期刊目录 |
| `cnki-researcher`（agent） | 无 | 上游用来编排 10 个技能的 agent；本仓库由 `/omp:survey` 与 literature-scout agent 承担 |

## 1. 关键词检索

```bash
node cnki.mjs search --query "深度学习"
```

一次调用完成：打开 `kns8s/search` → 等搜索框 → 检查验证码 → 填词提交 → 等"条结果"出现
→ 解析整页表格。返回 `{query, total, page, papers[]}`。

`papers[]` 每项含 `n / title / url / exportId / authors / journal / date / database /
citations / downloads / onlineFirst`。`exportId` 要留着，导出时用得上。

**追问**：用户想打开某篇时，直接用 `papers[i].url` 传给 `detail --url`，
不要去点标题链接（会开新标签）。

## 2. 高级检索

```bash
# 主题=脓毒症，且限定 CSSCI 或北大核心，2020 年起
node cnki.mjs advanced --query "脓毒症" --source CSSCI 北大核心 --from-year 2020

# 篇名含"脓毒症" AND 关键词含"早期预警"
node cnki.mjs advanced --query "脓毒症" --field TI \
  --query2 "早期预警" --field2 KY --logic AND

# 限定作者与期刊
node cnki.mjs advanced --query "机器学习" --author "周志华" --journal "计算机学报"
```

自然语言需求先拆成字段再传参：主题 / 篇名 / 关键词 / 作者 / 文献来源 / 时间范围 /
来源类别。来源类别只支持 `SCI` `EI` `北大核心` `CSSCI` `CSCD`，多选是 OR 关系。

## 3. 翻页与排序

```bash
node cnki.mjs pages --action next        # prev / page:3
node cnki.mjs sort --by citations        # relevance date citations downloads comprehensive
node cnki.mjs search --query "X" --sort citations   # 检索完直接排好，省一次调用
node cnki.mjs advanced --query "X" --sort citations
```

两者都基于"当前结果页"，会复用已有的 `kns.cnki.net` 标签。翻页靠 `.countPageMark` 变化
判断；**排序不能用它**（排序后仍在第 1 页，标记不变），改用首行标题变化。

**排序状态是跨检索保留的**，所以每次返回都带 `activeSort` / `activeSortDirection`，
以它为准，不要默认检索结果就是按相关度排的。已经是目标排序时命令会返回
`sortResult: already_active` 并跳过点击（新版界面点已激活项是空操作）。

**批量取多页时**：逐页 `pages --action next`，每页之间留出间隔，别连续猛翻。

（排序项必须按文本匹配，新版/旧版界面的 id 与顺序都不一样，细节见
`site-patterns/cnki.net.md`。）

## 4. 论文详情

```bash
node cnki.mjs detail --url "https://kns.cnki.net/kcms2/article/abstract?v=..."
```

返回标题、作者（含单位编号）、单位、摘要、关键词、基金、中图分类号、期刊、出版信息、
网络首发标识、目录、DOI、ISSN、`exportId`。

`error: not_a_detail_page` 表示当前页不是详情页——给 `--url`，或先在 Chrome 里打开。

## 5. 引用导出

**结果页批量**（推荐，N 篇只要一次调用）：

```bash
node cnki.mjs export --indices 1,3,5 --mode gbt \
  --out .pipeline/literature/<corpus>/cnki_export.json
```

不给 `--indices` 就导出当前页全部。返回 `papers[]`，每篇含 `GBTREFER`（GB/T 7714 引用串）、
`ENDNOTE`、`elearning`、`issn`、`pageUrl`。加 `--mode gbt` 会额外给一份 `citations[]`
只含引用串的数组。

**详情页单篇**：在详情页直接跑 `node cnki.mjs export --mode gbt`。

`--out` 写的是完整 JSON（含各格式原文）；引用串在 `citations` 字段里。

## 6. 期刊检索与收录查询

```bash
node cnki.mjs journal --name "计算机学报"
```

返回 `items[]`（命中期刊，含 `name` / `url`，`url` 是 `navi.cnki.net/knavi/detail?p=...`）、
`bodyText`（结果页正文前 4000 字，**收录数据库与影响因子都在这里**）、`captcha` 标志。

回答"这本刊是不是核心期刊"这类问题时：先 `journal` 拿到 `bodyText`，再从里面读
主办单位 / ISSN / CN / 复合影响因子 / 综合影响因子 / 被引次数，以及收录情况。
**不要把页面没写的指标补上去。**

实现上要点：检索按钮会触发整页跳转，所以命令拆成两次求值（填词点击 → 等 → 解析）；
检索框是 `#txt_1_value1`，不是 `input#txt_search`（那个 id 在新版 navi 上不存在）。
细节见 `site-patterns/cnki.net.md`。

## 7. 期刊目录

```bash
node cnki.mjs toc --journal "计算机学报" --year 2025 --issue 01
```

解析当前期刊页上的年份/期号链接与文章列表。完整流程需要先在 Chrome 里进到该刊详情页；
本命令只解析当前页面，`issues[]` 给可选期号，`paperRows[]` 给当期文章。

## 8. 全文下载与归档

```bash
node cnki.mjs download --format pdf
node cnki.mjs collect --title "<论文标题>" --into .pipeline/literature/<corpus>/papers
```

`download` 只在详情页触发浏览器下载，**文件落在 Chrome 的下载目录**（CDP 拿不到路径，
页面 JS 也无从得知）。实测 PDF 约 4–5 秒落盘，CAJ 更久。所以紧接着用 `collect` 按标题在
下载目录里找最近 N 分钟内的 PDF/CAJ，移动到 `--into/<标题slug>/paper.pdf`，
**并在同一目录写出 `metadata.json`**。

`metadata.json` 这一份不能省：`build_library_index.py` 与 `build_bibliography.py` 都是按
`papers/*/metadata.json` 遍历的，缺了就安静地报 0 篇、退出码 0，CNKI 下的全文永远进不了
索引和引用链。`collect --meta <detail输出的json>` 把年份/作者/期刊一并写进去；没有 `--meta`
也能跑，但缺 `year`/`authors` 的记录会被 `build_bibliography.py` 判为不可引用（显式 skip）。

常见中断（都以退出码 2 返回）：

| 返回 | 含义 | 处理 |
|------|------|------|
| `not_logged_in` | 没登录知网 | 让用户在 Chrome 里登录后重试 |
| `captcha` | 滑块拦住了 | 让用户手动完成拼图 |
| `record_only` | **只有题录、没有全文** | 页面上连下载区都没有（`#pdfDown` / `#cajDown` / `.btn-dlpdf` 全缺席）。登录或换权限都没用；保留元数据，`full_text_status` 标 `needs_institution` |
| `no_download_link` | 页面上没有下载区 | 通常是该文献确实未提供全文，与该文献需要权限不是一回事 |

CAJ 不是 PDF，OCR 脚本读不了；能下 PDF 就下 PDF。

## 9. 与 survey 的衔接

survey 第二步（方向确认）把 CNKI 列为可选源，用户选中文文献时：

1. `advanced` 或 `search` 检索，把 `papers[]` 转成 `survey_screening.md` 的行，
   数据源标 `cnki`；
2. 用户勾选后，`detail` 补元数据；
3. `export --mode gbt` 出引用串，供 `refs/references.bib` 对照；
4. 需要全文的走第 8 节，PDF 到手后交给 `literature-pdf-ocr-library` 的
   `paddleocr_layout_to_markdown.py`。

**cite_key 一律由 `build_bibliography.py` 生成**，不要为了 CNKI 单独手写 bib 条目。
