---
domain: cnki.net
aliases: [CNKI, 中国知网, 知网]
updated: 2026-09-10
verified: 2026-09-10
---

> 选择器与 URL 结构来自上游 [cookjohn/cnki-skills](https://github.com/cookjohn/cnki-skills)
> @ `20d65f660456daf53ad0f7c74494ac3b829b925f`。
>
> **2026-09-10 在真实浏览器 + 已登录机构账号下逐条复验过**（Chrome 152 /
> `kns8s/search` + `kns/AdvSearch` + `navi.cnki.net` 三处界面），含 `download`
> 与 `collect` 的完整下载链路（实下 PDF 与 CAJ 各一份并归档）。本文件里标了
> "实测"的都是那天验证的结论；下方「实测踩到的坑」一节是那次验证的主要产出，
> 多数是上游文档里没有、但踩了必炸的问题。CNKI 改版后如果取数为空，先怀疑选择器，
> 用 `CNKI_DEBUG_JS=1` 打出实际发出的脚本比对。

## 平台特征

- 中文文献、学位论文、期刊目录的主要来源；**无公开 API**
- 反爬：腾讯滑块验证码 + 登录态校验。只能走用户自己的 Chrome（CDP），
  天然携带 cookie 与机构权限
- 不要尝试：WebFetch、curl、任何第三方 CNKI 接口——会拿到验证码页或空页
- 检索站在 `kns.cnki.net`，期刊导航站在 `navi.cnki.net`，两套 DOM 完全不同

## 关键 URL

| 用途 | URL |
|------|-----|
| 首页 | `https://www.cnki.net` |
| 基础检索 | `https://kns.cnki.net/kns8s/search` |
| 高级检索（旧版） | `https://kns.cnki.net/kns/AdvSearch?classid=7NS01R8M` |
| 期刊导航 | `https://navi.cnki.net/knavi` |
| 导出 API | `https://kns.cnki.net/dm8/API/GetExport` |

**高级检索必须用旧版 URL**（`kns.cnki.net/kns/AdvSearch`）。新版 `kns8s/AdvSearch` 没有
来源类别复选框（SCI / EI / 北大核心 / CSSCI / CSCD）。`classid=7NS01R8M` 保证加载正确表单。

## 验证码判定

腾讯滑块 SDK 会**预加载** DOM 到 `top: -1000000px`（屏幕外，非激活）。只有
`getBoundingClientRect().top >= 0` 才是真的挡在用户面前：

```javascript
const el = document.querySelector('#tcaptcha_transform_dy');
const active = !!(el && el.getBoundingClientRect().top >= 0);
```

只看元素是否存在会误判成"有验证码"。`cnki.mjs` 里所有命令都用这个判定。

## 检索结果页选择器

`.result-table-list tbody tr` 是每篇论文一行。行内按列取：

| 数据 | 选择器 | 备注 |
|------|--------|------|
| 标题 | `td.name a.fz14` | 论文标题链接，`href` 即详情页 |
| 网络首发 | `td.name .marktip` | 存在则标 `[网络首发]` |
| 作者 | `td.author a.KnowledgeNetLink` | 多个，`;` 连接 |
| 来源期刊 | `td.source a` | |
| 日期 | `td.date` | |
| 数据库类型 | `td.data` | 期刊 / 学位论文 / 会议 |
| 被引 | `td.quote` | |
| 下载 | `td.download` | |
| 序号 | `td.seq` | |
| 复选框 | `input.cbItem` | **value 就是详情页的 `#export-id`** |
| 结果总数 | `.pagerTitleCell` | 文本"共找到 X 条结果" |
| 页码 | `.countPageMark` | 文本 "1/300" |
| 分页链接 | `.pages a` | 数字 + 上一页 / 下一页 |
| 当前页 | `.pages a.cur` | |
| 排序容器 | `#orderList li` | 点击即切换排序 |

排序项 ID：`#FFD` 相关度、`#PT` 发表时间、`#CF` 被引、`#DFR` 下载、`#ZH` 综合。
当前生效项带 `.cur`。

**排序项一定要按文本匹配，不要按 id 或序号**（实测）：

| | 新版 `kns8s/search` | 旧版 `kns/AdvSearch` |
|---|---|---|
| `li` 有没有 `id` | 有（FFD/PT/CF/DFR/ZH） | **没有** |
| 5 项顺序 | 相关度/发表时间/被引/下载/综合 | 相关度/发表时间/被引/**综合/下载**（后两项对调） |
| 当前项标记 | `class="DESC cur"` | `class="DESC cur"` |

所以按 id 匹配会在旧版界面上直接失配（`"" === "CF"` 恒为 false），按序号匹配会把下载和综合搞反。
统一用 `Array.from(document.querySelectorAll('#orderList li')).find(e => e.innerText.trim() === '被引')`。
升降序在 `class` 里（`ASC` / `DESC`），不是独立的控件。

## 高级检索表单选择器（旧版界面）

用 `Array.from(document.querySelectorAll('select')).filter(s => s.offsetParent !== null)`
取可见 select 后按下标访问，下面是实测下标：

| 字段 | 选择器 / 下标 | 取值 |
|------|--------------|------|
| 行1 字段类型 | `selects[0]` | `SU` 主题 / `TI` 篇名 / `KY` 关键词 / `TKA` 篇关摘 / `AB` 摘要 |
| 行1 关键词 | `#txt_1_value1` | |
| 行1 行内逻辑 | `selects[2]` | AND 并含 / OR 或含 / NOT 不含 |
| 行1 行内第二词 | `#txt_1_value2` | |
| **行间逻辑** | `selects[5]` | AND 并且 / OR 或者 / NOT 不含 |
| 行2 字段类型 | `selects[6]` | 同 `selects[0]` |
| 行2 关键词 | `#txt_2_value1` | |
| 作者 | `#au_1_value1` | |
| 作者单位 | `#au_1_value2` | |
| 文献来源 | `#magazine_value1` | 期刊名 / ISSN / CN |
| 基金 | `#base_value1` | |
| 起始年 | `selects[14]` / `#startYear` | select，1915–2026 |
| 结束年 | `selects[15]` / `#endYear` | select，2026–1915 |
| **检索按钮** | `div.search` | **不是** input/button，是 div |

来源类别复选框（多选为 OR 关系）：

| 来源 | Checkbox ID |
|------|-------------|
| 全部期刊（默认勾选） | `#gjAll` |
| SCI 来源期刊 | `#SCI` |
| EI 来源期刊 | `#EI` |
| 北大核心 | `#hx` |
| CSSCI | `#CSSCI` |
| CSCD | `#CSCD` |

**选其他来源前必须先取消 `#gjAll`**，否则筛选不生效。

## 论文详情页选择器

主容器 `.brief`。不在这个容器里说明当前不是详情页。

| 数据 | 选择器 | 备注 |
|------|--------|------|
| 标题 | `.brief h1` | 需去掉尾部"附视频"/"网络首发" |
| 作者 | `.brief h3.author:first-of-type a` | 文本末尾带上标数字，如"张三1" |
| 单位 | `.brief h3.author:nth-of-type(2) a` | 文本形如"1.北京大学" |
| 摘要 | `.abstract-text` | |
| 关键词 | `p.keywords a` | 分号分隔 |
| 基金 | `p.funds` | |
| 分类号 | `.clc-code` | 中图分类号 |
| 期刊 | `.doc-top a` | |
| 出版信息 | `.head-time` | |
| 网络首发标识 | `.brief .icon-shoufa` | 存在即网络首发 |
| 目录 | `.catalog-list, .catalog-listDiv` | |
| 引证统计 | `ul.module-tab.tpl_lieteratures li` | `data-id` 区分类型，文本含数量 |
| 导出 ID | `#export-id` | 导出 API 的 `filename` 参数 |
| 导出 URL | `#export-url` | 仅详情页有 |
| PDF 下载 | `#pdfDown` | `li.btn-dlpdf` 内的 `<a>` |
| CAJ 下载 | `#cajDown` | `li.btn-dlcaj` 内的 `<a>` |
| 未登录 | `.downloadlink.icon-notlogged` | 命中即需登录 |

## 导出 API

```
POST https://kns.cnki.net/dm8/API/GetExport
Content-Type: application/x-www-form-urlencoded

filename=<加密ID>&displaymode=GBTREFER,elearning,EndNote&uniplatform=NZKPT
```

- `filename` 必须是**加密 ID**：详情页取 `#export-id`，结果页取 `input.cbItem` 的 value
  （两者相等）。**不是** `#paramfilename`。
- 必须在页面内用 `fetch` 调用（带 cookie），不能从命令行直接 curl。
- 返回 `{code: 1, data: [{mode, value: [...]}]}`，`code !== 1` 即失败。
- `GBTREFER` 是 GB/T 7714 引用串，`ENDNOTE` 里 `%@` 字段是 ISSN，`elearning` 字段最全。

## 期刊导航站（navi.cnki.net）

实测（2026-09-10）：

| 数据 | 选择器 | 备注 |
|------|--------|------|
| 检索输入框 | `input#txt_1_value1` | class `rekeyword`，placeholder "请输入检索词" |
| 检索按钮 | `input#btnSearch` | class `researchbtn` |
| 字段类型下拉 | `select#txt_1_sel` | 来源名称 / 主办单位 / ISSN / CN 等 |
| 结果容器 | `#searchResult` | 即 `.sort.jsResult` |
| 结果条目 | `#searchResult dl.result` | 每条一个 `dl`，内含 `.re_brief` |

**⚠️ 不要用 `input[type=text]` 兜底检索框**。navi 页面上所有其他可见 `type=text` 输入框
都是登录框（`oauth1-name` 手机号、`ecp_userName` 用户名、`ecp_phone` 等），兜底会填错地方。

**⚠️ 点检索按钮会整页跳转**。点击后执行上下文被销毁，await 永远不 resolve，
表现为 CDP `Runtime.evaluate` 超时。必须拆成两次求值：先填词点击并**立刻返回**，
在 Node 侧 `sleep` 几秒，再起一次求值解析结果。

期刊名别按 `input#txt_search` 找（那个 id 在新版 navi 上不存在）；收录数据库、影响因子、
ISSN/CN 都在结果页正文里，`cnki.mjs journal` 返回的 `bodyText` 是主要交付物。
详情页 URL 形如 `navi.cnki.net/knavi/detail?p=...`，在 `items[].url` 里。

## 实测踩到的坑（2026-09-10）

这一节是那次实机验证的主要产出，多数在上游文档里没有，但踩了必炸。

### 1. CDP proxy 会把「被拒绝的 promise」吞成空结果

`cdp-proxy.mjs` 的 `/eval` 对各种返回的处理（实测）：

| 页面脚本 | proxy 返回 |
|---------|-----------|
| resolve 一个对象 | HTTP 200 `{"value": {...}}` |
| resolve `undefined` | HTTP 200 `{"result":{"type":"undefined"}}` |
| promise 被 reject | HTTP 400 `{"error":"Uncaught (in promise) Error: ..."}` |
| 同步抛错 | HTTP 400 `{"error":"Uncaught"}` |

**这个 reject 分支曾经是坏的**（本次验证时修掉，见 `cdp-proxy.mjs` 文件头的改动说明）：
原实现先判 `result.value !== undefined` 再判 `exceptionDetails`；而 promise 被 reject 时
Chrome 会**同时**返回 exceptionDetails 和一个 result（被抛出的 Error 对象），Error 在
`returnByValue` 下序列化成 `{}` 是 defined，于是返回 HTTP 200 + `{"value":{}}`——
页面里的报错被静默吞成"空结果"。上游那套"超时就 reject"的写法搬过来后，排序超时会
静默返回空结果，看起来像成功。

现在 proxy 已修，但仍然保持两条规矩（纵深防御，也防止将来 proxy 被换回旧版）：

- 页面脚本里**一律不 reject**。用 `waitUntil(pred, tries, label)` 返回 `{ok, label}`，
  调用方自己判断（见 `scripts/cnki.mjs` 的 `WAIT_HELPER_JS`）。
- `evalJs` 里对空对象 `{}` 直接报错兜底。

### 2. 模板字符串里的反斜杠会被吃掉

页面脚本是 JS 模板字面量。`\s` 在模板字面量里不是合法转义，反斜杠会被丢掉变成 `s`，
于是 `/<br\s*\/?>/` 静默变成 `/<brs*\/?>/`——**语法合法、语义全错**，而且不会报错。
正则里要写成 `\\s`。用 Python/脚本批量改写这段代码时尤其容易踩。

### 3. 弹出的排序刷新信号不是页标记

排序后仍停在第 1 页，`.countPageMark` 一直是 `1/300`。等它变化必然超时。
改用**首行标题变化**当刷新信号。

### 4. 点已激活的排序项是空操作

新版界面下再次点击当前生效的排序项**不会反转升降序**（实测确认页面无跳转、标记不变、
首行不变）。所以已经是目标排序时直接跳过点击，别赌。

### 5. 排序状态跨检索保留

CNKI 会记住上次的排序。实测一次 `search` 默认落在"发表时间"上，结果全是当天网络首发；
显式切到"被引"之后，后续检索都保持"被引"。所以**每次解析都要带上 `activeSort`**，
否则"相关度检索"可能实际拿到的是按时间排的结果。

### 6. 被引/下载为空多半不是选择器坏了

`td.quote` / `td.download` 单元格确实存在，只是 CNKI 对新论文不显示计数。
判断选择器是否失效要看**单元格是否存在**，不是看文本是否为空。

### 7. 其他零碎

- 作者上标有 `1`、`1,2`、`1,2,` 三种写法，剥名字时数字和逗号要一起处理。
- 导出串（GBTREFER / ENDNOTE）带 `<br>` 标签，落盘前要清掉。
- `#orderList` 只在有结果时才出现，空白检索页上取到 0 项是正常的。
- 调试时用 `CNKI_DEBUG_JS=1` 把实际发到页面的脚本打到 stderr；proxy 只回
  "Uncaught" 三个字，看不出哪行错了。（脚本还会先在本机 `new Function()` 过一遍语法。）
- 多个 `kns.cnki.net` 标签页会同时存在，`ensureCnkiTab` 取最后一个；调试时别用
  `.pop()` 想当然，先列 `/targets` 确认。

### 8. 下载链接是 `target="_blank"`，会被弹出拦截器静默挡掉

`#pdfDown` / `#cajDown` 都带 `target="_blank"`。CDP 的 `Runtime.evaluate` 默认
**不带用户手势**，脚本里 `a.click()` 触发的开新窗口会被 Chrome 判定为弹窗并拦截——
而且拦得悄无声息：没有新标签、没有报错、没有下载，`window.open()` 只是返回 `null`。

`cdp-proxy.mjs` 的 `/eval` 与 `/click` 已补 `userGesture: true`（见该文件头「本地改动 2」）。
实测对照：未加时 `window.open("about:blank")` 返回 `null`，加上后正常打开，
`download` 也才开始真的下载。**如果将来下载又变成"点了没反应"，先查这个参数。**

### 9. CAJ 是 `KDH 2.00` 私有格式，不是 PDF

实测下载到的 `.caj` 文件头是 `KDH 2.00 Copyright`，`pdfinfo` 直接报
"Couldn't find trailer dictionary"。文库的 OCR 管线（`paddleocr_layout_to_markdown.py`）
只吃 PDF，所以**能下 PDF 就别下 CAJ**。`collect` 在两者同时存在时会优先挑 PDF。

### 10. `collect` 的标题匹配不能"猜"

下载来的文件名形如「标题_作者.pdf」。实测两种会归档错文件的情况：

| 情形 | 曾经的行为 | 现在的行为 |
|------|-----------|-----------|
| 标题匹配不到任何文件 | **静默归档最近下载的那个** | 报错并列出目录里实际有什么 |
| 多个文件都含该标题（如「深度学习」对上「深度学习综述_李四.pdf」） | **静默取最新的** | 精确匹配（标题部分完全一致或紧接 `_`）优先；仍歧义则报错 |

两种旧行为都返回退出码 0，语料库里会出现标题与正文对不上的条目，从输出上看不出来。
另外 `collect --file "<文件名>"` 可以跳过匹配直接指定。

### 11. 「题录」记录下载区整块不存在

知网有一部分文献**只有题录、没有全文**。这类页面的 `<h1>` 会带一个「题录」后缀
（tab 标题里没有，只有页面内 `h1` 有），而且**页面上完全没有下载区**——实测
`#pdfDown`、`#cajDown`、`.btn-dlpdf`、`#DownLoadParts` 全部缺席。

这必须和「有按钮但要机构权限」分开报：前者登录、换权限都没用，后者登录就能解决。
把它们混成一句"可能不提供或需要权限"，会让用户白跑一趟登录。

`h1` 里的「题录」后缀要剥掉再返回，否则 `detail` 的标题和 `search`/`parse` 的对不上，
拿它去 `collect --title` 会匹配失败。

### 12. 详情页的出版年份在 `.doc-top`，不在 `.head-time`

`DETAIL_JS` 原来从 `.head-time` 取 `pubInfo`，实测这个节点**经常是空的**。真正的出版信息
在 `.doc-top` 里，形如：

```
计算机应用 . 2021 ,41 (S1) : 332-335 查看该刊数据库收录来源
```

年份、卷、期、页码都在这一行。所以 `detail` 另外返回一个 `citation` 字段（不混进
`pubInfo` 改变它的语义），`collect --meta` 归一化时按 `date` → `citation` → `pubInfo`
的顺序找年份。

### 13. `detail` 不记标签页会导致 `download` 跑错页面

survey 的流程是 `detail --url` 紧跟 `download`（不带 `--url`），而 `download` 靠
`rememberedTarget()` 找标签页、`rememberTarget()` 原来只有 `search`/`advanced` 会调——
于是 `download` 回到检索结果页，等 15 秒 `.brief h1` 超时。`detail` 现在也会记住。

同类的还有标签页堆积：`download --url <新论文>` 原来每篇开一个新标签，跑一轮调研能堆
几十个。现在 `download` 带上 `anyCnki`，变成「该论文开着就复用 → 否则复用上次用过的标签
并导航过去 → 都没有才开新的」。实测连下 10 篇标签数不增长。

### 14. `timeout` 曾经带着退出码 0 出去

`cmdDownload` 原来只处理 `not_logged_in` / `captcha` / `no_download_link` 三种错误，
其余（包括 `timeout`）会掉进最后的 `emit({...result, downloadDir, hint})`——
**退出码 0，还贴上了看起来像"已触发下载"的 hint**。现在任何 `error` 都走 `fail()`。

### 15. 中文作者名会让引用键退化成 `anon`

`build_bibliography.py` 的 `derive_lastname` 只认拉丁字母（`[A-Za-zÀ-ɏ]`），
`first_title_word` 同样只认 `[A-Za-z]+`。所以纯中文的论文会得到
`anon<年份>paper` 这样的键——实测一篇「龚欢欢」等作者的论文拿到 `anon2023mimic`
（mimic 来自标题里的 `MIMIC-Ⅳ`），纯中文标题则会是 `anon<年>paper`。

键不会真的冲突（重复时按 `a`/`b`/… 加后缀并写回 `metadata.json`），但键没有信息量，
而且 CNKI 语料全是中文作者时，同年同模式的论文会集中落进同一个前缀。要改得动
`build_bibliography.py` 的键生成策略，属于另一个技能的取舍（CJK 字符进 BibTeX 键
有兼容性代价），这里只记现象。

### 16. CNKI 的 PDF 有文字层，但数字与标点是全角

实测下载的 PDF：CJK 字体未嵌入、编码 `GBK-EUC-H`、无 Unicode 映射，`pdffonts`
三列全是 `no`；不过**文字层是有的**，`pdftotext` 能取到正文（第 3 页 6649 字符）。
代价是取出来的数字和标点是**全角**的（页码 `７５７`、句点 `．`）。
下游若用 `[0-9]`、`\.` 之类的正则做年份/卷期/页码抽取，要先做 NFKC 归一化，否则匹配不上。

## 已知陷阱

- **别点标题链接**：CNKI 的链接常在新标签打开，直接 `navigate` 到 `href` 更省事（少 3 次
  标签管理调用）。
- **UID 每次加载都变**：上游用 snapshot 时需要重新取；本仓库走 DOM 选择器，不受影响。
- **翻页/排序要等**：靠 `.countPageMark` 文本发生变化来判断完成，别用固定 sleep。
- **操作要有节奏**：快速连续翻页更容易触发滑块。
- **CAJ 不是 PDF**：文库 OCR 脚本读不了 CAJ，能选 PDF 就选 PDF。
- **下载落在 Chrome 下载目录**：CDP 拿不到下载路径（页面 JS 无从得知），所以
  `cnki.mjs download` 只触发，之后用 `cnki.mjs collect` 按标题把文件归档进语料库。
- **结果页与详情页是两套选择器**：结果页用 `td.name a.fz14`，详情页用 `.brief h1`，
  不要混用。
