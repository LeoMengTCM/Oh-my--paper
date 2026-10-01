---
name: codex-dispatch
description: Delegate coding tasks to a separate OpenAI Codex CLI process when native subagents are unavailable or an independent session is requested.
version: "1.1"
stages: [experiment]
---

# Codex dispatch

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
