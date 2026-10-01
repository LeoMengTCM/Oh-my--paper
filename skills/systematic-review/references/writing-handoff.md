# 写作交接：当前记录、统计运行与引用

适用于已建立结构化记录的系统综述。检查读取当前检索、筛选、研究归并和明确登记的分析，
导出供写作人员使用的材料；不会代写论文、新增统计分析或完成 GRADE。

## 配置与调用

在项目 `.pipeline/systematic-review/publication.json` 登记需要交接的全部运行：

```json
{
  "schema_version": 1,
  "purpose": "research",
  "protocol_version": "v1",
  "synthesis_mode": "quantitative",
  "analyses": [
    {"run_directory": "analyses/primary-run", "plan_path": "analysis_plan.json", "role": "primary"}
  ],
  "bibliography": "../literature/review-corpus/bibliography.json",
  "report_citations": {"report-main": "ExistingCitationKey2020"},
  "method_citations": [],
  "verification_records": "citation_verifications.jsonl"
}
```

示例中的报告 ID 和引用键须替换为实际已有记录。`role` 为 primary、secondary、sensitivity 或 exploratory。
程序只检查登记的运行，不自行选择最新目录，不推断未登记的分析是否完成。
`review.json` 和 publication 配置必须显式声明相同 `purpose`；真实研究为 research，
软件测试为 software_validation，公开数值基准为 public_benchmark。缺少用途时由负责人据实补充，
不要将示例改标为研究来绕过检查。

配置内的路径相对 review-dir（不是 publication.json 所在目录），也可以是绝对路径。
命令行的 review-dir、--config、--out 相对调用时工作目录。脚本路径从 skill 目录解析：

```bash
python3 scripts/writing_handoff.py check /path/to/review --config /path/to/review/publication.json
python3 scripts/writing_handoff.py build /path/to/review --config /path/to/review/publication.json --out /path/to/new-handoff
```

退出 0：本工具覆盖的检查通过，可据此起草；退出 2：partial，按 blockers 继续处理；
退出 1：输入结构、参数或文件操作错误。build 可以导出 partial 包，方便查看具体缺口。
输出目录必须是新目录，不能放在原统计运行目录内。源研究记录、结果和书目均不写回。

## 统计运行检查

每个运行须为 `completed`，对应当前方案、完整分析计划及选中输入。
检查重新运行分析前置校验，再比较 `prepared.json`、`source_snapshot.json` 和 `input.csv`，
核对结果研究 ID、排除记录、研究数量、效应尺度和必要产物。
SR-04 运行现在保存 `artifact_sha256`，用于识别运行后产物变动；没有摘要的旧运行须复核/重跑，
不补造历史摘要。摘要不是数字签名，也不证明研究真实性。

`counts.studies_in_quantitative_synthesis` 取全部有效 pooled 运行的 study_id 并集；
单研究效应不计为 Meta。只要任何登记运行无效、筛选未完成或版本失效，该计数即为 null。
引文缺失不改变已经核对的统计计数，但会使交接状态为 partial。

不做 Meta 时使用 `synthesis_mode=narrative`、`analyses=[]`，并登记 `narrative_reason`、
`narrative_approved_by` 和含时区的 `narrative_approved_at`；确认者须为已登记人类，
时间不早于当前方案批准。这只记录为何采用叙述性综合，不自动生成综合结果。

## 引用核验记录

先用现有 `build_bibliography.py` 生成文献库与引用键，不手写替代书目。
所有纳入报告都须映射至已有引用键，方法文献通过 method_citations 指定。
`bibliography.entries`、实际 BibTeX、原 metadata、报告 DOI/PMID/标题须一致。
`provenance.metadata_path` 相对 bibliography.json 所在目录；`bib_out` 沿用生成器记录的绝对路径。
若文献库搬迁，先用生成器更新路径并复核，不让交接脚本暗改来源。

`source` / `source_platforms` 只是来源声明，不等于核验。每个使用的引用键在 JSONL 中登记一条核验记录：

```json
{"schema_version":1,"verification_id":"verify-method","citation_key":"ExistingMethodKey","source_type":"crossref","source_url":"https://api.crossref.org/works/10.18637/jss.v036.i03","evidence_path":"evidence/crossref-method.json","checked_by":"registered-reviewer-id","checked_at":"2026-09-30T10:00:00+08:00"}
```

Crossref 记录须指向该 DOI 的 API 地址，evidence_path 保存实际响应，其中 DOI、题名、作者和年份
均与原 metadata 对比。程序不联网；一致性通过标记为 crossref_snapshot_checked，不能写成“实时认证”。

无 Crossref 资料时可以由登记人类提供 `source_type=manual`，保存包含 source_url、title、authors、
year、doi（及适用的 arxiv_id）的 JSON 证据并与元数据比对，标为 manual_record_checked。
checked_by 须为登记人类；AI 不能登记成一次人工核验。任一方式都不代表引用语境或论断支持已核对。

## 导出材料与写作边界

- `handoff.json` / `handoff.md`：状态、实际方法记录、缺口、来源和后续任务。
- `review_counts.json`：筛选计数和明确验证的定量合成研究并集。内部 screening 保留原筛选模块输出，最终定量计数读顶层 counts。
- `results.csv`：每次分析的比较、结局、时间窗、人群、效应与区间等原始值；`study_results.csv` 保留研究级效应。
- `analyses/run-NNN/`：通过检查的运行原文件；无效运行只在交接报告中列出，不导出为有效结果。
- `citations.json`、`refs/references.bib`、`refs/metadata.json`：引用检查、原引用键及元数据快照。partial 包内引用须结合 checks 使用。

只有 `package_status=completed` 才表示导出完成；中途失败的 building 包不可使用。
`ready_for_drafting` 不包括 GRADE、临床解释、引用语境、PRISMA 报告核查和全文审稿，
这些始终列在 reporting_pending。`submission_readiness=not_assessed`，工具不声称可以投稿。
注册状态 planned/submitted 不写成 registered；筛选人数只按实际登记说明。
software_validation/public_benchmark 始终保持 ready_for_drafting=false。

公开 BCG 数值验证见 `../examples/bcg-benchmark/README.md`。它没有临床筛选记录，
不能作为研究交接输入；完整真实综述验收仍需要研究者的真实材料与决定。
