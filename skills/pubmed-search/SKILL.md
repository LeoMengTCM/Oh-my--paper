---
id: pubmed-search
name: pubmed-search
description: Search PubMed and MEDLINE with MeSH/date filters, explicit retrieval completeness, batched metadata and abstracts, and resumable checkpoints.
version: 1.0.0
stages: [survey, ideation, experiment]
tools: [read_file, search_project, write_file, run_terminal]
domains: [clinical-medicine]
primaryIntent: research
intents: [research]
keywords: [pubmed, medline, ncbi, e-utilities, mesh, clinical-literature, evidence-search, systematic-review]
status: verified
---

# pubmed-search

通过 NCBI E-utilities 检索 PubMed/MEDLINE。区分探索性候选阅读和系统综述正式检索；数据库收录本身不证明文献已同行评审、符合纳入标准或已经取得全文。

脚本只使用 Python 标准库。开始前读取 `references/retrieval-and-resume.md`，尤其是完整性字段、退出码、恢复参数和来源记录规则。

## 候选检索

从实际技能目录解析脚本路径，结果写入研究项目而非技能目录：

```bash
python3 scripts/pubmed_search.py 'metformin AND cardiovascular outcomes' --retmax 50
python3 scripts/pubmed_search.py '"heart failure"[MeSH] AND randomized[tiab]' \
  --mindate 2020/01/01 --maxdate 2024/12/31 --abstracts
```

默认最多 20 条。成功取得候选不代表完整检索；检查 `retrieval_complete` 和 `incomplete_reasons`，不能只看退出码或 returned。

## 正式检索与恢复

systematic-review 先按 `systematic-review/references/rct-pairwise-profile.md` 确认方案版本和检索策略，再请求完整取回：

```bash
python3 scripts/pubmed_search.py '实际完整检索式' --all --abstracts \
  --checkpoint /path/to/project/.pipeline/literature/my-review/pubmed-checkpoint \
  --output /path/to/project/.pipeline/literature/my-review/pubmed.json
```

中断后使用同一组查询、日期、模式和批大小，加 `--resume`。输出文件已存在时，经确认再加 `--overwrite-output`。恢复复用已固定的 PMID 清单和成功字段，不重复查询已取得的记录。

- 默认每批 200 条，允许 1–200。
- 本实现的 UID 清单上限为 10000；超过时明确返回 partial/uid_limit，停止批量元数据获取，提示完整导出或人工审核的拆分。不自动绕过上限。
- 完整取回要求全部目标元数据和所请求的摘要响应齐全。真实没有摘要与响应漏掉 PMID 不同。
- 初始检索失败的 total_count 为 null，不是零命中。
- 退出 2 保留已取得结果和缺项；退出 1 表示参数、文件或检查点错误。详见参考文档。

## 输出与来源记录

保留 query/total_count/returned/results；新增 query_parameters、query_translation、executed_at、run_id、requested_pmids、missing_metadata_pmids、missing_abstract_pmids、retrieval_complete、status、incomplete_reasons 和 errors。

SR-02 导入使用源文件的 query 和 executed_at，保留日期限制、查询转换和来源运行 ID。未完整取回时，不能仅因 returned 恰好等于 total_count 就加 --complete。

## 检索策略

- MeSH 与自由词结合，兼顾规范主题词和最新尚未完成标引的文献。
- 按研究者批准的 PICO、纳排标准与数据库策略构建检索式，不自动用引用数、期刊等级或语言过滤替代资格标准。
- 保存完整检索式、日期参数、检索时间、命中数、实际导入数、查询转换和原始响应。未来数据库变化可能导致结果不同。

## 服务限制与验证边界

- `NCBI_API_KEY`、`NCBI_EMAIL` 环境变量可提供身份；也保留 --api-key 和 --email。请求配置和错误 URL 不记录凭证。
- 请求按单进程节流，有限重试并遵守 Retry-After。较长等待、网络失败或异常响应停止后允许恢复，不持续请求。
- 不自动删除其他任务的锁，不覆盖无关输出，不把损坏检查点当作空任务。
- 本轮已通过离线模拟传输与恢复测试；NCBI 官方页被浏览器验证拦截，尚未完成真实 API 与大查询验收，不把离线通过写成线上已验证。
