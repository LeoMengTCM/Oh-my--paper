/**
 * on-session-start.mjs
 * SessionStart hook — 注入当前任务上下文到 .pipeline/.session-context.md
 */
import fs from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { readExecution } from "../skills/codex-dispatch/scripts/executor.mjs";

const PROJECT = process.env.QODER_PROJECT_DIR || process.env.CLAUDE_PROJECT_DIR || process.cwd();
const SESSION_CONTEXT = path.join(PROJECT, ".pipeline", ".session-context.md");
async function main() {
  // 每次新会话都读取配置；旧上下文不能代替当前执行器选择。

  // 检查是否是研究项目
  const pipelineDir = path.join(PROJECT, ".pipeline");
  if (!existsSync(pipelineDir)) return;

  const lines = ["# Session Context (Auto-generated)", ""];

  try {
    const execution = readExecution(PROJECT);
    if (execution.status === "unconfigured") {
      lines.push("**执行器**: 未配置。执行研究任务前确认一次并保存到 .pipeline/execution.json；不得默认使用当前 Agent。");
    } else {
      lines.push(`**执行器**: ${execution.executor}；失败策略: stop。每次派发前重新读取 .pipeline/execution.json。`);
      if (execution.executor === "codex") lines.push("主 Agent 负责沟通和验收，研究任务必须通过 codex-dispatch/scripts/executor.mjs 实际启动 Codex；不得改用宿主原生子代理或失败后代做。");
    }
  } catch (error) {
    lines.push(`**执行器配置无法读取或无效**: ${error.message}。先处理配置，暂停研究执行，不默认回退。`);
  }
  lines.push("先读取当前插件实际 skills 目录的 codex-dispatch/references/execution-routing.md。", "");

  const briefPath = path.join(pipelineDir, "docs", "research_brief.json");
  if (existsSync(briefPath)) {
    try {
      const brief = JSON.parse(readFileSync(briefPath, "utf8"));
      lines.push(`**当前阶段**: ${brief.currentStage || "unknown"}`);
      lines.push(`**研究主题**: ${brief.topic || ""}`);
      lines.push("");
    } catch {}
  }

  const contextPath = path.join(pipelineDir, "memory", "execution_context.md");
  if (existsSync(contextPath)) {
    const content = readFileSync(contextPath, "utf8").trim();
    if (content) {
      lines.push("## 当前任务");
      lines.push(content.split("\n").slice(0, 30).join("\n"));
      lines.push("");
    }
  }

  const handoffPath = path.join(pipelineDir, "memory", "agent_handoff.md");
  if (existsSync(handoffPath)) {
    const content = readFileSync(handoffPath, "utf8");
    const matches = [...content.matchAll(/^## Handoff:.+$/gm)];
    if (matches.length > 0) {
      const last = content.slice(matches[matches.length - 1].index).trim();
      lines.push("## 上一步交接");
      lines.push(last.split("\n").slice(0, 10).join("\n"));
      lines.push("");
    }
  }

  lines.push(`_生成时间: ${new Date().toISOString()}_`);
  lines.push("");
  lines.push("## 启动指令");
  lines.push("");
  lines.push("检测到 Oh My Paper 研究项目。请立即用 `AskUserQuestion` 询问用户今天的工作模式，选项如下：");
  lines.push("");
  lines.push("- `统筹规划` — 以 Conductor 身份：查看全局进展，决定下一步，评审产出");
  lines.push("- `文献调研` — 以 Literature Scout 身份：搜索论文，整理 literature_bank");
  lines.push("- `实验执行` — 以 Experiment Driver 身份：设计/实现/运行实验，追踪结果");
  lines.push("- `论文写作` — 以 Paper Writer 身份：撰写章节，生成图表，审查引用");
  lines.push("- `论文评审` — 以 Reviewer 身份：同行评审，输出 review_log");
  lines.push("- `直接告诉我要做什么` — 跳过角色选择");
  lines.push("");
  lines.push("用户选择后，读取对应角色的记忆文件，以该角色身份开始工作。");
  lines.push("");
  lines.push("构造 AskUserQuestion 调用时，务必带齐 question、header、options、multiSelect 字段，每个 option 含 label 与 description，且全部用纯文本加半角标点、不放 emoji 或特殊符号——否则会报 Invalid tool parameters。");

  const output = lines.join("\n");

  // 输出到 stdout 供宿主 SessionStart hook 读取（Claude Code / Qoder）
  process.stdout.write(output + "\n");

  // 同时写文件备用
  await fs.mkdir(path.dirname(SESSION_CONTEXT), { recursive: true });
  await fs.writeFile(SESSION_CONTEXT, output, "utf8");
}

main().catch(() => process.exit(0));
