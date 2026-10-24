# PubMed 分块响应中断修复验收

日期：2026-10-01。由AIG英文叙述性综述的真实检索触发。

## 观察与原因

ESummary/EFetch的HTTP响应在读取分块内容时抛出 `http.client.IncompleteRead`。该异常未被原传输层的URLError/TimeoutError/OSError分支捕获，导致CLI退出1并打印回溯，而非进入既有可恢复错误路径。问题在批次200、50和8的请求中均观察到，不能简单归因于响应过大。

已成功保存的检查点仍在，并无证据表明这些记录损坏；但该次最终结果JSON没有生成。

## 最小修改

- `skills/pubmed-search/scripts/pubmed_api.py` 将 `HTTPException` 纳入现有传输错误处理。
- 保留原重试次数、退避、HTTP状态码与Retry-After逻辑。
- 不宽松解析截断内容，不将部分字节当作完整响应。
- 失败走现有RetrievalError和partial输出，保留缺项与恢复状态；不打印部分响应或凭证。

## 回归测试

新增两项测试覆盖三个端点的response.read异常、一次失败后成功、重试耗尽后写出partial、关闭响应流、释放本进程锁、不泄露部分响应内容，以及恢复时不重复成功的UID和题录请求。

- 修复前：25项专项测试中的新增用例复现4个错误子情形。
- 修复后：25/25专项测试通过。
- 完整 `npm run check`：退出0，Node 48通过/1跳过，Python 107通过/11跳过，合计155通过、12统计依赖相关跳过、0失败。
- 完整日志：`/Volumes/Leo/Projects/AIG-review/quality/software-check-pubmed-transport.log`。

## 真实恢复结果

将修复复制到AIG项目技能副本后，使用原检查点和原查询参数执行resume，输出到新文件，未覆盖失败历史：

- `pubmed-core-studies-recovered.json`：8/8题录及所请求摘要响应完整。
- `pubmed-neoplasia-metadata-recovered.json`：329/329题录完整；该查询没有请求全部摘要。

这证明本次恢复有效，不是对所有网络条件或更大查询的保证。原指南检索的两条Bookshelf题录覆盖问题未在本次改动中修复，仍如实保留。

未提交、推送或发布；未改变研究检索式、病例定义或临床结论。
