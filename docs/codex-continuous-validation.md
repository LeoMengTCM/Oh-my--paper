# 整链与原生自动续行验收

核对日期：2026-10-01。验收目标：已授权的 OMP 工作从初始化持续衔接到约定交付，
普通阶段转换无需用户提醒；真实作者决定、外部缺口和明确暂停保持有效。

## 验收结果

| 检查 | 当前证据 |
|---|---|
| 自动回归 | Node 46 项、Python 116 项，合计 162 项通过，0 失败、0 跳过；包含真实 R 计算 |
| 整链真实 Codex 回放 | 从初始化到 publication 交付，13/13 任务完成 |
| 作者交互 | 只回复评估范围和最终选题两次决定；用户流程提醒 0 次 |
| 整链续行 | 三次会话交互完成；未发生额外提前停止，驱动器没有发送自动补救消息 |
| 原生 Stop 自动续行 | 单次 codex exec 内，第一步故意提前结束后由宿主 hook 自动接回，第二步完成并 finish |
| 实际安装 | 会话加载的入口、脚本、九个工作流、五个角色及 hook 实现匹配当前仓库 |
| 本机运行状态 | 四个 OMP hooks 均 enabled=true、trustStatus=trusted；automaticContinuationReady=true |

## 整链回放覆盖

使用 `python3 scripts/eval-codex-pipeline.py`，在隔离临时项目中执行：

初始化 → survey → 五方向 idea board → 确认评估范围 → idea eval → 最终选题 →
证据整合 → 正文 → 引用/一致性核查 → 科学评审 → 必要返修记录 → 复审 →
本地交付规范检查 → 交付与最终完成审查。

驱动器只提供“全部五个方向评估”和“选择第一个方向”两次模拟作者决定，未提供
任何“下一步”“继续流程”提醒。代码具备 Stop 回调回放能力，但本轮使用次数为 0：
模型自己持续执行到下一真实决定或最终交付。

已逐项检查 13 个任务的 done、artifacts、completionSummary，核实所有登记文件存在，
最终稿与 delivery_report 已生成，当前会话 continuation 状态为 complete。材料明确
标为虚构软件测试，不能用来声称真实文献充分或稿件达到真实刊物要求。

初始化曾遇到运行环境对 `.codex/agents` 写入的限制，后续交互中已补齐角色文件。
该记录保留在回放交付报告中，不把初次初始化失败隐去。正式研究中的实际权限或
外部材料问题仍应明确报告，不能冒充完成。

## 原生自动续行测试

为单独检验运行时保护，另建只有 first/second 两项任务的隔离项目，明确要求：

1. 注册本会话目标，只完成 first.txt=FIRST，保持 second=pending，故意发出第一阶段最终回复。
2. 不手动执行 codex-hook.mjs、stopDecision 或 codex resume，不修改信任或内部状态文件。
3. 收到宿主 Stop hook 续行后，完成 final.txt=FINAL，再通过正式 finish 命令结束。

实际单次 `codex exec` 完成了上述过程。检查了只有一个线程、第一阶段最终回复、
之后的第二步执行、continuation.lastEvent 中保留的提前收尾事件、完整终态及文件
精确内容。执行轨迹没有手动 hook 调用或 resume 命令。该测试在 hooks 已 trusted 的
真实宿主上运行，没有使用信任绕过参数。

## 本机就绪检查

```bash
node scripts/check-codex-runtime.mjs --installed --project /path/to/research --require-hooks
```

上一次检查为 modified/untrusted，本次重新读取已全部 trusted。助手没有写入信任
设置，结论来自当前 Codex app-server 的 hooks/list。安装器也不会替用户批准 hooks。

连续模式绑定具体会话与已授权范围，其他会话和单次任务不受控制。用户承担的任务
（例如明确自行重绘图）是合法等待点，不会自动代做或标为完成。外部投稿/上传不属于
这次验收范围；promotion 仅在用户请求时进入。未提交、推送或发布代码。
