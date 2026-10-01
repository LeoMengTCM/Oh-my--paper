# PubMed 分批检索与恢复

本实现使用 Python 标准库，通过 ESearch 固定 PMID 清单，再用 POST 分批调用 ESummary/EFetch。检查点用于恢复固定清单，不把重新检索后的新结果混入旧批次。

## 两种模式

### 候选检索

```bash
python3 /实际技能目录/pubmed-search/scripts/pubmed_search.py \
  '实际完整检索式' --retmax 20
```

默认取最多 20 条。若数据库还有其他命中，命令可退出 0，但结果为 `status: partial`、`retrieval_complete: false`，原因包含 bounded_search。这是有意的候选上限，不是完整系统综述检索。

### 请求完整取回

在研究项目目录中运行，路径示例需替换为实际安装位置与项目路径：

```bash
python3 /实际技能目录/pubmed-search/scripts/pubmed_search.py \
  '实际完整检索式' --all --abstracts \
  --mindate 2020/01/01 --maxdate 2025/12/31 \
  --checkpoint .pipeline/literature/my-review/pubmed-checkpoint \
  --output .pipeline/literature/my-review/pubmed.json
```

- `--all` 必须指定专用检查点目录。
- 默认每批 200 条，`--batch-size` 可设 1–200。
- 完整取回要求 UID 清单完整、目标元数据齐全，以及请求的所有摘要记录均已收到。
- 本实现至多请求 10000 个 UID；超出时返回 partial/uid_limit，停止大批量元数据获取，不假装完整。使用合法完整导出，或由研究者审核检索拆分与去重方案。本版不自动日期分区，也不承诺 History Server 可绕过限制。
- 本版没有访问机构订阅、下载论文全文、筛选研究或执行统计。

## 恢复

使用原查询、日期、排序、模式、abstracts 和 batch-size，增加 `--resume`：

```bash
python3 /实际技能目录/pubmed-search/scripts/pubmed_search.py \
  '实际完整检索式' --all --abstracts \
  --mindate 2020/01/01 --maxdate 2025/12/31 \
  --checkpoint .pipeline/literature/my-review/pubmed-checkpoint --resume \
  --output .pipeline/literature/my-review/pubmed.json --overwrite-output
```

只补取缺失元数据和摘要，不重复请求成功项。已完成的恢复运行不发网络请求。

- 已固定完整 UID 清单后，不重新执行 ESearch；元数据的取回时间可能跨多次运行，每次响应时间保存在批次记录中。
- 初始 ESearch 失败，或尚未得到完整 UID 清单且没有进入元数据批次时，恢复会重试检索；每次尝试的时间和数量都有记录。
- 更换查询、日期范围、模式或批大小，应使用新检查点，不混用旧结果。
- API key、email、重试次数和输出路径可改变；它们不改变检索集合，不写入请求快照。
- 已有目录不能用新运行覆盖。损坏或不兼容的检查点报错，不自动重置。

## 目录与文件保护

```text
pubmed-checkpoint/
  checkpoint.json        # 查询规范、run_id、时间、UID 快照、原始 ESearch 响应
  batches/
    00000.json            # 该批次的 PMID、已取得字段、响应记录和时间
    00200.json
  .lock                   # 运行期间的独占锁，正常结束或 Ctrl+C 后释放
```

命令不会自动移除别的进程的锁。系统强制结束进程可能留下 `.lock`；先确认没有运行中的任务，再由用户处理。不要并发编辑检查点，不把它当成手工录入表。

结果 `--output` 不能位于检查点内部。已有输出默认保护，明确传 `--overwrite-output` 才允许替换。即使文件在请求过程中才被其他操作创建，也不会在未授权时覆盖。

文件写入使用同目录临时文件和原子发布；新建结果文件的独占发布需要文件系统支持硬链接，不支持时会报错，而不是退回不安全覆盖。仍可选择 stdout 输出，或使用支持该操作的本地文件系统。

## 输出

保持旧字段：query、total_count、returned、results。新增：

- producer、schema_version、run_id：生产者与运行标识。
- query_parameters：日期限制、datetype、sort、模式、批大小等；不含 key/email。
- query_translation、executed_at：ESearch 的查询转换与此次 UID 清单的取得时间。
- updated_at：本次输出更新时间，不替代原检索时间。
- requested_pmids：固定的目标清单。
- missing_metadata_pmids、missing_abstract_pmids：明确的未完成项。
- retrieval_complete、status、incomplete_reasons、errors、search_warnings：完整性及错误说明。

请求摘要时，单条结果的 abstract_status 为：

- available：收到记录且有摘要正文。
- not_reported：收到结构完整的文章记录，但没有摘要正文。
- missing_record：该 PMID 的摘要记录尚未取得，不能说成“文章没有摘要”。

返回的元数据数量可能等于总命中数，但缺少摘要响应时仍不完整。初始检索失败时 total_count 为 null，不能解释为零命中。

## 退出码

- **0**：请求范围内的工作完成。有意的候选上限仍可为 partial，必须读取完整性字段。
- **2**：请求未完成、达到本实现上限、网络/API 错误或中断。若有输出，仍可查看已取得记录和缺项。
- **1**：参数、文件冲突、权限、检查点损坏或不兼容；不进行不安全覆盖。

HTTP 200 中的错误对象不是成功。网络失败有限重试后停止，防止持续请求服务。单进程无 key 约每 0.34 秒发一次请求，有 key 约每 0.11 秒；多个进程合计仍可能触发服务端限流。遵守 Retry-After；要求等待超过 60 秒时停止并留待稍后恢复，不忽略等待要求继续请求。

推荐用 `NCBI_API_KEY`、`NCBI_EMAIL` 环境变量提供调用身份；也保留 `--api-key`、`--email`。错误消息不打印完整请求 URL，检查点请求配置不保存身份参数。检查点仍可能包含研究主题、论文元数据和摘要，应按研究资料管理。

## 交给 SR-02

导入预览使用原输出的 query 和 executed_at，不用今天的日期替代检索日期：

```bash
python3 /实际技能目录/systematic-review/scripts/import_records.py \
  .pipeline/literature/my-review/pubmed.json --format pubmed-json \
  --review-id my-review --search-run-id pubmed-001 \
  --source PubMed --source-type database \
  --query '与源文件相同的完整检索式' --searched-at '源文件的 executed_at'
```

只有 `retrieval_complete=true` 且已核对完整来源时，才加 `--identified-count <真实总数> --complete`。新生产者明确为 partial 时，不能通过匹配条数或手动加 --complete 提升为完整来源。

导入保留 source_run_id、日期参数、查询转换和缺项状态，供研究记录校验。现有综述还应传 `--existing-reports` 复用报告身份；导入器只输出预览，不自动写回权威 JSONL。

## 验证范围与参考

离线测试覆盖模拟 HTTP 边界、分批、恢复、缺项、限流、中断、输出保护、凭证不出现在错误 URL，以及检索输出→导入预览→综述记录校验。

2026-09-29，本轮 NCBI 官方说明页被浏览器验证拦截，搜索服务也返回限流；没有现场核验当前 API 服务行为，没有运行真实研究检索。10000 是本实现保守支持的 UID 上限，不是未经核验的无限取回承诺。

官方说明入口：<https://www.ncbi.nlm.nih.gov/books/NBK25499/>。真实 API、小样例返回结构及更大查询的验收须另行执行。
