# 合成 RCT 综述示例

本目录所有人物、报告、研究、检索记录、批准记录和“已取得全文”状态都是**合成测试数据**。没有真实试验、论文 PDF、注册号或人工审批，不能用于论文、真实筛选或统计分析。

从 `systematic-review` 技能目录运行：

```bash
python3 scripts/review_state.py prisma examples/rct-pairwise --format markdown
```

预期：

- 3 条来源题录；其中 1 条是跨来源重复。
- 2 份报告，分别表示同一合成试验的主要报告与随访报告。
- 2 份报告均纳入，但只计 1 项研究。
- 定量合成研究数为 null，因为没有执行任何 Meta 分析。

修改副本可以观察 partial 状态：移除一条全文判断、删除 study_link，或将当前 protocol_version 改为 v2。把全文状态改为 sought 时还须移除该报告的全文判断，否则会因“尚未取得全文却已作全文判断”得到错误。不要编辑本例后将合成人工批准复制到真实项目。

字段和导入方式见 `../../references/review-records.md`。
