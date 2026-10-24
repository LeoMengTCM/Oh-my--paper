import assert from "node:assert/strict";
import { cpSync, existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { configureExecution, readExecution } from "../skills/codex-dispatch/scripts/executor.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const runner = path.join(root, "skills/codex-dispatch/scripts/executor.mjs");
const hook = path.join(root, "plugins/oh-my-paper/scripts/on-session-start.mjs");

function fixture(t) {
  const project = mkdtempSync(path.join(os.tmpdir(), "omp-executor 空格-"));
  t.after(() => rmSync(project, { recursive: true, force: true }));
  mkdirSync(path.join(project, ".pipeline/docs"), { recursive: true });
  mkdirSync(path.join(project, "bin"));
  writeFileSync(path.join(project, "bin/codex"), `#!${process.execPath}
const fs = require('node:fs');
const args = process.argv.slice(2);
const input = fs.readFileSync(0, 'utf8');
fs.writeFileSync('called.json', JSON.stringify({args, input, worker: process.env.OMP_CODEX_DISPATCH}));
if (process.env.FAKE_MODE === 'fail') { console.error('not authenticated'); process.exit(7); }
const result = args[args.indexOf('--output-last-message') + 1];
if (process.env.FAKE_MODE !== 'no-result') fs.writeFileSync(result, process.env.FAKE_MODE === 'empty-result' ? '' : '已完成任务，待验收');
if (!['missing', 'stale'].includes(process.env.FAKE_MODE)) fs.writeFileSync('output.md', '本次实际产物');
console.log(JSON.stringify({type: process.env.FAKE_MODE === 'turn-failed' ? 'turn.failed' : 'turn.completed'}));
`, { mode: 0o755 });
  writeFileSync(path.join(project, ".pipeline/task.md"), "只执行已确认的任务。$(touch SHOULD_NOT_EXIST) ' \" 中文");
  writeFileSync(path.join(project, ".pipeline/tasks.json"), '{"tasks":[{"id":1,"status":"pending"}]}');
  const request = { version: 1, intent: "survey", promptFile: ".pipeline/task.md", allowedPaths: ["output.md"], artifacts: ["output.md"] };
  writeFileSync(path.join(project, ".pipeline/request.json"), JSON.stringify(request));
  const env = { ...process.env, PATH: `${path.join(project, "bin")}${path.delimiter}${process.env.PATH}`, OMP_CODEX_DISPATCH: "" };
  const run = (args = [], extra = {}, script = runner) => spawnSync(process.execPath, [script, ...args, "--project", project], { encoding: "utf8", env: { ...env, ...extra } });
  return { project, request, run };
}

function lastStatus(result) {
  return JSON.parse(result.stdout.trim().split("\n").at(-1));
}

test("执行器选择跨进程保留，重复配置不重置，切换需要明确标志", (t) => {
  const { project, run } = fixture(t);
  assert.equal(readExecution(project).status, "unconfigured");
  assert.equal(run(["configure", "--executor", "codex"]).status, 0);
  const file = path.join(project, ".pipeline/execution.json");
  const original = readFileSync(file, "utf8");
  assert.equal(run(["configure", "--executor", "codex"]).status, 0);
  assert.equal(readFileSync(file, "utf8"), original);
  assert.equal(lastStatus(run(["status"])).executor, "codex");
  assert.equal(run(["configure", "--executor", "claude"]).status, 1);
  assert.equal(readFileSync(file, "utf8"), original);
  assert.equal(run(["configure", "--executor", "claude", "--replace"]).status, 0);
  assert.equal(readExecution(project).executor, "claude");
});

for (const mode of ["missing-config", "claude", "invalid-config", "recursive"]) {
  test(`${mode} 不启动 Codex，不悄悄执行任务`, (t) => {
    const { project, run } = fixture(t);
    if (mode === "claude") configureExecution(project, "claude");
    if (mode === "recursive") configureExecution(project, "codex");
    if (mode === "invalid-config") writeFileSync(path.join(project, ".pipeline/execution.json"), '{"executor":"codex"}');
    const result = run(["run", "--request", ".pipeline/request.json"], mode === "recursive" ? { OMP_CODEX_DISPATCH: "1" } : {});
    assert.equal(result.status, 1);
    assert.equal(existsSync(path.join(project, "called.json")), false);
    assert.equal(existsSync(path.join(project, "output.md")), false);
    assert.match(result.stderr, /"fallback":false/);
  });
}

for (const intent of ["plan", "survey", "ideate", "experiment", "write", "review", "delegate", "promotion"]) {
  test(`${intent} 确实启动 Codex 并通过 stdin 传任务`, (t) => {
    const { project, request, run } = fixture(t);
    configureExecution(project, "codex");
    writeFileSync(path.join(project, ".pipeline/request.json"), JSON.stringify({ ...request, intent }));
    const result = run(["run", "--request", ".pipeline/request.json"]);
    assert.equal(result.status, 0, result.stderr);
    const states = result.stdout.trim().split("\n").map(JSON.parse);
    assert.deepEqual(states.map((item) => item.status), ["starting", "running", "ready_for_review"]);
    const status = states.at(-1);
    assert.equal(status.exitCode, 0);
    assert.ok(status.pid > 0);
    assert.equal(JSON.parse(readFileSync(path.join(status.runDir, "status.json"))).status, "ready_for_review");
    const called = JSON.parse(readFileSync(path.join(project, "called.json")));
    assert.equal(called.args[0], "exec");
    assert.equal(called.args.at(-1), "-");
    assert.ok(called.args.includes("--json"));
    assert.ok(called.args.includes("--skip-git-repo-check"));
    assert.ok(!called.args.includes("--sandbox"), "默认继承配置，不自动提高权限");
    assert.ok(!called.args.includes("--model"));
    assert.match(called.input, /\$\(touch SHOULD_NOT_EXIST\)/);
    assert.match(called.input, /不要注册 OMP continuation/);
    assert.equal(called.worker, "1");
    assert.equal(existsSync(path.join(project, "SHOULD_NOT_EXIST")), false);
    assert.equal(JSON.parse(readFileSync(path.join(project, ".pipeline/tasks.json"))).tasks[0].status, "pending");
  });
}

for (const mode of ["fail", "missing", "stale", "no-result", "empty-result", "turn-failed"]) {
  test(`${mode} 不标记成功，不转交 Claude，保留运行记录`, (t) => {
    const { project, run } = fixture(t);
    configureExecution(project, "codex");
    if (mode === "stale") writeFileSync(path.join(project, "output.md"), "旧产物");
    const result = run(["run", "--request", ".pipeline/request.json"], { FAKE_MODE: mode });
    assert.equal(result.status, 1, result.stderr);
    const state = lastStatus(result);
    assert.equal(state.status, "failed");
    assert.ok(state.error);
    assert.ok(existsSync(path.join(state.runDir, "stderr.log")));
    assert.equal(readExecution(project).executor, "codex");
    if (mode === "fail") {
      assert.equal(state.exitCode, 7);
      assert.match(readFileSync(path.join(state.runDir, "stderr.log"), "utf8"), /not authenticated/);
    }
  });
}

test("CLI 缺失时记录启动失败", (t) => {
  const { project, run } = fixture(t);
  configureExecution(project, "codex");
  const result = run(["run", "--request", ".pipeline/request.json"], { PATH: "" });
  assert.equal(result.status, 1);
  assert.equal(lastStatus(result).status, "failed");
  assert.match(lastStatus(result).error, /ENOENT/);
});

test("独立安装 skill 能派发，不依赖仓库根", (t) => {
  const { project, run } = fixture(t);
  const bundle = path.join(project, "bundle/codex-dispatch");
  cpSync(path.join(root, "skills/codex-dispatch"), bundle, { recursive: true, dereference: true });
  configureExecution(project, "codex");
  const result = run(["run", "--request", ".pipeline/request.json"], {}, path.join(bundle, "scripts/executor.mjs"));
  assert.equal(result.status, 0, result.stderr);
});

test("通过 stdin 模块导入不会误执行或因 argv 为短横线而崩溃", () => {
  const result = spawnSync(process.execPath, ["--input-type=module", "-"], {
    input: `await import(${JSON.stringify(runner)}); console.log('imported');`, encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), "imported");
});

test("通过插件 skills 软链接也确实执行 CLI 入口", (t) => {
  const { project, run } = fixture(t);
  const linked = path.join(root, "plugins/oh-my-paper/skills/codex-dispatch/scripts/executor.mjs");
  assert.equal(lastStatus(run(["status"], {}, linked)).status, "unconfigured");
  assert.equal(lastStatus(run(["configure", "--executor", "codex"], {}, linked)).executor, "codex");
  const result = run(["run", "--request", ".pipeline/request.json"], {}, linked);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(lastStatus(result).status, "ready_for_review");
  assert.ok(existsSync(path.join(project, "called.json")));
});

test("新会话即使缓存新鲜也重新输出执行器选择", (t) => {
  const { project } = fixture(t);
  configureExecution(project, "codex");
  const runHook = () => spawnSync(process.execPath, [hook], { cwd: project, encoding: "utf8" });
  assert.match(runHook().stdout, /执行器.*codex/);
  assert.match(runHook().stdout, /执行器.*codex/);
  configureExecution(project, "claude", { replace: true });
  assert.match(runHook().stdout, /执行器.*claude/);
  writeFileSync(path.join(project, ".pipeline/execution.json"), "invalid");
  assert.match(runHook().stdout, /执行器配置.*无效|执行器配置.*无法读取/);
});

test("Claude 各阶段和角色在专业分支前加载统一执行器规则", () => {
  for (const [dir, names] of [
    ["commands", ["plan", "survey", "ideate", "experiment", "write", "review", "delegate", "sync"]],
    ["agents", ["conductor", "literature-scout", "experiment-driver", "paper-writer", "reviewer"]],
  ]) {
    for (const name of names) {
      const content = readFileSync(path.join(root, "plugins/oh-my-paper", dir, `${name}.md`), "utf8");
      assert.match(content, /codex-dispatch\/references\/execution-routing\.md/, `${dir}/${name}`);
      assert.doesNotMatch(content, /Codex 不可用就自己执行|codex --background|CODEX_DONE/);
      const branch = content.indexOf("## 叙述性综述");
      if (branch >= 0) assert.ok(content.indexOf("execution-routing.md") < branch);
    }
  }
});
