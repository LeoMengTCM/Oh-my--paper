# SR-05 实施计划：写作交接与公开数据验证

日期：2026-09-30
依据：已批准总体设计及继续推进 SR-05 的指令。

实施状态：写作交接工具、双插件入口和公开 BCG 数值基准已完成，见
`2026-09-30-sr05-validation.md`。真实临床综述端到端验收仍待实际研究材料与人工环节。

## 交付范围

增加只读交接检查与新目录导出：汇总当前筛选记录、明确登记的统计运行、参考文献与核验记录，生成机器可读清单、结果表、引用材料和给写作角色的交接说明。不是自动生成一篇论文，也不替代人工 GRADE、引用语境核查或投稿审查。

接口：`writing_handoff.py check|build <review-dir> --config <publication.json> [--out <新目录>]`。

配置包含 schema_version=1、purpose（research/software_validation/public_benchmark）、protocol_version、analyses（run_directory/plan_path/role）、bibliography、report_citations、method_citations、verification_records。路径相对 review-dir 或为绝对路径。

## 核心规则

1. 当前检索/筛选/研究归并必须完整。对每个登记运行重新核对当前计划和选中输入，拒绝 failed、旧版本、错误研究身份和已改动结果。
2. SR-04 完成运行新增文件摘要，用于检测运行后改动，不当作人员签名或研究真实性认证。交接只接受有完整摘要的 completed 运行；旧运行需复核/重跑，不自动补造历史摘要。
3. 多个分析共用研究时，定量合成计数取已登记 pooled 运行的 study_id 并集；单研究结果不当作 Meta。任何登记运行仍不确定时，最终定量合成计数为 null，不低估为已完成。
4. 参考文献必须核对 bibliography.entries、BibTeX、原 metadata 和报告身份；source_platforms 只是来源声明，不能冒充外部核验。
5. 核验记录支持保存的 Crossref 响应比对，以及登记人类的人工核验记录。检查本地证据一致性，不把它称为实时在线认证或引用语境支持。
6. 明确区分研究与软件验证。示例与公开数值基准不能成为 ready_for_drafting 的真实研究交接包；不生成 ready_for_submission=true。
7. build 只创建新目录，不修改研究记录、统计输出或原引用库。部分交接也能导出清楚标为 partial 的检查报告；不可把缺项填成完成。

## 产物

- handoff.json / handoff.md：状态、来源和下一步事项。
- review_counts.json：实际筛选计数及经确认的定量合成研究并集。
- results.csv / study_results.csv：直接来自已绑定运行的结果，不由模型重写数字。
- citations.json / refs：使用的引用键、元数据快照、核验层次及原 BibTeX 条目。
- reporting_pending：GRADE、引用语境、临床解释、报告清单和稿件审查仍需人工完成或另行核对。

## 验证

先用离线文件测试新旧计划不匹配、输出被修改、缺引用或外部核验、重复研究并集、验证材料保护、输出不覆盖及输入不变。再使用实际 R 执行的分析运行做交接测试。

## 公开案例边界

已找到 JSS 2010 的 metafor 方法学论文：DOI 10.18637/jss.v036.i03。正式站点的文本提取失败，但作者维护的 CRAN R 包内包含论文 PDF；Crossref API 已直接读取并核对题名、作者、年份和 DOI。metadat 1.6.0 的许可为 GPL (>= 2)。本轮不另行分发原 PDF。

BCG 数据共有 13 项研究，分配方式包含 7 random、2 alternate、4 systematic，不能把全部数据称为本产品支持的纯 RCT 临床流程。可用其复现论文已发表的 REML 数值，验证 R 内核及引用证据；不得为通过临床流程伪造纳排、RoB 或人工批准。真实系统综述的完整端到端验收仍需原始资料和真实人工环节，本轮如实保留缺口。

不提交、不推送，不自动发表或上传稿件。
