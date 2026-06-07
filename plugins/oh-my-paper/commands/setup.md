---
name: setup
description: 初始化研究项目结构（.pipeline/），并检查 Codex 插件是否就绪
---

> **确认或选择类步骤用 AskUserQuestion 工具。构造调用时务必：①每个 question 带齐 question、header(不超过12字)、options(2到4项，每项含 label 与 description)、multiSelect 字段，缺任一个都会报 Invalid tool parameters；②字段全部用纯文本加半角标点，不要放 emoji、特殊符号(如星号、箭头、警告标志)或全角括号；③需要 emoji、表格或长说明时，放在调用前的正文里输出，别塞进工具参数。payload 越精简越不容易出错。**

你正在为当前目录初始化 Oh My Paper 研究 harness。

## 第一步：检查 Codex 插件

先确认 Codex 插件已安装。如果 `/codex:setup` 命令可用，运行它：

```bash
node -e "process.exit(0)" 2>/dev/null && echo "Node.js OK"
which codex 2>/dev/null && codex --version 2>/dev/null || echo "Codex not found"
```

用 `AskUserQuestion` 告知状态：

> **环境检查**：
> - Node.js：[OK / 未安装]
> - Codex CLI：[版本 / 未安装]
>
> Codex 插件用于执行子任务。如果未安装：
> `/plugin install codex@openai-codex` 然后 `/reload-plugins`

选项：
- `Codex 已就绪，继续初始化`
- `先去安装 Codex，稍后再运行 /omp:setup`

## 第二步：询问研究信息

用 `AskUserQuestion` 收集项目基本信息：

> 请描述你的研究项目：
> - 研究主题是什么？（例：多模态医学影像分割）

然后再问：

> 从哪个阶段开始？

选项：
- `survey（文献调研）`
- `ideation（创新点生成）`
- `experiment（实验）`
- `publication（论文写作）`

然后问研究类型（决定阶段含义、硬闸门、作图时机与质量门）：

> 这是哪类研究？

选项：
- `ml — 机器学习 / 计算实验`
- `clinical — 临床研究（RCT / 队列 / 病例对照 / 诊断等；需注册与伦理审查）`
- `systematic-review — 系统综述 / Meta 分析（需 PROSPERO 注册）`
- `bioinformatics — 生物信息学（组学流程，常用 HPC）`

记下选择写入 `pipeline.track`。clinical / systematic-review 自动设 `analysisMode = confirmatory`，其余为 `exploratory`。

## 第三步：创建目录结构

```bash
mkdir -p .pipeline/memory .pipeline/tasks .pipeline/docs .pipeline/.hook-events .claude/skills
cp -rn "${CLAUDE_PLUGIN_ROOT}/skills/." .claude/skills/
```

> **关于 hooks**：SessionStart / Stop / PostToolUse 三个 hook 已由插件自带的 `hooks/hooks.json` 提供，**插件启用即生效，无需在项目里重复注册**。（早期版本曾在这一步手动把 SessionStart 写进 `.claude/settings.json`，与插件自带的那份重复、会导致每次开会话角色选择触发两次，现已移除。）

## 第四步：写入初始文件

创建以下文件（已存在则跳过）：

**`.pipeline/docs/research_brief.json`**：
```json
{
  "topic": "[用户填写的主题]",
  "goal": "",
  "currentStage": "[用户选择的阶段]",
  "pipeline": {
    "track": "[ml|clinical|systematic-review|bioinformatics]",
    "analysisMode": "[clinical/SR 填 confirmatory，其余 exploratory]",
    "startStage": "[用户选择的阶段]"
  },
  "successThreshold": "成功标准（confirmatory 研究：填主要结局与预设分析，而非可反复迭代的阈值）"
}
```

> clinical / systematic-review track 额外创建冻结计划与偏离记录：`.pipeline/docs/protocol.md`、`.pipeline/docs/sap.md`（统计分析计划）、`.pipeline/memory/protocol_deviations.md`。它们是预注册的依据——锁定后不得随意改写，任何变更记入 deviations。

**`.pipeline/memory/project_truth.md`**：
```markdown
# Project Truth

## 研究主题
[主题]

## 已确认决策
（空，随项目推进逐步填充）
```

**`.pipeline/memory/orchestrator_state.md`**、**`execution_context.md`**、**`review_log.md`**、**`agent_handoff.md`**、**`decision_log.md`**、**`literature_bank.md`**、**`experiment_ledger.md`**：均创建空白初始版本。

**`.pipeline/tasks/tasks.json`**：
```json
{"version": 1, "tasks": []}
```

## 第五步：完成确认

> ✅ 研究项目初始化完成！
>
> **项目**：[主题]
> **起始阶段**：[阶段]
>
> 接下来：
> - 运行 `/omp:plan` 查看整体状态
> - 运行 `/omp:survey` 开始文献调研（如果从 survey 阶段）

选项：
- `开始！运行 /omp:plan`
- `我先自己看看文件结构`
