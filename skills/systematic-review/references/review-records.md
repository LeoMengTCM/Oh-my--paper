# SR-02：综述记录、导入预览与筛选计数

本工具使用 Python 标准库，只读本地记录，不联网、不修改源文件、不替研究者作纳排决定。它验证结构、关联和登记的人员角色，不认证真实身份，不证明实际阅读过全文，也不构成正式电子签名系统。

## 命令与退出码

从实际安装的 `systematic-review` 技能目录运行（下列路径相对此目录）：

```bash
python3 scripts/review_state.py validate /path/to/project/.pipeline/systematic-review
python3 scripts/review_state.py prisma /path/to/project/.pipeline/systematic-review
python3 scripts/review_state.py prisma /path/to/project/.pipeline/systematic-review --format markdown
```

Windows 按本机 Python 安装使用 `python`。输出默认是 JSON；Markdown 只用于 `prisma`。

- **0**：本工具覆盖的检索、筛选和研究归并记录完整。不是整项系统综述、RoB 2、GRADE 或 Meta 分析已完成。
- **1**：文件、结构、标识或逻辑错误。stderr 给出错误，不在 stdout 输出可能误用的计数。
- **2**：结构合法但有待处理事项。stdout 仍输出明确标为 partial 的进度，不应把它当成工具故障，也不应忽略其阻塞项。

先完成记录写入，再运行校验；不要同时由多个进程修改这些文件。此版本没有事务写入、自动迁移、审批采集或筛选界面。

## 文件与通用规范

目录内必须有 `review.json` 及下面六个 JSONL 文件。尚无记录的 JSONL 文件为空即可，不能省略文件。JSONL 每行一个对象，每个对象带 `schema_version: 1`。重复 JSON 字段、重复 ID、断开的关联会报错。日期使用包含时区的 ISO 格式，例如 `2026-01-02T10:00:00Z`。

### review.json

```json
{
  "schema_version": 1,
  "review_id": "my-review",
  "purpose": "research",
  "protocol_version": "v1",
  "screening_mode": "dual",
  "screeners": ["researcher-a", "researcher-b"],
  "reviewers": [
    {"reviewer_id": "researcher-a", "kind": "human"},
    {"reviewer_id": "researcher-b", "kind": "human"},
    {"reviewer_id": "adjudicator", "kind": "human"},
    {"reviewer_id": "assistant", "kind": "ai"}
  ],
  "registration": {"status": "not_registered", "reason": "填写真实原因并由研究者确认"}
}
```

`single` 必须指定一名人类 screener；`dual` 必须指定两名不同的人类 screener。其他登记人类可参与裁决；AI 不得计入独立筛选人数。

`purpose` 区分 research、software_validation 和 public_benchmark。旧筛选记录可暂缺该扩展字段；
进入 SR-05 写作交接前必须据实补充，并与 publication.json 一致。示例不能改标为真实研究。

注册状态为 planned/submitted/registered/not_registered/not_applicable。registered 要有非空 `registration_id`，其他状态要有非空 `reason`。状态如实记录，不能倒填前瞻性注册。

### approvals.jsonl

每条包含：

- `approval_id`、`protocol_version`、`reviewer_id`（登记的人类）、`approved_at`。
- `screening_mode`、`registration_status`：批准时对应的模式和注册状态；与当前配置不一致时，当前批准失效。
- `acknowledged_limitations: true`：单人筛选或注册未完成/不适用时必填，表示研究者确认相应说明。
- `protocol_document`、`sap_document`：批准所依据的文件路径，相对本目录或绝对路径。路径指向已有文件。

每个版本只有一条批准记录；更改资格标准、方案或批准范围时建立新版本，而不是覆盖旧记录。程序仅检查文件存在，不核验正文语义或文件签名；修改正文必须同步升级版本并重新确认。无法由程序证明批准者真实存在或实际作出过决定。

### search_runs.jsonl

`search_run_id`、`source`、`source_type`、`query`、`searched_at`、`status`、`identified_count`、`retrieved_count`。

- source_type：database/register/other。
- status：complete/partial。
- query：实际执行的完整检索式，不用主题词摘要代替。
- identified_count：数据源报告的非负整数命中数；仅 partial 允许明确的 null（未知）。
- retrieved_count：实际导入的题录数，必须等于对应 records 数量。
- complete 需要已知命中数等于导入数。人为截断、部分分页或来源覆盖未完成必须标 partial。

空项目不能算已检索；确实执行且有记录的零结果检索可以完成筛选。某一个来源的记录完整，不等于研究者选择的数据库范围充分，后者仍须方法学判断。

### records.jsonl

`record_id`、`search_run_id`、`source_record_id`、`report_id`。

一条代表一个来源批次中的题录。相同批次的来源记录 ID 不可重复导入。不同来源/批次的重复题录仍保留，通过相同 report_id 表示同一份报告，不能直接删除来源记录。

### reports.jsonl

`report_id`、`title`、`retrieval_status`，可选 `doi`、`pmid` 与 `study_link`。

retrieval_status：not_requested（尚未请求）、sought（获取中）、retrieved（已取得）、not_retrieved（已尝试但未取得）。这不是开放获取许可证状态，也不是资格排除结果；原文库的 `full_text_status` 继续单独维护。

同一 DOI/PMID 不能对应两个 report_id。题名相似不自动等于同一报告。

study_link 示例：

```json
{"study_id":"study-1","protocol_version":"v1","confirmed_by":"researcher-a","confirmed_at":"2026-01-02T10:00:00Z","reason":"填写核对注册号、中心、样本与时间范围等的实际依据"}
```

当前纳入报告的 study_link 须由登记人类确认，指向 studies 中已有研究，并匹配当前方案版本。没有归并、版本过期或关联未知研究不能算归并完成。同一试验的主要与随访报告可以关联同一个研究，不默认排除伴随报告。

### studies.jsonl

`study_id`、`design`；可以保存其他研究元数据。study_id 是研究身份，不从论文标题或引用键重算。只有当前纳入且归并已确认的报告才贡献 `studies_included`。

### screening_decisions.jsonl

必填 `decision_id`、`report_id`、`protocol_version`、`stage`、`reviewer_id`、`decision`、`decided_at`、`role`。

- stage：title_abstract/full_text。
- decision：include/exclude。
- role：initial/adjudication。
- 全文排除及裁决必须有非空 `reason`。
- initial：指定筛选者的独立判断；AI initial 是建议，不能替代人类。
- 修订：新增记录并以 `supersedes` 指向同一人员、事项、角色和版本的旧决定。保留旧行，不按最新时间猜有效决定；分叉或循环会报错。
- adjudication：登记人类作出，`resolution_method` 为 discussion/third_reviewer，`resolves` 引用有分歧的人工初始判断 ID。第三位研究者不能是所引用的初始筛选者。不得引用 AI 建议冒充人工分歧。

两名人类同意才能形成 dual 初始结论。全文排除理由不同也需要解决分歧，不能任取一条填入 PRISMA。裁决只作用于明确引用的有效判断；原判断被修订后旧裁决失效。原判断修订导致分歧消失时可以采用新的独立一致结论。

全文判断须已有题名摘要纳入且确实取得全文；题名摘要最终判断晚于既有全文判断时，旧全文判断不计入当前完成数，须复核并显式修订。当前版本未获批准时，不把其中的暂存判断当作已完成正式筛选。

## 导入预览

```bash
python3 scripts/import_records.py /path/to/export.json --format pubmed-json \
  --review-id my-review --search-run-id pubmed-001 \
  --source PubMed --source-type database \
  --query '实际完整检索式' --searched-at '2026-01-02T10:00:00Z'
```

- `--format` 支持 pubmed-json、ris、csv。
- PubMed JSON 兼容现有 pubmed-search 的 query/total_count/returned/results 输出。returned 与数组长度不符会报错。新版输出的 retrieval_complete/status/缺项必须一致，不能因条数相等就用 --complete 提升未完整取回的来源。
- 新版 PubMed 导入的 --searched-at 必须等于源文件 executed_at（等价时区表示可以），不能改为导入日期。search_run 会保留 source_run_id、query_parameters、query_translation、retrieval_complete 与缺项原因；日期限制和查询转换不会在导入时丢失。
- CSV 必须有唯一的 source_record_id、title 列；doi、pmid 可选。缺列、多列或重复表头报错。
- RIS 支持 TY/ER 记录、TI/T1 标题及续行、DO、ID 和显式 PMID 标签；并非所有数据库的私有扩展都能自动解释。没有来源 ID 时生成稳定的记录摘要标识并给出说明。
- `--existing-reports /path/to/reports.jsonl`：已有综述应提供此参数，精确匹配 DOI/PMID 后保留原 report_id。既有报告不作为替换条目输出。新标识建议人工复核后补入既有记录。
- `--identified-count N --complete`：只有明确知道总命中数且全部取回时使用。默认 partial；未知命中数保持 null，不用记录数替代。

stdout 是预览对象：`search_run`、`records`、仅新增的 `reports`、`warnings`。review_id 用于稳定 ID 生成，同一批次重复导入的 record_id 相同。不同批次不应复用同一 search_run_id。

先审阅预览，再由维护者把对象逐条追加到相应 JSONL 文件，保留历史。此 CLI 不负责多文件写回或合并事务；不要把整个预览 JSON 直接写进 records.jsonl，不要用空输出覆盖已有记录。处理完后运行 validate/prisma。新检索批次若没有提供既有报告表，需要人工检查跨批次的重复身份。

## PRISMA 输出解释

`records_identified` 是实际导入题录数，不是未知或尚未取回的 API 总命中数。后者另列为 `search_hits_reported`；存在未知来源时该字段为 null。partial 下的表明确标为非最终。

分别显示待完成的题名摘要筛选、尚未请求的全文、获取中的全文、全文筛选和研究归并。已完成筛选的计算使用最终有效决定，不用“曾被某人看过”代替。

本轮统一使用题名摘要→获取→全文路径，包括 other 来源；若真实研究对其他来源采取不同流程，不能直接把这张汇总表当成完整官方 PRISMA 图。SR-04 的受限范围 RCT 分析见 `extraction-and-analysis.md`；本计数器不自动汇总不同结局的分析运行，GRADE 和原文自动提取仍未实现。

此计数器的 `studies_in_quantitative_synthesis` 保持 null：未明确关联并核对多个分析运行时，不能把纳入研究数或某一个结局的 k 当作整项综述的定量合成研究数。SR-04 运行结果中的 k_analyzed 只适用于该 analysis_id。

## 合成示例

```bash
python3 scripts/review_state.py prisma examples/rct-pairwise --format markdown
```

示例中的人物、报告、研究、检索与批准都是合成测试数据，不是真实学术证据。预期 3 条来源记录、1 条重复、2 份报告、1 项研究。可复制到临时目录学习字段，但不得混入真实综述。
