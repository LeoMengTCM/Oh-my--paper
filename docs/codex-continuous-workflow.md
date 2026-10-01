# 连续执行 OMP：不靠用户提醒下一阶段

完整流程采用检查状态 → 执行 → 核验产物 → 记录 → 再路由的循环。
任务、章节或阶段完成不自动结束工作；只有完整交付、真实研究决策、外部阻塞或
用户明确暂停才允许停下。单次审稿、单段修改等请求仍按原范围完成。

## 会话收尾检查

`skills/omp/scripts/continuation.mjs` 将已授权的完整任务绑定到实际 Codex 会话 ID。
它不启动后台研究、不修改任务完成状态、不代替用户批准方案，也不改变 hooks 信任配置。

```bash
node "$OMP_SKILLS/omp/scripts/continuation.mjs" start --project . --objective "完成约定稿件与检查" --through publication --deliverable Publication/manuscript.md --deliverable Publication/delivery_report.md
node "$OMP_SKILLS/omp/scripts/continuation.mjs" status --project .
```

会话 ID 默认取 Codex 提供的 `CODEX_THREAD_ID`。没有它时必须提供实际 `--session-id`，
不得猜测或绑定到其他会话。目标、截止阶段和交付路径以用户实际请求为准。

已信任的 Stop hook 会在这个会话准备结束时检查：

| 当前情况 | 行为 |
|---|---|
| 有可执行任务、待检查产物或缺失交付物 | 返回 Codex 原生继续指令，自动续行 |
| 当前是用户选择、用户承担的任务或其他真实决定 | 允许停在该具体任务，不当作完成 |
| `wait` 已记录真实外部缺口或用户决定 | 等待所需信息，解决后 `resume` |
| 用户明确要求暂停 | `pause` 后停止 |
| 全范围任务及交付物已核验 | `finish --summary` 后结束 |
| 连续续行仍没有记录任何进展 | 明确报告 stalled，不能伪称完成或无限空转 |
| 其他未注册会话或单次任务 | 不施加连续执行检查 |

`finish` 拒绝未完成任务、缺交付物或缺完成说明。它检查结构条件，稿件内容与
科学证据仍须按当前任务标准实际核验。禁止为退出而把未完成任务写成 done。

需要停在实际缺口时，例如：

```bash
node "$OMP_SKILLS/omp/scripts/continuation.mjs" wait --kind external-blocker --reason "待用户提供其负责重绘的最终图文件"
node "$OMP_SKILLS/omp/scripts/continuation.mjs" resume
node "$OMP_SKILLS/omp/scripts/continuation.mjs" finish --summary "当前稿件、图表、复审和交付文件已逐项核对"
```

不能把“下一阶段还没开始”“想让用户说继续”登记为外部阻塞。

## 必须核对本机 hooks 是否真正运行

安装成功不等于 hooks 已运行。OpenAI 官方要求非托管 hook 在执行前审查并信任其定义：
“Before a non-managed hook can run, Codex requires you to review and trust the exact hook definition.”
见 [Hooks：Review and trust hooks](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)。

```bash
node scripts/check-codex-runtime.mjs --installed --project /path/to/research --require-hooks
```

此命令分别报告已加载内容、每个 hook 的 enabled/trustStatus 和
`automaticContinuationReady`。自动收尾 hook 未启用时退出 2，不能用源码包可发现或
安装启用状态替代运行证据。需要在 Codex `/hooks` 中审查并信任 Oh My Paper 的定义；
本项目不绕过该机制。未启用时，AGENTS.md 仍要求连续执行，但不声称有自动收尾保护。

## 整链回放

`python3 scripts/eval-codex-pipeline.py` 是需要模型调用的手动验收，不属于离线 CI。
它创建隔离临时项目，用明确标记的虚构资料从初始化走到交付。驱动器仅回复
“全部评估”和“选择第一个方向”两次模拟作者决定，不发送用户流程提醒。

若模型提前收尾，驱动器调用真实 Stop 适配器，并通过 Codex resume 回放其继续指令；
这验证原生回调契约而不修改本机信任设置。出现其他意外停止或超出回放上限均为失败。
回放结果记录作者决定、自动续行次数、最终任务数和真实会话 ID。

这是软件流程验收，不将虚构资料变为真实研究证据，也不证明稿件达到真实刊物投稿要求。

当前整链、原生 Stop 自动续行和本机受信任状态见
[整链验收记录](codex-continuous-validation.md)。
