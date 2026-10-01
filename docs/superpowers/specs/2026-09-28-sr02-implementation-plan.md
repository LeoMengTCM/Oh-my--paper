# SR-02 实施计划：记录、筛选与 PRISMA

日期：2026-09-28
依据：已批准的总体设计，以及用户继续推进 SR-02 的指令。

## 本轮边界

保留 `.pipeline/systematic-review/` 下的 JSON/JSONL 规范。新增 Python 标准库命令 `review_state.py validate <目录>`、`prisma <目录> --format json|markdown`：只读校验并向 stdout 输出结果，不直接修改用户研究记录。题录导入先提供只读预览，不在多个权威文件之间做隐式写回。没有数据库、界面、远端调用或真实研究执行。

JSON 为配置，JSONL 为具有稳定 ID 的记录。命令验证结构、引用、版本与已登记角色，不认证真实身份，不能保证人工记录没有伪造。

## 权威输入

- `review.json`：schema_version=1、review_id、protocol_version、single/dual 筛选模式、登记的 human/ai reviewer、真实注册状态。
- `approvals.jsonl`：具体方案版本、人工批准者、批准时间、筛选模式及注册状态的确认。
- `search_runs.jsonl`：数据库/注册库/其他来源、完整检索式、执行时间、命中数、取回数、complete/partial 状态。
- `records.jsonl`：来源题录、search_run_id、report_id、原始来源记录标识。
- `reports.jsonl`：报告元数据、全文获取状态、经人工确认且关联方案版本的 study_link。
- `studies.jsonl`：研究身份与设计；不按报告数量代替研究数。
- `screening_decisions.jsonl`：报告、方案版本、title_abstract/full_text、reviewer、include/exclude、时间、initial/adjudication、排除理由、supersedes/resolves。

每条 JSONL 记录带 schema_version。保留历史版本，禁止按最新时间猜测哪条决定有效；修订显式 supersedes，裁决显式 resolves。当前版本以外的决定留存但不计入当前筛选结果。

## 决策规则

- single：至少一名登记的人类研究者的有效判断；输出必须注明单人筛选限制。
- dual：两名指定的人类筛选者分别判断。AI 建议不计入独立人数。
- 分歧未裁决保持 conflict；裁决只能由登记人类作出并引用当前独立判断。原判断修订后旧裁决失效。
- 全文筛选必须对应题名摘要纳入且已取得全文的报告；未取得全文不能作为资格排除。
- 注册为未注册/未完成时保留真实状态及说明，不自动阻断一项已由研究者批准继续的综述。
- 当前版本未获批准、检索不完整、筛选未完成、报告未归并等列为阻塞项；不把结构合法等同于研究完成。

## 输出与状态码

0：本轮支持的检索/筛选/研究归并记录完整；不表示整项系统综述或 Meta 分析已完成。
1：结构、引用或逻辑错误，不输出可误用的计数。
2：结构合法但仍有待处理事项，输出明确 partial 的进度与原因。

PRISMA 输出是计数表，不是自动绘制的官方流程图。分别计算 records/reports/studies，核对识别→去重→筛选→获取→全文→纳入的数量关系。保留未完成数量与全文未取得数量；定量合成研究数为 null（本轮没有分析运行记录）。

## 实施顺序

1. 用最小离线样例建立 validate 命令与 schema/引用校验。
2. 实现人工独立决定、AI 隔离、分歧与裁决、版本失效。
3. 计算并测试 PRISMA 计数，覆盖重复题录、多报告同研究、全文缺失与部分检索。
4. 增加 PubMed JSON / RIS / 标准 CSV 导入预览与身份冲突检查；不自动用相似标题归并。
5. 接入现有 profile、技能与 npm/CI 离线测试，提供可运行的合成示例和字段文档。
6. 汇总通过/跳过/未实现项。不提交、不推送，不迁移既有项目。
