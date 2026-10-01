# RCT 干预疗效系统综述：成对 Meta profile

适用于 `pipeline.track=systematic-review` 的 RCT 干预疗效综述。Claude/Codex 共用本文件；其他综述类型先确认方法学方案，不自动套用本 profile。已有 SR-01 入口规则、SR-02 只读记录校验/计数、SR-03 PubMed 分批恢复、SR-04 受限范围的统计适配器和 SR-05 写作交接工具；真实 API、大查询、原文提取与真实研究验收尚未完成。

## 入口路由

先读 `.pipeline/docs/research_brief.json`、现有方案与研究者确认记录。

- **exploratory-search**：方案未批准，或用户明确要求可行性调研。可以精选阅读，明确注明不是正式系统检索或纳入研究集；没有方案时不自行进入正式筛选。
- **formal-review**：用户批准了具体版本的 `protocol.md` 和 `sap.md`，登记真实注册状态，且本次任务明确是正式综述。不得继续通用 survey 的 `--limit 30`、按引用挑 5–10 篇、核心期刊筛选或按全文是否可下载决定纳入的流程。
- 已批准方案但用户只要求探索时仍走 exploratory-search，不能把探索记录混入正式筛选计数。

模式不是 `analysisMode`：把分析改为 exploratory 不能绕过正式综述的方案确认与筛选记录。

## 五阶段与命令职责

| 阶段 | SR 内容 |
|---|---|
| survey | 探索性检索、已有综述核查、可行性判断 |
| ideation | PICO、纳排标准、检索策略、结局与时间窗、SAP、研究者批准与注册记录 |
| experiment | 正式检索/导入、去重、筛选、研究归并、提取、RoB 2、可合并性判断和分析 |
| publication | GRADE、Summary of Findings、PRISMA、证据核查与写作 |
| promotion | 按需准备汇报，不是研究完成的前置条件 |

- survey 命令在 formal-review 模式只执行正式检索子任务，归属 experiment；结束后返回筛选工作，不走通用 gap/idea 循环。
- ideate 命令在本 profile 中制定或修订研究方案，不生成五个算法创新点、不按已有显著结果修改结局。
- experiment 命令按下面的前置检查执行，不套用 ML 的达标迭代或强制消融。
- plan、review 与相关 agent 使用同一规则，不能因任务 `done` 就假定研究证据齐全。

## 方案、批准与注册

沿用 `.pipeline/docs/protocol.md`、`sap.md`。结构化项目按 `review-records.md` 在 `.pipeline/systematic-review/approvals.jsonl` 登记人工批准的具体版本、人员、时间和适用范围；`decision_log.md` 保存摘要与引用，不能另行维护相互矛盾的批准状态。旧项目原有批准记录先人工核对，再经用户同意转换，不自动迁移。变更继续记入 `protocol_deviations.md`。

只读 CLI 检查所登记的版本、角色、文件和决定关系，不认证真实人员，不证明实际作出过批准；不能把文件字段当作电子签名。修改方案正文须同步升级版本。

方案至少包含 PICO、资格标准、数据库与完整检索式、检索范围、主要/次要结局、时间窗、人群、比较、效应方向、缺失数据规则、统计模型、零事件处理、预设亚组和敏感性分析。

注册状态逐项如实记录：`planned`、`submitted`、`registered`、`not_registered`、`not_applicable`。只有 verified 注册信息才能写 registered；未注册/不适用需说明理由，提交未完成不能写成已注册。注册优先在正式筛选前完成，但未注册不自动否定系统综述的性质；用户确认继续时保留真实时间顺序和局限，不倒填前瞻性注册。

公开汇总数据综述不默认要求 IRB；涉及非公开或个体参与者数据时先核实适用审批与授权。不能替用户注册、同意伦理声明或上传材料。

## 每次执行前检查

1. **正式检索/筛选前**：核对方案和检索策略版本、研究者批准、注册状态与未注册说明。仅有 `survey_register_protocol` 等旧任务为 done 不足以通过；保留旧 task ID，不强制改名。
2. **筛选前**：来源覆盖和取回完整性已说明。部分检索可作明确标识的批次筛选，不能把阶段或 PRISMA 标为最终完成；纳排依照批准标准，不按引用数、期刊级别或全文权限替代资格标准。
3. **提取前**：筛选最终决定与 study/report 归并经确认。研究是分析单位，多份报告不是多个独立试验。
4. **分析前**：提取值与出处已核对、RoB 2 已评估、比较/结局/时间窗/分析人群已明确，研究者确认可合并性及适用方法。
5. **方案变化**：列出受影响的筛选、提取和分析，先取得批准并记录偏离，再复核或重跑；无关产物无需重做。

缺少材料时列出具体缺口，可以准备草稿或继续不依赖缺口的任务，但不得编造批准或标记完成。PostToolUse hook 只作提醒，不是执行拦截器；这些是命令与 agent 必须遵守的检查规则，不是对任意外部脚本的隔离保证。

结构化记录建立后，每次准备标记检索/筛选任务完成或交接下一阶段前，运行本技能的 `scripts/review_state.py validate <项目的 .pipeline/systematic-review 目录>`。退出 1 修复输入错误；退出 2 按 blocker 处理（未批准不能正式筛选，待筛选可以继续筛选，分歧交人工裁决，partial 检索不得宣称最终完成），不能形成“必须先全部筛完才能开始”的循环。退出 0 只证明此工具覆盖的记录完整，不能替代分析前人工判断。

## 检索与证据记录

保留数据源、完整检索式、日期限制、执行时间、命中数、实际取回数及原始结果。数据库会变化；未来计数不同不自动意味着不可复现。

PubMed 正式取回使用实际 skills 目录下 `pubmed-search/scripts/pubmed_search.py --all --checkpoint <专用目录>`；先读 `pubmed-search/references/retrieval-and-resume.md`，保持批准的检索式和日期范围。需要摘要时加 `--abstracts`，中断后按原参数加 `--resume`，不重取成功字段。默认 `--retmax` 仍是候选检索，不代表完整。

本实现支持的 UID 清单上限为 10000；超过上限、响应缺项、网络失败或异常时如实保留 partial。不要未经核验自动拆分，改用合法完整导出或由研究者审核拆分方案。新 CLI 已有离线测试，但尚未真实 API 验收。导入使用源输出的 query、executed_at 和完整性字段；元数据条数相等也不能掩盖摘要记录缺失。注册库概览输出仍不等于核查全部结局/结果。

复用 `.pipeline/literature/<corpus>/papers/<slug>/metadata.json`、PDF/OCR 与既有引用库。证据出处至少含报告标识、页/表/章节或网页字段及访问日期。引用元数据可靠性与取得全文是不同问题；未取到全文不能伪称阅读过，也不能仅因无 PDF 就否定可核实的题录。

## 人工筛选与数据提取

- 独立人工筛选决定、AI 建议和最终裁决分开记录；两名 AI 不等于两名研究者，不伪造 reviewer 身份。
- 单人流程可继续，但必须说明限制，不写成双人独立筛选。
- 全文排除保留主要理由；未取得全文单列为 not retrieved，不等同于不符合资格。
- 区分 records（来源题录）、reports（报告）、studies（研究），PRISMA 计数按实际记录计算。探索性精选数量不能充当正式计数。
- 关键数据保留原始值、标准化值、转换过程与出处；未报告不等于 0，OCR 数字需核对原文。
- 当前旧 CSV 只是起始交换模板，不是完整的多报告/多结局数据库，也不能直接交给 R snippets。

## 成对 Meta 范围与统计规则

SR-04 适配器限定平行组 RCT、两组比较、RR/MD/SMD。先读 `extraction-and-analysis.md`，运行本技能 `scripts/meta_analysis.py validate <review-dir> --plan <plan.json>`，确认有出处的提取、当前版本、人工核对、结果级 RoB 2 和预设方法后，再用 run 写入新结果目录。现有示例中的 OR/RD/HR 仍需统计人员按方案使用，不在该适配器范围。

R 返回成功不等于结果已完整：读取 run_manifest.json 的 completed/failed，再核对 summary.json、effects.csv 和图。单研究与 not_estimable 如实报告，不填合并值或异质性；双零排除仅针对计算，不修改综述纳入记录。summary_of_findings_draft.csv 不是完成的 GRADE 表；按 ledger_entries.md 核查后登记项目记忆，不自动把运行完成写成研究完成。

多臂、整群、交叉设计，以及重复人群、不同时间点/结局需单独处理；不自动当作独立两组试验。零事件与缺失方差按 SAP 明确处理，不静默加校正或删除研究。

仅一个研究时报告单项效应；不适合合并时做叙述性综合，不能为了出图强行合并。RR/OR/HR 的对数尺度与 MD/SMD/RD 的原始尺度分开，后者不能指数转换。

偏倚检验不默认执行：少于 10 个独立研究不执行；达到 10 个也需满足预设方法与效应量适用性。漏斗图不对称不是发表偏倚的确定证明；不把 Egger 直接套用于所有二分类或 SMD 数据。

**confirmatory** 禁止为显著性更换方案，但允许有记录的错误修复后重跑、确定性复现和预设敏感性分析。计划外分析单独标为探索性，不能混入预设结果。

图表使用真实数据与分析代码，保存 PDF、输入数据和 `.R` 或 `.py` 脚本，登记 `figure_ledger.md`；不为满足数量画不适用的 KM、漏斗图或消融图。

## 写作与验收

PRISMA 陈述只能来自实际执行记录；未完成步骤不能写成完成。RoB 2 按具体结果及正式工具判断，不能把域列表当完整评价工具；GRADE 按比较与结局保留依据。

核对注册状态与时间、检索覆盖、筛选人员、排除理由、重复报告、提取出处、分析偏离、PRISMA 和 Summary of Findings。研究方法、结果表、图与正文一致，不把计划写成事实。

写作交接先读 `writing-handoff.md`。负责人在 publication.json 登记全部需报告的分析与引用，运行
`scripts/writing_handoff.py check <review-dir> --config <publication.json>`；build 只导出至新目录。
未通过检查的运行不用于结果写作；定量研究数按 pooled 运行的研究并集计算，有未解决运行时保留 null。
ready_for_drafting 只覆盖此处已核查材料，GRADE、引用语境和投稿检查继续保留待办。
软件测试与公开基准须据实标注 purpose，不冒充真实研究交接。

SR-02 已提供导入、版本化人工筛选/裁决、研究归并校验和 PRISMA 计数；SR-03 提供受支持上限内的 PubMed 分批恢复；SR-04 提供带出处的提取规范、人工 RoB 2 记录及 RR/MD/SMD 计算；SR-05 提供写作交接与公开 BCG 数值基准。真实服务与大查询验收、其他数据库恢复、自动原文提取、GRADE、官方 PRISMA 图和真实临床案例端到端验收仍待完成。工具不自动写回研究决定或认证人员身份。
