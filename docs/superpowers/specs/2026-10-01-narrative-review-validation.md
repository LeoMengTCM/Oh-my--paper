# 叙述性综述支持验收

日期：2026-10-01。对应设计：`2026-10-01-narrative-review-support-design.md`。

## 实施结果

- 新建项目可使用正式 `narrative-review`，默认 exploratory，不生成临床专用 protocol/SAP/deviations。
- 保留四种既有类型、旧任务格式和研究类型字段；正式叙述综述 track 不被旧兼容字段覆盖。
- 两个宿主的 setup、survey、ideate、plan、experiment、write、review 及五个角色引用同一 narrative-review profile。
- 规划、证据综合、写作与评审采用叙述综述语义；保存独立的稿件语言，不强制 RCT、训练、Meta 分析或 PRISMA。
- 缺少初始化文件时，Claude 研究入口明确要求先 setup；此入口行为仍需模型执行提示词，不能描述为不可绕过的程序强制限制。
- Codex 生成副本与技能目录已同步。未提交、推送或发布。

## 测试

1. `node --test tests/codex-workflow.test.mjs tests/codex-routing.test.mjs`：27/27 通过。
2. `npm run check`：退出码 0。
   - 技能目录同步检查通过，45 个技能。
   - Codex 9 个 workflow、5 个角色副本一致。
   - 插件一致性检查 11 类通过。
   - Node 测试：49 项，48 通过、1 跳过、0 失败。
   - Python 测试：116 项，105 通过、11 跳过、0 失败。
   - 合计 153 通过、12 跳过。R 语法检查实际运行；统计计算所需依赖未就绪，12 项统计相关检查跳过，其中 Node 明确报告缺少 metafor。本次未声称完整统计计算回归通过，也未安装额外统计依赖。
3. 增量补丁应用前已检查可应用性；`git diff --check` 通过。

完整检查输出位于实际研究工作区：`/Volumes/Leo/Projects/AIG-review/quality/software-check-narrative-init.log`。

## 真实项目初始化

研究者已确认 AIG、叙述性综述、英文写作。独立工作区为 `/Volumes/Leo/Projects/AIG-review`。

- 从实际初始化器创建 brief 与项目配置，保留此前已建立的研究决策和记忆文件。
- 刷新本项目 `.claude/skills`，再次 init 更新受管理角色及资源路径，研究者资料不重置。
- 实际 status 返回 `initialized: true`、`missing: []`、`resourcesAvailable: true`、`track: narrative-review`。
- 实际 workflow 返回 `researchDesign: narrative-review`、`workflow: plan`、`action: plan-tasks`；空任务表未被视为研究完成。
- 稿件语言保存为 `projectContext.writingLanguage = en`，沟通语言为 zh-CN。

## 验收边界

这次验收确认软件初始化、状态路由和配置一致性，不证明真实论文质量、引用语境或临床结论正确。截至初始化完成，尚未执行文献检索或写作。真实研究验收将在检索、原文核对、证据综合和稿件评审过程中继续进行；也未据本次检查声称新研究会话中的自动 hooks 已获信任并实际运行。
