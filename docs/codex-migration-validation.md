# Codex 全流程迁移验证

后续用户对话暴露了实际安装版本和流程路由问题；本页的早期软件验证不证明模型
按步骤执行。原因、修复、147 项回归和两次真实模型回放见
[流程修复验证](codex-routing-fix-validation.md)。

日期：2026-09-30。目标：将现有 Oh My Paper 流程接入 Codex，保留共享研究工具及
已有 SR-01 至 SR-05 工作。不替用户开展新的临床研究，不提交、不推送、不发布。

## 需求与证据

| 要求 | 实现 | 当前验证 |
|---|---|---|
| 可安装、可发现的 Codex 入口 | `skills/omp/SKILL.md`、插件 manifest、安装器 | 本机 Codex 0.159.2 的 `plugin/read` 识别 `oh-my-paper-codex:omp`；仓库与临时独立安装包均通过 |
| 完整九个工作流 | setup、plan、survey、ideate、experiment、write、review、delegate、sync | `codex:check` 对照维护源验证 skill 内九份资源；所有入口链接存在；write 包含 promotion 分支 |
| 五个原生项目角色 | 字符串形式的 `developer_instructions`，初始化到 `.codex/agents/omp-*.toml` | 五份文件逐个通过 TOML 解析，名称匹配文件名，无 model 覆盖 |
| 初始化、恢复及旧项目保留 | `project.mjs init/status`、AGENTS.md 标记块、十个记忆文件 | 四类研究均初始化成功；重复运行无改写；已有任务、方案、外部指令和自定义角色保留；冲突在写入前失败 |
| Codex 原生 lifecycle hooks | SessionStart、PostToolUse、Stop、SubagentStop | Codex 实际读取四个注册事件；真实 stdin JSON 驱动适配器，检查上下文刷新、阶段提醒去重、报告记录与故障恢复 |
| 任务契约一致 | 共享 task-contract.mjs | 兼容 `master.tasks`/`dependsOn`，保留旧 ID；冲突拒绝；双插件阶段脚本通过回归 |
| 系统综述到写作交接 | 共享 RCT profile、检索恢复、记录/筛选、分析与 handoff 工具 | Python 116 项通过，包含真实 R 的 RR/MD/SMD、零事件、单研究、写作导出和公开数值基准 |
| 安装更新可恢复且状态诚实 | 临时拷贝后替换、保留 marketplace 元数据、精确查询安装条目 | 独立包安装/重装/卸载通过；其他条目和项目保留；错误目标不删除；未确认 enabled 不报告安装启用成功 |
| 文档与维护入口 | 中英文 README、codex-workflow.md、同步及检查脚本 | 技能目录、资源同步、插件一致性、链接和 `git diff --check` 通过；CI 加入 Codex 资源检查 |

## 执行结果

设置已有隔离 R 库的 `R_LIBS_USER`，运行：

```bash
OMP_REQUIRE_R=1 npm run check
npm run codex:runtime:check
git diff --check
```

- Node：24 项通过，0 失败，0 跳过。
- Python：116 项通过，0 失败，0 跳过。
- 合计：**140 项通过，0 失败，0 跳过**。
- R 4.6.0、metafor 5.2.1、jsonlite 2.0.0；未向全局库新增依赖。
- 45 个顶层 skill；Codex 还发现既有嵌套 `init-analysis`，共 46 个可加载 skill。
- 运行时返回事件名为 `sessionStart`、`postToolUse`、`stop`、`subagentStop`。
- 临时独立安装包无需仓库根文件，即可初始化研究项目、执行 hook 适配器并被 Codex 读取。

## 验证边界

本次验证是软件迁移验收。真实 RCT 综述仍需合法原文、实际检索与筛选、人工提取核对、
RoB 2、GRADE 和临床判断；之前 SR 验证记录中的这些待办不因迁移而变为完成。

Codex 运行时验证使用只读 app-server API，没有启动模型研究任务，也没有修改用户的
已安装插件、权限或 hook 信任配置。自动安装协议另用可控 app-server 替身验证。
原生 hook 注册已被 Codex 识别，适配器通过事件输入执行验证；要由真实会话自动触发，
仍需用户按 Codex 的 `/hooks` 流程信任插件定义。

本地验证平台为 macOS；Windows 安装入口保留并修正 `.cmd` 启动方式，但未在 Windows
实机运行。未触发远端 CI，版本号保持 2.0.3。
