import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const cli = path.join(root, "skills/inno-pipeline-planner/scripts/task-contract.mjs");

function run(t, document, executable = cli) {
  const dir = mkdtempSync(path.join(os.tmpdir(), "omp-contract-test-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const file = path.join(dir, "tasks.json");
  const original = JSON.stringify(document);
  writeFileSync(file, original);
  const result = spawnSync(process.execPath, [executable, file], { encoding: "utf8" });
  assert.equal(readFileSync(file, "utf8"), original);
  return result;
}

test("CLI 兼容旧依赖，保留 ID 类型、任务状态及文档元数据", (t) => {
  const result = run(t, {
    version: 3, custom: "保留", master: { label: "原项目", tasks: [
      { id: 1, status: "done", dependsOn: [] },
      { id: "task-old", status: "pending", dependsOn: [1] },
    ] },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), {
    version: 3, custom: "保留", master: { label: "原项目" }, tasks: [
      { id: 1, status: "done", dependencies: [] },
      { id: "task-old", status: "pending", dependencies: [1] },
    ],
  });
});

test("CLI 可通过插件 skills 符号链接调用，不会静默输出空内容", (t) => {
  for (const plugin of ["oh-my-paper", "oh-my-paper-codex"]) {
    const executable = path.join(root, "plugins", plugin, "skills/inno-pipeline-planner/scripts/task-contract.mjs");
    const result = run(t, { master: { tasks: [] } }, executable);
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(JSON.parse(result.stdout), { tasks: [] });
  }
});

test("CLI 接受规范化后相同的双格式文档", (t) => {
  const result = run(t, {
    tasks: [{ id: 1, dependencies: [] }],
    master: { tasks: [{ id: 1, dependsOn: [] }] },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), { tasks: [{ id: 1, dependencies: [] }] });
});

test("CLI 拒绝缺失或损坏的任务数据，不能当作空任务成功", (t) => {
  for (const document of [
    {}, null, { tasks: null }, { tasks: {} }, { tasks: [null] },
    { tasks: [{}] }, { tasks: [{ id: 1 }, { id: 1 }] },
    { tasks: [{ id: 1, dependencies: null }] },
    { tasks: [{ id: 1, dependsOn: "task-old" }] },
    { tasks: [{ id: 1, dependencies: [{}] }] },
    { tasks: [], master: { tasks: null } },
  ]) {
    const result = run(t, document);
    assert.equal(result.status, 1, JSON.stringify(document));
    assert.match(result.stderr, /任务格式错误/);
    assert.equal(result.stdout, "");
  }
});

test("CLI 拒绝冲突的依赖字段，不输出可误用的任务列表", (t) => {
  const result = run(t, { tasks: [{ id: 1, dependencies: [], dependsOn: [2] }] });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /dependencies.*dependsOn.*冲突/);
  assert.equal(result.stdout, "");
});
