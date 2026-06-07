/**
 * on-stage-transition.mjs
 * PostToolUse(Write) hook — 检测阶段任务全部完成时提示推进
 */
import fs from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const PROJECT = process.cwd();

async function main() {
  // PostToolUse hook 的数据通过 stdin 的 JSON 传入（不存在 CLAUDE_TOOL_INPUT 环境变量）
  const stdin = await readStdin();
  let toolInput = {};
  try { toolInput = JSON.parse(stdin).tool_input || {}; } catch { return; }
  const filePath = toolInput.file_path || toolInput.path || "";
  if (!filePath.includes("tasks.json")) return;

  const tasksPath = path.join(PROJECT, ".pipeline", "tasks", "tasks.json");
  if (!existsSync(tasksPath)) return;

  let tasks;
  try { tasks = JSON.parse(readFileSync(tasksPath, "utf8")); } catch { return; }

  const briefPath = path.join(PROJECT, ".pipeline", "docs", "research_brief.json");
  let currentStage = "unknown";
  let track = "ml";
  if (existsSync(briefPath)) {
    try {
      const brief = JSON.parse(readFileSync(briefPath, "utf8"));
      currentStage = brief.currentStage || "unknown";
      track = (brief.pipeline && brief.pipeline.track) || brief.track || "ml";
    } catch {}
  }

  const stageTasks = (tasks.tasks || []).filter(t => t.stage === currentStage);
  if (!stageTasks.length) return;
  if (stageTasks.filter(t => t.status === "done").length !== stageTasks.length) return;

  const statePath = path.join(PROJECT, ".pipeline", "memory", "orchestrator_state.md");
  const ts = new Date().toISOString().slice(0, 16).replace("T", " ");
  const gateNote =
    track === "clinical" || track === "systematic-review"
      ? ` 注意：本项目为 ${track} track——推进前须确认注册/锁定/伦理门与报告规范清单（见 /omp:plan 的闸门检查）。`
      : "";
  await fs.mkdir(path.dirname(statePath), { recursive: true });
  await fs.appendFile(
    statePath,
    `\n⚠️ [${ts}] 阶段 '${currentStage}' 所有任务已完成，请运行 /omp:plan 评审并决定是否推进。${gateNote}\n`,
    "utf8"
  );

  const eventsDir = path.join(PROJECT, ".pipeline", ".hook-events");
  await fs.mkdir(eventsDir, { recursive: true });
  await fs.writeFile(
    path.join(eventsDir, `${Date.now()}.json`),
    JSON.stringify({ type: "stage-complete", stage: currentStage, timestamp: Date.now() }),
    "utf8"
  );
}

async function readStdin() {
  if (process.stdin.isTTY) return "";
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

main().catch(() => process.exit(0));
