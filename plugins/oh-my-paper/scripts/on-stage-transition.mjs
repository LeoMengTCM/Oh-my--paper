/**
 * on-stage-transition.mjs
 * PostToolUse(Write|Edit) hook — 检测阶段任务全部完成时提示推进
 * 兼容内置 Write/Edit 与 filesystem MCP 的 write_file/edit_file（file_path 或 path 字段）
 */
import fs from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { readTaskDocument } from "../skills/inno-pipeline-planner/scripts/task-contract.mjs";

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

  const tasks = readTaskDocument(tasksPath);

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
    track === "systematic-review"
      ? " 注意：systematic-review 推进前核对方案版本的研究者批准、真实注册状态与 PRISMA 记录（见 rct-pairwise-profile.md）；本 hook 仅提醒，不执行研究审批。"
      : track === "clinical"
        ? " 注意：clinical 推进前须确认方案、适用注册与伦理批准及报告规范（见 /omp:plan）。"
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

main().catch((error) => {
  process.stderr.write(`阶段检查失败：${error.message}\n`);
  process.exitCode = 1;
});
