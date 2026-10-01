import assert from "node:assert/strict";
import { cpSync, existsSync, mkdtempSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const plugins = ["oh-my-paper", "oh-my-paper-codex"];

function runStageHook(t, plugin, tasks) {
  const project = mkdtempSync(path.join(os.tmpdir(), "omp-task-test-"));
  t.after(() => rmSync(project, { recursive: true, force: true }));
  for (const dir of ["tasks", "docs"]) mkdirSync(path.join(project, ".pipeline", dir), { recursive: true });
  const tasksPath = path.join(project, ".pipeline/tasks/tasks.json");
  const original = JSON.stringify(tasks);
  writeFileSync(tasksPath, original);
  writeFileSync(path.join(project, ".pipeline/docs/research_brief.json"), JSON.stringify({ currentStage: "survey" }));
  const result = spawnSync(process.execPath, [path.join(root, "plugins", plugin, "scripts/on-stage-transition.mjs")], {
    cwd: project,
    input: JSON.stringify({ tool_input: { file_path: tasksPath } }),
    encoding: "utf8",
  });
  assert.equal(readFileSync(tasksPath, "utf8"), original, "读取任务不能迁移或覆盖原文件");
  return { project, result };
}

for (const plugin of plugins) {
  test(`${plugin}：现有顶层任务仅在当前阶段全部完成后提醒`, (t) => {
    for (const status of ["pending", "done"]) {
      const { project, result } = runStageHook(t, plugin, {
        tasks: [
          { id: "task-1", stage: "survey", status },
          { id: 2, stage: "experiment", status: "pending" },
        ],
      });
      assert.equal(result.status, 0, result.stderr);
      assert.equal(existsSync(path.join(project, ".pipeline/.hook-events")), status === "done");
    }
  });

  test(`${plugin}：独立插件包无需仓库根目录即可加载共享任务解析器`, (t) => {
    const bundle = mkdtempSync(path.join(os.tmpdir(), "omp-bundle-test-"));
    t.after(() => rmSync(bundle, { recursive: true, force: true }));
    const scriptDir = path.join(bundle, "scripts");
    const helperDir = path.join(bundle, "skills/inno-pipeline-planner/scripts");
    mkdirSync(scriptDir, { recursive: true });
    mkdirSync(helperDir, { recursive: true });
    cpSync(path.join(root, "plugins", plugin, "scripts/on-stage-transition.mjs"), path.join(scriptDir, "on-stage-transition.mjs"));
    cpSync(path.join(root, "plugins", plugin, "skills/inno-pipeline-planner/scripts/task-contract.mjs"), path.join(helperDir, "task-contract.mjs"), { dereference: true });
    const { project } = runStageHook(t, plugin, { tasks: [] });
    const result = spawnSync(process.execPath, [path.join(scriptDir, "on-stage-transition.mjs")], {
      cwd: project, encoding: "utf8",
      input: JSON.stringify({ tool_input: { file_path: ".pipeline/tasks/tasks.json" } }),
    });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stderr, "");
  });

  test(`${plugin}：新旧任务列表冲突时报告错误且不推进`, (t) => {
    const { project, result } = runStageHook(t, plugin, {
      tasks: [{ id: "existing-id", stage: "survey", status: "done" }],
      master: { tasks: [{ id: "existing-id", stage: "survey", status: "pending" }] },
    });
    assert.equal(result.status, 1);
    assert.match(result.stderr, /tasks.*master.tasks.*冲突/);
    assert.equal(existsSync(path.join(project, ".pipeline/.hook-events")), false);
    assert.equal(existsSync(path.join(project, ".pipeline/memory/orchestrator_state.md")), false);
  });

  test(`${plugin}：旧 master.tasks 的完成阶段仍产生提醒`, (t) => {
    const { project, result } = runStageHook(t, plugin, {
      master: { tasks: [{ id: 1, stage: "survey", status: "done", dependsOn: [] }] },
    });
    assert.equal(result.status, 0, result.stderr);
    const events = readdirSync(path.join(project, ".pipeline/.hook-events"));
    assert.equal(events.length, 1);
    const event = JSON.parse(readFileSync(path.join(project, ".pipeline/.hook-events", events[0]), "utf8"));
    assert.equal(event.type, "stage-complete");
    assert.equal(event.stage, "survey");
  });
}
