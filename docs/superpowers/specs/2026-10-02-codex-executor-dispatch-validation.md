# Codex 执行器派发修复验证

日期：2026-10-02。

## 代码与测试

- 新增 `skills/codex-dispatch/scripts/executor.mjs`，配置独立保存为 `.pipeline/execution.json`。
- Claude 的 setup、八个工作入口和五个角色使用共享执行器规则；会话启动每次读取配置。
- `tests/executor.test.mjs` 的 25 个测试全部通过：配置持久化、所有执行阶段、实际启动及 stdin、失败与旧产物、独立包、软链接入口、模块导入、会话恢复。
- 首次入口测试发现会话缓存和命令未连接；修复后通过。独立检查发现插件 skills 软链接会让 CLI 静默退出；修复真实路径比较并补测试。真实调用准备阶段发现 stdin 模块导入时 argv 为 `-` 导致异常；修复并补测试后才执行真实 Codex。
- 最终 `npm run check` 成功：Node 测试 74 项，73 通过、1 跳过；Python 测试 118 项，107 通过、11 跳过。跳过项均因缺少 R/metafor 统计依赖，与本次执行器测试无关。
- `git diff --check` 通过。源码插件校验仅提示 skills 是软链接；更新后安装包校验通过。

## 真实 Codex 调用

使用本机 `codex-cli 0.159.3`、继承现有模型及沙箱设置，在独立临时目录测试，未传入研究资料或凭据，未提高权限。

- runId：`2026-10-02T08-41-37-168Z-800af89f`
- 实际 Codex PID：18089
- 状态：starting → running → ready_for_review
- 退出码：0
- 期望产物：`smoke-result.txt`
- 已独立读取核对：内容为 `OMP_CODEX_DISPATCH_OK` 加换行；最终回复确认读取验证。
- 本次验证的是实际进程派发与产物回收，不是完整研究流程、检索能力或科学质量验收。

## 本机安装

本机 `oh-my-paper` 市场原本已指向本仓库。使用官方 `claude plugin update omp@oh-my-paper --scope user --json` 更新，不手改注册表或缓存。

- 更新前：1.1.2。
- 更新后：2.1.0。
- 核对 19 个关键安装文件与当前源码一致。
- 从安装副本运行执行器 status，读取临时项目的 Codex 选择成功。
- 没有修改认证、权限设置或任何实际研究目录。
- 用户仍须重启 Claude Code；当前会话已加载的旧指令不会被仓库修改自动替换。
- 旧研究项目没有 execution.json 时，需保存一次执行器选择；已有研究文件不重建。

未提交或推送 git。原有未提交修改保留。
