# 叙述性综述首次初始化与双宿主支持

日期：2026-10-01。

## 背景与批准

AIG 真实研究项目由研究者明确选择为英文叙述性综述。首次执行 setup 时发现只有四种 track，现有 Codex 通过旧 ml 值加 articleType 兼容，Claude 的部分流程没有等价分支。研究者已明确批准“补齐支持并继续”。

## 范围

1. 增加正式 `pipeline.track = narrative-review`，默认 `analysisMode = exploratory`。
2. 保留现有四类及旧 researchType/articleType 的兼容，不自动迁移已有项目。
3. 新增共享 narrative-review profile，双宿主命令与角色引用同一规则。
4. survey 为可追溯检索，ideation 为确定综述重点，experiment 为原文证据提取、核对与综合，publication 为英文或研究者指定语言的写作、引用核验、评审和返修。
5. 不自动创建临床 protocol/SAP，不强制 RCT 注册、伦理批准、训练/消融、Meta 分析、PRISMA 或每阶段一图；资料类型或研究方法改变时重新核实要求。
6. 研究入口缺项目文件时先初始化，不凭聊天上下文假定已建立研究项目。
7. setup 收集方法类型时遵守每题最多四个选项，已知主题、阶段和语言不重复询问。

## 非目标

不重构任务引擎，不改变既有 RCT 系统综述规范，不增加桌面界面，不把任何软件测试当作真实研究验收，不提交或推送代码。

## 验证

- 初始化：新 track 可用、默认 exploratory、无不适用临床文件。
- 重复初始化：保留已有任务 ID、内容及用户自定义文件。
- 路由：正式 track 与旧兼容字段均能识别，任务按既定 survey、证据整合和 publication 继续。
- 文本约束：两个宿主的初始化、规划、写作和评审都能找到共享 profile，并优先处理叙述综述。
- 回归：运行已有 check，包括技能/副本一致性和测试；真实 R 及外部服务未执行时须明确说明。
- 项目实例：刷新 AIG 技能副本后，创建正确 brief，通过任务校验和项目状态检查，进入 plan。

## 实施分工

- runtime：project.mjs、workflow.mjs 及相应行为测试。
- 宿主：Claude/Codex 命令和角色，Codex 生成副本统一同步。
- 共享规则：brief-schema、track-profiles、generation-rules、研究阶段包装技能及必要文档。

## 方法学边界

脚本检查可以验证配置、任务依赖和文件状态；正文是否完整、文献是否真正支持临床结论仍需要原文检查和研究者判断。提示词约束不得被描述为程序强制保证。
