#!/usr/bin/env node
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, realpathSync, renameSync, statSync, writeFileSync, openSync, closeSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const CONFIG = ".pipeline/execution.json";
const INTENTS = new Set(["plan", "survey", "ideate", "experiment", "write", "review", "delegate", "promotion"]);

function saveJson(file, value) {
  const temp = `${file}.${randomUUID()}.tmp`;
  writeFileSync(temp, JSON.stringify(value, null, 2) + "\n", { mode: 0o600 });
  renameSync(temp, file);
}

export function readExecution(project) {
  const file = path.resolve(project, CONFIG);
  if (!existsSync(file)) return { status: "unconfigured", executor: null, onFailure: "stop" };
  const config = JSON.parse(readFileSync(file, "utf8"));
  if (config.version !== 1 || !["claude", "codex"].includes(config.executor) || config.onFailure !== "stop") {
    throw new Error(`${CONFIG} 无效：需要 version=1、executor=claude|codex、onFailure=stop`);
  }
  return { ...config, status: "configured" };
}

export function configureExecution(project, executor, { replace = false } = {}) {
  if (!["claude", "codex"].includes(executor)) throw new Error("executor 必须是 claude 或 codex");
  const current = readExecution(project);
  if (current.status === "configured") {
    if (current.executor === executor) return current;
    if (!replace) throw new Error("已有执行器选择；用户明确同意后才可用 --replace 更改");
  }
  mkdirSync(path.resolve(project, ".pipeline"), { recursive: true });
  const { status, ...retained } = current;
  saveJson(path.resolve(project, CONFIG), { ...retained, version: 1, executor, onFailure: "stop" });
  return readExecution(project);
}

function projectFile(project, relative) {
  if (typeof relative !== "string" || !relative.trim() || path.isAbsolute(relative)) {
    throw new Error("任务文件必须使用项目内相对路径");
  }
  const file = path.resolve(project, relative);
  const inside = (candidate) => candidate === project || candidate.startsWith(project + path.sep);
  if (!inside(file) || file === project) throw new Error(`路径超出项目范围：${relative}`);
  let ancestor = file;
  while (!existsSync(ancestor)) ancestor = path.dirname(ancestor);
  if (!inside(realpathSync(ancestor))) throw new Error(`符号链接超出项目范围：${relative}`);
  return file;
}

function readArtifact(project, relative) {
  const file = projectFile(project, relative);
  if (!existsSync(file)) return null;
  if (!statSync(file).isFile()) throw new Error(`产物不是普通文件：${relative}`);
  return readFileSync(file);
}

export async function dispatch(project, request, { onStatus = () => {} } = {}) {
  project = realpathSync(project);
  if (process.env.OMP_CODEX_DISPATCH === "1") throw new Error("Codex 子任务不能递归派发；请执行当前任务并返回结果");
  const config = readExecution(project);
  if (config.status !== "configured") throw new Error("尚未选择执行器；先通过 setup 确认并保存选择");
  if (config.executor !== "codex") throw new Error("当前执行器是宿主 Agent（claude）；不会擅自启动 Codex");
  if (!request || request.version !== 1 || !INTENTS.has(request.intent)) throw new Error("任务需要 version=1 和有效 intent");
  if (!Array.isArray(request.artifacts) || request.artifacts.length === 0) throw new Error("必须声明至少一个期望产物");
  if (!Array.isArray(request.allowedPaths) || request.allowedPaths.length === 0) throw new Error("必须声明允许修改的路径 allowedPaths");
  for (const relative of request.allowedPaths) projectFile(project, relative);
  for (const relative of request.artifacts) {
    projectFile(project, relative);
    if (relative.startsWith(".pipeline/runs/") || relative === CONFIG) throw new Error("运行记录和执行器配置不能作为研究产物");
    if (!request.allowedPaths.some((allowed) => {
      const target = path.resolve(project, relative);
      const base = path.resolve(project, allowed);
      return target === base || target.startsWith(base + path.sep);
    })) throw new Error(`产物不在允许修改范围内：${relative}`);
  }
  if (request.sandbox !== undefined && !["read-only", "workspace-write"].includes(request.sandbox)) {
    throw new Error("sandbox 只允许 read-only 或 workspace-write；不支持绕过权限");
  }
  const task = readFileSync(projectFile(project, request.promptFile), "utf8").trim();
  if (!task) throw new Error("任务说明不能为空");
  const before = request.artifacts.map((file) => readArtifact(project, file));
  const runs = projectFile(project, ".pipeline/runs");
  mkdirSync(runs, { recursive: true });
  const runId = `${new Date().toISOString().replace(/[:.]/g, "-")}-${randomUUID().slice(0, 8)}`;
  const runDir = path.join(runs, runId);
  mkdirSync(runDir, { mode: 0o700 });
  const prompt = [
    "你是由宿主 Agent（Claude Code / Qoder）委派的 Codex 执行者，只执行下方已经授权的单个任务。",
    "不要递归派发、不要注册 OMP continuation、不要启动全项目循环或更改执行器配置。",
    "专业 skill 仍适用，但其中的用户选择和阶段推进由宿主主会话负责；缺少真实决定就报告阻塞。",
    "只修改 allowedPaths 内的文件；这是一项任务约束，不是额外的沙箱权限。",
    "不得绕过权限、上传未授权资料或执行未授权外部操作。凭据从既有环境获取，不写入报告。",
    "不得修改任务完成状态来冒充验收；最后说明实际改动、验证结果与未解决问题。",
    `工作目录：${project}`,
    `任务类型：${request.intent}`,
    `允许修改：${JSON.stringify(request.allowedPaths)}`,
    `期望本次生成或更新的产物：${JSON.stringify(request.artifacts)}`,
    "", task, "",
  ].join("\n");
  writeFileSync(path.join(runDir, "prompt.md"), prompt, { mode: 0o600 });
  saveJson(path.join(runDir, "request.json"), request);
  const args = ["exec", "--cd", project, "--skip-git-repo-check", "--json", "--output-last-message", path.join(runDir, "result.md")];
  if (request.sandbox) args.push("--sandbox", request.sandbox);
  args.push("-");
  let state = { version: 1, runId, executor: "codex", intent: request.intent, status: "starting", startedAt: new Date().toISOString(), runDir, command: ["codex", ...args], artifacts: request.artifacts };
  const update = (changes) => {
    state = { ...state, ...changes };
    saveJson(path.join(runDir, "status.json"), state);
    onStatus(state);
  };
  update({});
  const output = openSync(path.join(runDir, "events.jsonl"), "wx", 0o600);
  const errors = openSync(path.join(runDir, "stderr.log"), "wx", 0o600);
  let exit;
  try {
    exit = await new Promise((resolve) => {
      const child = spawn("codex", args, {
        cwd: project, shell: false, stdio: ["pipe", output, errors],
        env: { ...process.env, OMP_CODEX_DISPATCH: "1" },
      });
      let error;
      let interrupted = false;
      const interrupt = (signal) => { interrupted = true; child.kill(signal); };
      const sigint = () => interrupt("SIGINT");
      const sigterm = () => interrupt("SIGTERM");
      process.once("SIGINT", sigint);
      process.once("SIGTERM", sigterm);
      child.on("spawn", () => update({ status: "running", pid: child.pid }));
      child.on("error", (err) => { error = err.message; });
      child.stdin.on("error", (err) => { if (err.code !== "EPIPE") error = err.message; });
      child.on("close", (code, signal) => {
        process.removeListener("SIGINT", sigint);
        process.removeListener("SIGTERM", sigterm);
        resolve({ code, signal, error, interrupted });
      });
      child.stdin.end(prompt);
    });
  } finally {
    closeSync(output);
    closeSync(errors);
  }
  let failure = exit.error;
  let artifactChecks = [];
  if (!failure && (exit.code !== 0 || exit.interrupted)) failure = `Codex 未成功退出：code=${exit.code}, signal=${exit.signal}`;
  if (!failure) {
    try {
      const events = readFileSync(path.join(runDir, "events.jsonl"), "utf8").split("\n").filter(Boolean).map((line) => JSON.parse(line));
      if (events.some((event) => event.type === "turn.failed") || !events.some((event) => event.type === "turn.completed")) {
        throw new Error("Codex 没有有效的 turn.completed 事件或报告了 turn.failed");
      }
      if (!readFileSync(path.join(runDir, "result.md"), "utf8").trim()) throw new Error("Codex 最终回复为空");
      artifactChecks = request.artifacts.map((file, index) => {
        const after = readArtifact(project, file);
        return { path: file, valid: Boolean(after?.length && (!before[index] || !after.equals(before[index]))) };
      });
      const invalid = artifactChecks.filter((item) => !item.valid);
      if (invalid.length) throw new Error(`产物缺失、为空或未更新：${invalid.map((item) => item.path).join(", ")}`);
    } catch (error) { failure = error.message; }
  }
  update({
    status: failure ? "failed" : "ready_for_review", finishedAt: new Date().toISOString(),
    exitCode: exit.code, signal: exit.signal, artifactChecks, ...(failure ? { error: failure } : {}),
  });
  return state;
}

async function main(argv) {
  const [command, ...rest] = argv;
  const options = {};
  for (let i = 0; i < rest.length; i++) {
    const key = rest[i];
    if (key === "--replace") { options.replace = true; continue; }
    if (!["--project", "--executor", "--request"].includes(key) || !rest[i + 1] || rest[i + 1].startsWith("--")) {
      throw new Error(`未知参数或缺少参数值：${key}`);
    }
    options[key.slice(2)] = rest[++i];
  }
  const project = path.resolve(options.project || ".");
  const print = (value) => process.stdout.write(JSON.stringify(value) + "\n");
  if (command === "status") { print(readExecution(project)); return; }
  if (command === "configure") { print(configureExecution(project, options.executor, options)); return; }
  if (command === "run") {
    if (!options.request) throw new Error("run 需要 --request <项目内任务JSON>");
    const request = JSON.parse(readFileSync(projectFile(realpathSync(project), options.request), "utf8"));
    const result = await dispatch(project, request, { onStatus: print });
    if (result.status !== "ready_for_review") process.exitCode = 1;
    return;
  }
  throw new Error("用法：executor.mjs status|configure|run --project <目录> [--executor claude|codex] [--replace] [--request <文件>]");
}

if (process.argv[1] && existsSync(process.argv[1]) && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(JSON.stringify({ status: "blocked", error: error.message, fallback: false }) + "\n");
    process.exitCode = 1;
  });
}
