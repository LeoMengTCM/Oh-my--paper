# 选题之后的 OMP 衔接

本页对应完整论文任务；单独的写作、审稿、同步任务仍遵守用户指定范围。

| 当前产出 | 必须交给下一步的内容 | 下一操作 |
|---|---|---|
| 选题评估、用户最终选择 | 选定方向、论证边界、评估依据、未决问题 | 规划并执行证据整合/实验 |
| 证据整合或实验 | 论点—来源/结果矩阵、限制、图表台账、result_summary | 按既定提纲完成正文与图注 |
| 当前版本稿件 | 实际稿件路径/版本、引用库、证据与覆盖检查 | 引用/一致性核验、科学评审 |
| 有问题的评审报告 | 问题 ID、具体位置、依据、修复任务 | 补证或返修 |
| 修订稿 | 问题到修改的对应表、变更后的稿件版本 | 复审当前版本 |
| 实质问题已解决 | 当前稿件及有效检查、实际目标刊物要求 | 投稿准备检查与用户要求的交付 |

证据不足先回到补证，再修改论证；不能用润色掩盖来源缺口。评审任务完成只表示报告
写完，不代表稿件通过。旧版检查不能自动给新版放行；返修和复审任务需建立依赖，
不能在问题尚未处理时跳到 promotion。实际投稿、上传和发送需要相应授权。

对于叙述性综述，experiment 阶段表示文献证据整合。按 `projectContext.researchType`
或明确的 articleType 识别，兼容值 `track=ml` 不能强制训练、消融、ML 章节或会议格式。
稿件保留实际 Markdown、Word 或 LaTeX 格式；不因为某个默认脚本只接受 LaTeX 就重建项目。

## 任务如何路由

`workflow.mjs` 先检查阶段和依赖，再看具体任务的 `workflow`、`suggestedSkills`、
`assignee` 与状态。publication 内的写作、审稿、引用核验和投稿检查不再统一交给 writer。

```json
{
  "id": "submission-check",
  "stage": "publication",
  "status": "pending",
  "workflow": "review",
  "taskType": "gate",
  "checkpointType": "artifact",
  "suggestedSkills": ["submission-checker"],
  "dependencies": ["revision-recheck", "integrity-check"]
}
```

`checkpointType=artifact` 表示执行产物检查；`user` 表示必须由研究者决定。
旧 gate 未分类时先核对其用途和已有授权，不把协议批准降为普通文件检查。
完整写作已授权时连续完成章节和常规修复，不逐节要求用户说“继续”。

## 已做的代码与指令修复

- 按任务路由 write/review，并返回 integrity-auditor/submission-checker 等具体处理技能。
- 审稿退回 experiment 补证时，同样核对作为依赖的评审报告。
- experiment、write、review、Conductor 和对应角色均补充叙述性综述分支与收尾要求。
- review 明确问题 → 修复 → 复审；sync 不再以重复的下一步菜单结束已授权流程。
- 初始化器记录自身管理的角色版本，更新未被用户改动的旧角色；自定义角色保留。
- 实际安装检查覆盖 omp 入口、初始化/路由脚本、九个工作流和五个角色的缓存内容。

验证结果见 [后半程验证记录](codex-downstream-validation.md)。
