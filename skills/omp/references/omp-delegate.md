---
description: 使用 Codex 原生子代理委派已授权任务，验证产出并同步项目记录
---

OMP 项目先读取实际 skills 目录下 `omp/SKILL.md`，运行 `omp/scripts/workflow.mjs` 检查当前阶段、依赖和产物后再执行本入口。单次任务与已授权全流程分别按原范围执行。


沿用当前会话已明确的意图、参数和授权；下文的确认步骤仅用于尚未决定的研究判断或范围变化。已有明确下一步时继续执行。


# Delegate

读取 project_truth.md、execution_context.md、decision_log.md、agent_handoff.md
和 research_brief.json；用 task-contract.mjs 校验 tasks.json。复用本会话已授权的
委派范围。尚未确定任务时，先把任务、输出路径、验收标准和依赖具体化。

优先使用当前 Codex 会话提供的原生子代理工具，并选择 .codex/agents/omp-*.toml
中相应角色。若自定义角色尚未加载，将对应角色指令放入任务上下文。
角色继承会话模型；不要擅自指定模型或降低执行权限要求。

给子代理明确任务 ID、背景、已否决方向、允许修改的文件、验收命令和交付要求。
独立任务才并行，避免多个代理同时改 tasks.json 和共享记忆；主代理负责合并这些更新。
保存工具返回的 agent/session ID，通过实际工具等待/读取结果。超时继续检查同一
句柄；不要凭旧 CODEX_DONE 标记判定本次任务完成，也不要因观察超时重启工作。

没有原生子代理且任务确需独立进程时，读取 codex-dispatch/SKILL.md，使用
`codex exec` 的 stdin 文件输入和进程退出状态。环境不支持委派时，在当前会话完成
已授权工作，并说明采用同会话角色。

读取真实产物并运行相应验证，汇报文件、结果与未解决问题。需要研究者判断的内容
保留 review；其余按验收证据更新任务和 project_truth.md。更新 agent_handoff.md
记录本次任务、过程句柄和结果。不得把两名 AI 描述为两名人类筛选者。
