# Qoder 支持

Oh My Paper 现在同时支持 Claude Code 和 Qoder。两套宿主共用同一份 `plugins/oh-my-paper`：

| 组件 | Claude Code | Qoder |
| --- | --- | --- |
| 清单 | `.claude-plugin/plugin.json` | `.qoder-plugin/plugin.json` |
| 命令 | `/omp:*` | `/omp:*` |
| 角色 agents | `agents/*.md` | `agents/*.md` |
| Skills | `skills/` | `skills/` |
| Hooks | `hooks/hooks.json` | `hooks/qoder-hooks.json` |

Qoder 的 `.qoder-plugin/plugin.json` 显式声明了 `hooks`，因此不会额外加载 Claude Code 的 `hooks/hooks.json`。

## 安装

### 方式一：ZIP 上传（推荐）

Qoder Desktop 当前版本没有随附 `qodercli`，用插件市场导入最直接。

```bash
npm run qoder:package
```

该命令生成 `dist/omp-qoder-<version>.zip`。ZIP 根目录直接包含 `.qoder-plugin/`，符合 Qoder 的插件包要求；仓库里 `plugins/oh-my-paper/skills` 是指向根目录 `skills/` 的符号链接，打包脚本会把它解引用成真实文件。

然后在 Qoder 中：

1. 打开 **Extensions → Plugins**；
2. 点击 **Add Plugin → Upload Plugin**；
3. 选择 `dist/omp-qoder-<version>.zip`；
4. 确认安装并启用；
5. **新建一个对话**（插件在会话启动时加载）。

### 方式二：本地目录（有 qodercli 时）

```bash
qodercli plugins install /path/to/Oh-my--paper/plugins/oh-my-paper
# 部分版本使用 qoder plugins install ... 或 qodercli plugin install ...
```

如果当前 Qoder 版本把 `qodercli` 放在 `~/.qoder/bin/qodercli/`，使用其中的可执行文件。注意：本地目录安装会跳过指向插件根目录之外的符号链接，可能丢失 `skills/`；需要完整技能时请用 ZIP。

## 验证

新建对话后：

1. 输入 `/`，确认出现 `/omp:setup`、`/omp:plan`、`/omp:survey` 等命令；
2. 在 Qoder 的 Agents 面板确认 `conductor`、`literature-scout`、`experiment-driver`、`paper-writer`、`reviewer` 五个角色；
3. 在研究项目里运行 `/omp:setup`，检查 `.pipeline/`、`.pipeline/docs/research_brief.json` 和 `.pipeline/tasks/tasks.json` 是否生成；
4. 新开一次会话，确认 SessionStart hook 会提示选择工作模式。

## 与 Claude Code 的差异

- **执行器 `claude`**：`.pipeline/execution.json` 里的 `claude` 表示“由当前宿主 Agent 执行”。在 Qoder 上就是 Qoder 本身，不会启动 Claude Code。选择 `codex` 时仍通过 `codex-dispatch` 启动 Codex CLI。
- **Skills 副本**：Qoder 直接加载插件里的 skills，`/omp:setup` 不再把技能复制到项目的 `.claude/skills/`。Claude Code 仍保留该可选的兼容步骤。
- **Hooks**：Qoder 使用 `${QODER_PLUGIN_ROOT}`，并额外匹配 `MultiEdit`、`NotebookEdit`；Stop hook 优先读取 Qoder 提供的 `last_assistant_message`，Claude Code 继续走 transcript 解析。
- **续行**：Codex 的持续执行注册只适用于 Codex 会话。Qoder 像 Claude Code 一样使用 `/omp:*` 命令和角色 agents，不注册 Codex continuation。

## 更新

修改插件后重新打包并重新上传 ZIP 即可。Qoder 不会热更新已加载的插件，安装或更新后需要新建对话。

## 排查

- **看不到 `/omp:*`**：确认插件已启用；新建对话或重启 Qoder。插件只在会话启动时加载。
- **Skills 缺失**：确认安装的是 ZIP，而不是直接导入 repo 里的 `plugins/oh-my-paper` 目录；目录安装会跳过越界的 `skills` 符号链接。
- **Hook 报错**：确认 `hooks/qoder-hooks.json` 使用 `${QODER_PLUGIN_ROOT}`；运行 `npm run qoder:package` 会检查这一点。
- **角色 agents 不可见**：确认安装后的插件目录包含 `agents/conductor.md` 等五个文件，并在新对话中查看 Agents 面板。
- **Codex 派发失败**：先运行 `codex --version` 和 `executor.mjs status`，再按 `.pipeline/execution.json` 的配置处理；Qoder 不会自动回退到自身执行。
