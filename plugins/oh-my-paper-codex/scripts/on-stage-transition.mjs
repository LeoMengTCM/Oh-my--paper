/**
 * on-stage-transition.mjs
 * 检测阶段任务全部完成时提示推进
 * 手动触发：node scripts/on-stage-transition.mjs
 */
import fs from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { readTaskDocument } from "../skills/inno-pipeline-planner/scripts/task-contract.mjs";

const PROJECT = process.cwd();

async function main() {
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
      ? " 注意：systematic-review 推进前核对方案版本的研究者批准、真实注册状态与 PRISMA 记录（见 rct-pairwise-profile.md）；本脚本仅提醒，不执行研究审批。"
      : track === "clinical"
        ? " 注意：clinical 推进前须确认方案、适用注册与伦理批准及报告规范（见 omp 的 plan 工作流）。"
        : "";
  await fs.mkdir(path.dirname(statePath), { recursive: true });
  await fs.appendFile(
    statePath,
    `\n⚠️ [${ts}] 阶段 '${currentStage}' 所有任务已完成，请使用 omp 的 plan 工作流评审并决定是否推进。${gateNote}\n`,
    "utf8"
  );

  const eventsDir = path.join(PROJECT, ".pipeline", ".hook-events");
  await fs.mkdir(eventsDir, { recursive: true });
  await fs.writeFile(
    path.join(eventsDir, `${Date.now()}.json`),
    JSON.stringify({ type: "stage-complete", stage: currentStage, timestamp: Date.now() }),
    "utf8"
  );

  console.log(`✅ Stage '${currentStage}' complete — transition prompt added.`);
}

main().catch((error) => {
  process.stderr.write(`阶段检查失败：${error.message}\n`);
  process.exitCode = 1;
});
