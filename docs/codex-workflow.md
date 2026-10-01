# 在 Codex 中运行完整科研流程

本仓库保留 Claude Code 插件，并提供可独立安装的 Codex 插件。Codex 通过 `omp`
skill 进入九个工作流，复用同一套研究技能、`.pipeline` 数据和系统综述工具。

## 安装与初始化

需要 Node.js、Codex；研究脚本使用 Python 3.11+，Meta 分析另需 R、metafor、jsonlite。
在仓库运行 `./scripts/install-codex-plugin.sh`；Windows 运行
`powershell -ExecutionPolicy Bypass -File .\scripts\install-codex-plugin.ps1`。
也可使用跨平台命令 `node scripts/manage-codex-plugin.mjs install`。

安装器保留其他 marketplace 条目，将 skills 实体复制进安装包，并尝试通过 Codex
app-server 安装和核对启用状态。自动安装不可用时，在 Codex `/plugins` 中找到
**Oh My Paper** 并安装。安装后开新会话。

在研究项目中告诉 Codex：

> 用 omp 初始化这个研究项目。主题是……，类型为 systematic-review，从 survey 开始。

`omp` 会读取 setup 工作流并运行 `skills/omp/scripts/project.mjs`。它创建缺失的
研究概要、任务表、十个记忆文件和适用的方案草稿；向现有 `AGENTS.md` 增加自身
标记块；安装 `.codex/agents/omp-*.toml`。已有资料、任务 ID 和自定义角色保留。
初始化后再次开启会话以加载项目角色。CLI 不自动注册 `/omp-setup` 之类的命令。

完整流程中先运行只读 `omp/scripts/workflow.mjs` 核对阶段、依赖与产物。
“选题”请求不能跳过 survey；原 OMP 选题依次完成五方向 idea board、评估范围确认、
idea eval 和最终用户选题。不要用独立的 2–4 候选收敛替代它。
每项已验证工作结束后，自动执行下一项已授权任务，仅在真实研究决策处等待用户。

需要直接运行时，从实际安装位置确定 `OMP_SKILLS`。默认安装的示例为：

```bash
OMP_SKILLS="$HOME/plugins/oh-my-paper-codex/skills"
node "$OMP_SKILLS/omp/scripts/project.mjs" init --project /path/to/research --topic "研究主题" --track systematic-review --stage survey
node "$OMP_SKILLS/omp/scripts/project.mjs" status --project /path/to/research
```

`status` 只读，返回初始化状态、技能资源可用性和任务数；不判断临床研究是否完成。
若移动插件，重跑 init 可更新路径，不会重置已有研究文件。

## 九个入口与五阶段

| 对 Codex 说 | 执行入口 | 主要产物 |
|---|---|---|
| 用 omp 初始化项目 | setup | AGENTS.md、项目角色、brief、记忆与任务表 |
| 用 omp 规划／继续当前项目 | plan | 任务、依赖、execution_context |
| 用 omp 调研这个主题 | survey | 可追溯题录、文献库、研究空白 |
| 用 omp 确定研究方向／综述方案 | ideate | 已选方向，或 PICO、protocol、SAP |
| 用 omp 执行当前实验／正式综述 | experiment | 运行、结果和图表台账 |
| 用 omp 写作／制作汇报材料 | write | 稿件；promotion 阶段的汇报文件 |
| 用 omp 评审当前稿件 | review | review_log 与待修改项 |
| 用 omp 委派这个任务 | delegate | 原生子代理结果及已验证的交接 |
| 用 omp 同步项目状态 | sync | tasks、project_truth、各角色记忆 |

五阶段保持 survey → ideation → experiment → publication → promotion。
ML、生信以 exploratory 为默认；临床、系统综述以 confirmatory 为默认。
已给出的任务和授权沿用，不重复询问角色。需要研究判断的关口仍由研究者决定。

## 系统综述的完整路径

1. **探索**：检索已有综述和关键研究，判断可行性；精选阅读不计作正式筛选。
2. **方案**：明确 PICO、纳排、检索式、结局时间窗与 SAP，记录实际研究者对具体版本的批准和真实注册状态。
3. **正式检索与导入**：用 pubmed-search 保留批次、原始响应和完整性；RIS/CSV 可预览导入，partial 检索不能报为 complete。
4. **筛选与研究归并**：分别保存 record/report/study 身份、人工决定和裁决；无法获取全文不算资格排除。
5. **提取与分析**：保存数值出处与核对，完成结果级 RoB 2 和可合并性判断；当前适配器执行平行两组 RCT 的 RR/MD/SMD，或保留有理由的叙述性综合。
6. **写作与报告**：核对当前分析、引用与检索筛选记录，生成写作交接包；继续完成 GRADE、SoF、PRISMA、正文和审稿。
7. **汇报**：按用户需要从已确认材料制作汇报文件，不自动发布。

方法和字段规范以共享资源为准：

- [RCT profile](../skills/systematic-review/references/rct-pairwise-profile.md)
- [检索与恢复](../skills/pubmed-search/SKILL.md)
- [记录、筛选与 PRISMA](../skills/systematic-review/references/review-records.md)
- [提取与分析](../skills/systematic-review/references/extraction-and-analysis.md)
- [写作交接](../skills/systematic-review/references/writing-handoff.md)

从实际 skills 目录调用已有工具即可，例如：

```bash
python3 "$OMP_SKILLS/systematic-review/scripts/review_state.py" validate .pipeline/systematic-review
python3 "$OMP_SKILLS/systematic-review/scripts/review_state.py" prisma .pipeline/systematic-review --format markdown
python3 "$OMP_SKILLS/systematic-review/scripts/meta_analysis.py" validate .pipeline/systematic-review --plan /path/to/analysis_plan.json
python3 "$OMP_SKILLS/systematic-review/scripts/meta_analysis.py" run .pipeline/systematic-review --plan /path/to/analysis_plan.json --out /path/to/new-run
python3 "$OMP_SKILLS/systematic-review/scripts/writing_handoff.py" check .pipeline/systematic-review --config /path/to/publication.json
python3 "$OMP_SKILLS/systematic-review/scripts/writing_handoff.py" build .pipeline/systematic-review --config /path/to/publication.json --out /path/to/new-handoff
```

产物校验不能代替真实研究材料或人类判断。合成案例、BCG 数值基准不能冒充完成的
临床综述；自动全文提取、人工 RoB/GRADE 和真实临床端到端验收的边界保持原样。

## Hooks、恢复与委派

插件注册 SessionStart、PostToolUse、Stop、SubagentStop。Codex 要求用户在 `/hooks`
中审查信任定义；安装器不替用户设置可信状态。未启用 hooks 时，AGENTS.md 仍指导
Codex 读取状态、核验任务并更新记忆。

SessionStart 每次生成当前上下文；PostToolUse 检查真实任务文件变化，写一次阶段
评审提醒；Stop/SubagentStop 只将结构化 executor report 记为 pending-review。
hooks 不改任务完成状态、不代替方案审批。委派使用实际 agent/session 句柄；
CLI 后备路径为 `codex exec`，不用旧完成标记或不存在的后台参数。

## 开发与验证

`plugins/oh-my-paper-codex/prompts/` 和 `agents/` 是工作流文本与角色的维护源。
修改后运行 `npm run codex:sync` 将它们同步为 `omp` skill 的独立资源；
`npm run check` 校验复制一致性并运行安装、项目初始化、hooks 和研究工具回归。
完整统计验证使用 `OMP_REQUIRE_R=1 npm run check`，要求 R 依赖实际存在，不接受跳过。
安装 Codex CLI 后可运行 `npm run codex:runtime:check`，只读检查其实际发现的技能和
hooks，不启动模型任务。[本次迁移验证记录](codex-migration-validation.md) 列出检查范围和结果。
验证实际启用的个人插件及缓存内容请运行 `npm run codex:runtime:check -- --installed`。
[流程修复与真实对话回放](codex-routing-fix-validation.md) 补充了调研前选题和调研后自动衔接的验证。
[选题之后的衔接](codex-downstream-handoffs.md) 说明证据整合、写作、核验、评审、返修和复审如何按具体任务衔接。
[连续执行与整链验收](codex-continuous-workflow.md) 说明会话绑定、提前收尾续行、真实停点以及本机 hook 信任检查。

官方接口依据（2026-09-30 核对）：
[插件打包](https://developers.openai.com/plugins/build/plugins)、
[自定义子代理](https://developers.openai.com/codex/subagents)、
[Hooks](https://learn.chatgpt.com/docs/hooks)。现有 `.codex-plugin/plugin.json`
仍是官方支持的兼容格式，项目角色要求 `developer_instructions` 为字符串。
