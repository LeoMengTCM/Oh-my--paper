# Claude Code / Qoder 的执行器路由

本规则用于 Claude Code / Qoder 主会话及其角色。Codex 原生会话不因为项目配置为 codex 就再次派发。`OMP_CODEX_DISPATCH=1` 表示已在执行子任务，必须直接完成当前授权范围，不注册 continuation、不递归调用 runner。

## 每次入口都读取配置

从当前加载插件的实际 skills 目录定位本 skill，不优先使用项目里可能过期的 `.claude/skills` 副本。以下 `OMP_SKILLS` 必须先替换为该绝对路径：Claude Code 通常为 `${CLAUDE_PLUGIN_ROOT}/skills`，Qoder 为 `${QODER_PLUGIN_ROOT}/skills`；环境变量不可用时从已加载的 `SKILL.md` 路径反推。

```bash
node "$OMP_SKILLS/codex-dispatch/scripts/executor.mjs" status --project "/实际研究目录"
```

- `unconfigured`：旧项目尚未保存执行器，询问一次 `使用 Codex 执行任务` / `使用当前 Agent 执行任务`。将已有明确选择保存，不要求用户重答。不要重建 brief、tasks 或研究文件。
- `configured`：沿用 `executor`，不因新会话、阶段变化、角色切换或后面的专业分支而忽略它。
- 配置无法读取或无效：停止执行并报告；不能把错误当成“使用当前 Agent”。

用户确认后保存：

```bash
node "$OMP_SKILLS/codex-dispatch/scripts/executor.mjs" configure --project "/实际研究目录" --executor codex
```

选择当前 Agent 时将 `codex` 改为 `claude`（Qoder 上也保存为 `claude`）。重复 setup 保留选择；更改已有选择须用户明确同意，再加 `--replace`。`onFailure` 固定为 `stop`，不自动回退。

## 谁执行什么

主 Agent 负责：读取状态、向用户提问、记录真实决定、准备任务包、验收结果、根据证据维护任务与进度。setup 与 sync 的状态维护仍由主 Agent 完成。选择 `claude`（当前宿主 Agent）时，研究工作按现有 skill / 角色执行。

选择 `codex` 时，下方命令中的“运行脚本”“调用 skill”“写正文”“生成报告”是交给 Codex 的任务说明，**不是主 Agent 直接执行这些研究工作的授权**。不使用宿主原生子代理替代 Codex。适用于所有研究类型，包括提前返回的 narrative-review / systematic-review 分支：

| 入口 | Codex 执行的工作 |
|---|---|
| plan | 根据已确认研究目标生成或修订具体研究计划、任务与依赖草案 |
| survey | 检索、下载和已授权 OCR、书目生成、文献整理及证据分析 |
| ideate | 全文总结、方向或综述框架生成、适用的评估、研究方案草案 |
| experiment | 实验设计/实现/运行，或综述证据提取、核对与综合 |
| write | 正文和图表制作、修订及稿件检查 |
| review | 对指定版本只评不改，生成报告 |
| delegate / promotion | 已授权的其他明确任务，不包含未经确认的投稿或上传 |

交互点仍由主 Agent 处理。比如 survey 先派发检索，返回摘要表后由用户选文；再派发获准的下载/OCR，不能将尚未确认的整个阶段一次交出去。已有完整授权时不重复询问 routine 步骤。缺少 Codex 可用的浏览器、MCP、网络或凭据时报告具体阻塞，不假定继承宿主的工具，不转由主 Agent 偷做同一任务。宿主已拒绝的操作不得交给 Codex 绕过。

## 实际派发

1. 为本次任务创建新的 `.pipeline/dispatch/<唯一任务名>/`，写入 `prompt.md` 和 `request.json`。任务说明包含已确认范围、适用研究类型、写作语言、输入文件、实际 skill 的绝对路径、方法审批与验证命令。不要写凭据。只提供完成当前任务所需的资料。
2. `request.json` 的路径均相对研究目录，至少一个产物必须由本次生成或内容更新。允许修改目录不是沙箱，仍须遵守 Codex/宿主权限。计划任务建议先写草案再由主 Agent 验收合并；不把任务状态更新当作研究产物。

```json
{
  "version": 1,
  "intent": "survey",
  "promptFile": ".pipeline/dispatch/survey-001/prompt.md",
  "allowedPaths": [".pipeline/literature", ".pipeline/docs/survey_report.md"],
  "artifacts": [".pipeline/docs/survey_report.md"]
}
```

3. 用宿主 Bash 工具实际执行（耗时任务可用宿主的 `run_in_background`，不是 Codex 的命令行 flag）：

```bash
node "$OMP_SKILLS/codex-dispatch/scripts/executor.mjs" run --project "/实际研究目录" --request ".pipeline/dispatch/survey-001/request.json"
```

runner 使用 `codex exec --cd ... --skip-git-repo-check --json --output-last-message ... -`，通过 stdin 传入任务，继承模型与默认沙箱设置。若确实需要修改研究目录而当前沙箱只读，先说明缺失权限；只有获准且宿主政策允许，才在请求中明确加入 `"sandbox": "workspace-write"`。禁止自动扩大权限或使用危险绕过选项。

4. 保留宿主返回的实际进程句柄。stdout 中 `starting` 不代表已启动；`running` 包含 PID；结束后的状态必须读取该次 `.pipeline/runs/<runId>/status.json`。后台超时或旧 `running` 记录不是成功，不用历史 handoff 标记证明完成，也不要在旧进程尚未确认结束时重复派发。
5. `ready_for_review` 仅说明退出码、完成事件、最终回复及本次产物检查通过。主 Agent 还要读真实产物并按专业标准验收，检查 partial、引用、研究方法和用户决定。只有验收后才能更新任务状态；失败或有阻塞时不宣称任务已完成。
6. `failed` / `blocked`：显示错误和该次 `stderr.log`、`result.md` 的相关信息；保留失败产物供检查，不切换回主 Agent。由用户决定修复环境、重新派发或明确切换执行器。
