/**
 * on-session-start.mjs
 * Codex 版本 — 生成 .pipeline/.session-context.md 供 AGENTS.md 引用
 * 可通过 `node scripts/on-session-start.mjs` 手动触发
 */
import fs from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const PROJECT = process.cwd();
const SESSION_CONTEXT = path.join(PROJECT, ".pipeline", ".session-context.md");

async function main() {
  // 检查是否是研究项目
  const pipelineDir = path.join(PROJECT, ".pipeline");
  if (!existsSync(pipelineDir)) return;

  const lines = ["# Session Context (Auto-generated)", ""];
  lines.push("Read AGENTS.md and the installed omp skill for the requested workflow. Resume the user's current task without a role-selection prompt.", "");
  lines.push("Before selecting a workflow, run the omp skill's scripts/workflow.mjs --project . --intent continue (choose-topic for broad topic selection). Check prerequisites and evidence; finish survey before recommending topics. After verified work, execute the next authorized task without another workflow reminder; preserve the user's final topic/protocol decisions.", "");

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

  const output = lines.join("\n");

  // 输出到 stdout
  process.stdout.write(output + "\n");

  // 同时写文件备用
  await fs.mkdir(path.dirname(SESSION_CONTEXT), { recursive: true });
  await fs.writeFile(SESSION_CONTEXT, output, "utf8");
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; });
