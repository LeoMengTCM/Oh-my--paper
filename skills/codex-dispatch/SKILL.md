---
name: codex-dispatch
description: Execute authorized OMP research tasks in a separate Codex CLI process when Claude Code or Qoder selects Codex; also supports explicit standalone Codex delegation.
version: "1.2"
stages: [survey, ideation, experiment, publication, promotion]
---

# Codex dispatch

## 宿主 Agent 项目委派（Claude Code / Qoder）

先读取 [execution-routing.md](references/execution-routing.md)，使用其中的项目配置与 `scripts/executor.mjs` 实际派发所有已授权研究任务。选择 Codex 后不能以宿主原生子代理替代，也不能失败后静默回退。setup 的选择不是可用性提示，而是必须保存和遵守的执行策略。

Qoder 与 Claude Code 共用同一套 `/omp:*` 命令、角色 agents 和 hooks。执行器配置里的 `claude` 表示由当前宿主 Agent 执行（在 Qoder 上即 Qoder 本身），不要因此启动 Claude Code 或把它当成另一个子代理。

`OMP_CODEX_DISPATCH=1` 时已经是执行子进程：完成当前任务并返回，不递归派发，不注册全项目续行。

## Codex 原生或独立 CLI 委派

以下原生子代理优先规则仅适用于已经运行在 Codex 内的独立会话，不适用于 Claude Code / Qoder 项目选定 Codex 的执行器路由。

Prefer native Codex subagent tools for already-authorized delegation. Use a separate
CLI process when requested or when native agents are unavailable. Inherit the
session model preference; do not pin a model without an explicit requirement.

Write the task, context, allowed files, expected artifacts, and validation commands
to a prompt file. Pass it through stdin, avoiding shell interpolation of its contents:

```bash
codex exec --cd /path/to/project --json --output-last-message /path/to/run/result.md - < /path/to/run/prompt.md
```

Use a new run directory for each dispatch. Keep the returned process/session handle
and poll it to completion. A timeout is not proof of failure. Verify the exit code,
result and artifacts before updating task state; old handoff markers are not job IDs.
If execution requires unavailable permissions or credentials, report the specific
failure and continue independent work. Do not use unsupported `--background`,
`--approval-mode`, `-p` prompt, or `--cwd` flags, or bypass sandbox/approval policies.
