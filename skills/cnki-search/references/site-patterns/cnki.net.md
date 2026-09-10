---
domain: cnki.net
aliases: [CNKI, 中国知网, 知网]
updated: 2026-09-10
---

> 选择器与 URL 结构来自上游 [cookjohn/cnki-skills](https://github.com/cookjohn/cnki-skills)
> @ `20d65f660456daf53ad0f7c74494ac3b829b925f`，上游标注为"已验证"。本仓库把它们搬进
> `scripts/cnki.mjs` 时**未做逐条实机复验**——CNKI 改版后如果取数为空，先怀疑选择器，
> 用 Chrome DevTools 重新核对后再更新本文件和脚本。

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

| 数据 | 选择器 | 备注 |
|------|--------|------|
| 检索输入框 | `input#txt_search` | 兜底 `input[type=text]` |
| 检索按钮 | `input.researchbtn` | 兜底 `input[type=button]` |
| 收录数据库 | 详情页 "该刊被以下数据库收录" | 等待文本出现 |

期刊详情页在**新标签页**打开，需要 `list_pages` + 切标签。`cnki.mjs` 的 `journal` 命令
只解析当前页文本，收录信息见返回的 `bodyText`。

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
