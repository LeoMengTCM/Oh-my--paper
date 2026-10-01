# `tasks.json` Schema

`.pipeline/tasks/tasks.json` 的统一任务契约。

```json
{
  "tasks": [
    {
      "id": 1,
      "title": "<string>",
      "description": "<string>",
      "status": "pending",
      "stage": "survey|ideation|experiment|publication|promotion",
      "priority": "high|medium|low",
      "dependencies": [],
      "taskType": "exploration|implementation|analysis|writing|scripting|rendering|narration|delivery|gate|figure",
      "inputsNeeded": ["sections.ideation.research_goal"],
      "suggestedSkills": ["inno-idea-generation"],
      "sourceBlueprintId": "<string>",
      "nextActionPrompt": "<string>",
      "createdAt": "<ISO timestamp>",
      "updatedAt": "<ISO timestamp>"
    }
  ]
}
```

## 读写兼容规则

在 Codex 的 OMP 流程中，完成任务时可追加 `artifacts`（项目内实际文件路径数组，
也接受含 `path` 的对象）和 `completionSummary`（核查范围、结果与局限）。
`omp/scripts/workflow.mjs` 以只读方式检查阶段顺序、依赖与产物可用性；不把这些
字段当作研究真实性或人工批准。旧项目缺字段时先核读已有产物并补记，不清空任务、
重跑已完成的研究或伪造历史审批。

同一 publication 阶段的不同操作用可选 `workflow` 指定（如 `write`、`review`），
并以 `suggestedSkills` 区分 `integrity-auditor`、`submission-checker`、同行评审和返修。
`checkpointType: artifact` 表示执行产物检查；`checkpointType: user` 表示研究者决策。
旧 gate 没有该字段时先核对其用途与已有授权，不把方案批准自动降为普通文件检查。
写作后的任务依赖应覆盖审查、必要返修和复审；有报告不等于稿件通过。返修任务引用
报告里的具体问题及稿件版本，影响相关核查结果的改动需要重新核查。

- 新建文档统一写顶层 `tasks`，每个任务的依赖写 `dependencies`。读取兼容旧 `master.tasks` 和 `dependsOn`，不得把旧嵌套任务当作零条任务。
- 保留既有数字或字符串 ID 及其类型、状态、任务与文档元数据；尤其不得重编号旧 gate ID 或破坏依赖引用。
- 顶层 `tasks` 与 `master.tasks` 同时存在时，规范化后完全一致才可读取；不一致则停止并报告冲突，不自动选一个或合并。同一任务的 `dependencies` 与 `dependsOn` 冲突时也停止。
- 通过实际安装的技能目录运行共享只读 CLI（从本技能目录解析 `scripts/task-contract.mjs`，不要依赖仓库根目录的 `scripts/`）：

  ```bash
  node "<实际skills目录>/inno-pipeline-planner/scripts/task-contract.mjs" .pipeline/tasks/tasks.json
  ```

  成功时 stdout 输出规范化文档，CLI 不写文件；错误写 stderr 并以状态码 1 退出。仅在成功后使用输出中的顶层 `tasks` 统计和规划；CLI 缺失或失败时停止任务更新和阶段判断，不按空列表继续。
- 规范化输出只作为内存中的读取视图，不自动迁移用户文件。更新旧文件中的任务时保留原容器和依赖字段，只改获准修改的内容；迁移到顶层 `tasks` / `dependencies` 或重新生成前须取得用户同意，并保留旧 ID、状态与元数据。
