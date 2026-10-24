---
description: 在 Codex 中初始化 .pipeline、AGENTS.md 和五个项目角色，保留已有研究资料
---

OMP 项目先读取实际 skills 目录下 `omp/SKILL.md`，运行 `omp/scripts/workflow.mjs` 检查当前阶段、依赖和产物后再执行本入口。单次任务与已授权全流程分别按原范围执行。


沿用当前会话已明确的意图、参数和授权；下文的确认步骤仅用于尚未决定的研究判断或范围变化。已有明确下一步时继续执行。


# Setup

复用用户已提供的主题、研究类型、写作语言和起始阶段，仅询问缺失信息。先确认研究目录；不要把插件源码仓库误初始化为论文项目。
类型为 ml / clinical / systematic-review / bioinformatics / narrative-review；阶段为
survey / ideation / experiment / publication / promotion。
类型未明确时先区分文献综述与原始研究，再选择子类：综述为 narrative-review / systematic-review，原始研究为 ml / clinical / bioinformatics；有最多 4 选项限制的交互不能一次列出五类。
定位已加载 omp skill 的实际目录，以其父目录为 OMP_SKILLS。

运行 Node.js 初始化器（将变量替换为已确认值；路径和主题作为独立参数传入）：

```bash
node "$OMP_SKILLS/omp/scripts/project.mjs" init --project . --topic "研究主题" --track "$TRACK" --stage "$STAGE"
node "$OMP_SKILLS/omp/scripts/project.mjs" status --project .
```

`TRACK` 和 `STAGE` 必须来自已确认信息，不把示例值当成研究决定。初始化后将已确认的稿件语言写入 brief 的 `projectContext.writingLanguage`；兼容旧根级 `writingLanguage`，不同时创建两个值。对话语言不自动决定论文语言。

narrative-review 读取实际 skills 目录下 `inno-pipeline-planner/references/narrative-review-profile.md`，默认 exploratory；不生成临床 protocol/SAP，不要求 RCT 注册、IRB、PRISMA 计数或 Meta 分析。ideation 确定综述重点，experiment 提取、核对与综合证据，publication 按主题写作和核验。新项目直接使用 `pipeline.track=narrative-review`，不伪装为 ml 或 clinical；旧项目的 projectContext.researchType/articleType 或根级同名字段继续兼容，类型冲突先核对原始决定，不静默迁移。

脚本创建缺失的 brief、空任务表、十个记忆文件、适用的 protocol/SAP/deviations；
在 AGENTS.md 追加或更新自身标记块，保留外部指令；将五个角色安装到
.codex/agents/omp-*.toml。已有研究内容不覆盖，冲突的任务格式在写入前报错。
`.pipeline/codex.json` 保存实际技能路径。已有且不同的角色文件保留并列出。
空任务表表示尚未规划，不能声称研究已完成。角色变更在新会话加载。

读取或更新任务前，运行 `node "$OMP_SKILLS/inno-pipeline-planner/scripts/task-contract.mjs" .pipeline/tasks/tasks.json`。
新任务写顶层 `tasks` / `dependencies`；读兼容 `master.tasks` / `dependsOn`，
冲突停止，保留旧 ID、状态和元数据，不把规范化输出直接覆盖原任务文件。

systematic-review 读取实际 skills 目录下 `systematic-review/references/rct-pairwise-profile.md`。五阶段不变：survey 探索 → ideation 批准 PICO/方案/SAP → experiment 正式检索、筛选、提取与合成 → publication → promotion。默认 `confirmatory`；批准记录写入 `.pipeline/memory/decision_log.md`，关联批准的方案版本，任务 `done` 本身不是审批证据。注册状态如实记录为 `planned` / `submitted` / `registered` / `not_registered` / `not_applicable`；未注册须用户说明并确认，但不绝对阻断。公开汇总数据不默认要求 IRB；涉及个体数据或其他伦理要求时另行核实。允许错误修复后重跑并记录原因与偏离，不允许为显著性改方案。

若从 experiment 或更晚阶段开始，也须核验既有批准记录；不能用起始阶段跳过适用审批。

## 完成初始化

报告实际创建/保留的文件和状态。接着按用户意图进入 omp 的 plan 或 survey 工作流，
不要建议不存在的自定义 slash 命令。用户已有明确下一步且已授权时继续执行。
原生 hooks 需要 Codex 自身的信任审查；没有启用时由 AGENTS.md 恢复流程，
初始化器不修改用户的 hooks 信任或权限配置。
