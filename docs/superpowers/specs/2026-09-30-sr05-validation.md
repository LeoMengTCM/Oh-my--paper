# SR-05 实施与验证记录

日期：2026-09-30。
从 Claude Code 会话 `2d69a494-9584-4307-b2b0-1090e7f70c07` 恢复：引用核验模块和基础交接测试已存在，
交接主脚本尚未实现。本轮完成写作交接工具、双插件入口、公开数值验证及回归检查。
真实临床综述端到端验收仍未完成。未提交、未推送、未修改版本号。

## 已实现

- `skills/systematic-review/scripts/writing_handoff.py check/build`：只读检查当前记录，向新目录导出交接材料。
- `handoff_records.py`：重新验证当前筛选、研究归并、分析计划与选中输入；核对运行快照、统计结果、研究身份和产物摘要。
- 旧计划、failed 运行、缺摘要或已改动的结果不能用于有效结果导出。只要仍有未解决运行，整项定量合成研究数保留 null。
- 多个 pooled 分析的研究数按 study_id 并集计算；单研究效应不计为 Meta；叙述性综合须记录理由和当前方案下的人类确认。
- 导出 handoff JSON/Markdown、计数、分析级与研究级 CSV、有效运行原文件、原引用键/BibTeX 和元数据快照。build 拒绝覆盖已有目录及写入原运行目录。
- 接入已有 `citation_records.py`：核对书目、BibTeX、原 metadata、报告身份及保存的 Crossref/人工核验记录。来源声明不能替代核验。
- research、software_validation、public_benchmark 分别登记；后两者不能获得真实研究的 ready_for_drafting。示例明确标为 software_validation。
- Claude/Codex 写作命令及 paper-writer 角色共同引用 `references/writing-handoff.md`，一致性检查覆盖两侧入口。
- `submission_readiness=not_assessed`，GRADE、临床解释、引用语境、PRISMA 报告和全文审稿继续列为 reporting_pending。

使用方式见 [写作交接说明](../../../skills/systematic-review/references/writing-handoff.md)。

## 公开数值验证

运行 `skills/systematic-review/examples/bcg-benchmark/run_benchmark.py`，读取已安装的
`metadat::dat.bcg`，以同一个 `pairwise_meta.R` 计算风险比 REML 模型。
参考为 Viechtbauer (2010), *Conducting Meta-Analyses in R with the metafor Package*,
JSS 36(3), DOI [10.18637/jss.v036.i03](https://doi.org/10.18637/jss.v036.i03)，PDF 第 14 页。
参考值与容差已写入示例的 reference.json；不以被测函数生成期望值。

| 指标 | 论文参考值 | 实际运行 | 绝对容差 |
|---|---:|---:|---:|
| 研究数 | 13 | 13 | 0 |
| 合并 log RR | -0.7145 | -0.7145323484 | 0.00005 |
| 标准误 | 0.1798 | 0.1797815318 | 0.00005 |
| log RR 区间下界 | -1.0669 | -1.0668976757 | 0.00005 |
| log RR 区间上界 | -0.3622 | -0.3621670210 | 0.00005 |
| tau² | 0.3132 | 0.3132433260 | 0.00005 |
| I² (%) | 92.2214 | 92.2213860750 | 0.00005 |
| Q | 152.2330 | 152.2330080824 | 0.00005 |

8 项全部匹配。已目视检查实际森林图 PNG：研究标签、单项区间和合并菱形清楚，
RR 展示为比值、横轴为对数坐标，图题明确标识公开数值基准和混合分配方式。

本轮重新请求该 DOI 的 Crossref API，保存原响应，经现有书目生成器及引用核验模块检查，
得到 `viechtbauer2010conducting`、`crossref_snapshot_checked`，无 blocker。
匹配字段为题名、作者、年份和 DOI；不宣称完成引用语境核查。

实际环境：R 4.6.0、metafor 5.2.1、jsonlite 2.0.0、metadat 1.6.0（包描述版本 1.6-0）。
metadat 许可为 GPL (>= 2)。仓库不重新分发原数据表或论文 PDF，示例运行时从已安装公开包读取。

该数据包含 7 random、2 alternate、4 systematic。示例不生成人工筛选、批准、RoB 2 或临床运行清单，
始终标为 public_benchmark，ready_for_drafting=false。它验证数值内核，不替代纯 RCT 临床综述验收。

## 回归验证

使用既有隔离 R 库，设置 R_LIBS_USER 和 OMP_REQUIRE_R=1 后运行 `npm run check`：

- 44 个研究技能目录与生成内容一致。
- 10 类插件一致性检查通过。
- Node 测试 15 项通过；Python 测试 116 项通过。
- **合计 131 项，通过 131，跳过 0，失败 0。**
- 交接测试包括当前完整记录、计划/输入失效、产物改动、缺必要摘要、failed 运行、研究身份错误、研究并集、重复运行、筛选缺口、引用缺口、用途限制、叙述性综合和目录保护。
- 实际 R 的 pooled 与 single_study 运行均通过 build 导出；公开基准也接入测试入口。
- `git diff --check` 及新增 Python 入口语法检查通过。

全量检查还发现原 PubMed 传输模块未关闭 HTTPError 响应。Python 3.14 的资源回收警告可能包含
错误对象中的请求信息，使已有凭证保护测试失败。现已在重试或提前退出前关闭响应；
新增回归覆盖 400、429 长等待和 503 重试，PubMed 23 项测试全部通过。

## 后续仍需完成

真实 RCT 综述端到端验收需要合法原文、实际检索与纳排记录、真实研究归并、人工提取核对和方法学判断。
本轮没有提供或伪造这些材料。SR-03 的真实 PubMed 服务与大查询验收、其他数据库恢复、
自动原文提取、GRADE 和正式 PRISMA 图也仍待完成。

检查通过证明本工具覆盖的结构和一致性条件满足，不证明研究真实性、人员身份或临床结论有效。
本轮仅完成本地检查，未触发远端 CI 或发布。
