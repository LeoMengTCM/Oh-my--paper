import { existsSync, readFileSync, realpathSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isId(value) {
  return (typeof value === "string" && value.trim().length > 0) || Number.isSafeInteger(value);
}

function normalizeTasks(tasks) {
  if (!Array.isArray(tasks)) throw new Error("tasks 必须为数组");
  const ids = new Set();
  return tasks.map((value) => {
    if (!isObject(value) || !isId(value.id)) throw new Error("任务必须有非空字符串或整数 id");
    if (ids.has(value.id)) throw new Error(`重复任务 id：${value.id}`);
    ids.add(value.id);
    const { dependsOn, ...task } = value;
    for (const key of ["dependencies", "dependsOn"]) {
      if (Object.hasOwn(value, key) && (!Array.isArray(value[key]) || !value[key].every(isId))) {
        throw new Error(`任务 ${task.id} 的 ${key} 必须是 ID 数组`);
      }
    }
    if (task.dependencies && dependsOn && !isDeepStrictEqual(task.dependencies, dependsOn)) {
      throw new Error(`任务 ${task.id} 的 dependencies 与 dependsOn 冲突`);
    }
    return { ...task, dependencies: task.dependencies ?? dependsOn ?? [] };
  });
}

export function normalizeTaskDocument(document) {
  if (!isObject(document)) throw new Error("任务文档必须为对象");
  if (Object.hasOwn(document, "master") && !isObject(document.master)) {
    throw new Error("master 必须为对象");
  }
  const current = Object.hasOwn(document, "tasks") ? normalizeTasks(document.tasks) : undefined;
  const legacy = document.master && Object.hasOwn(document.master, "tasks")
    ? normalizeTasks(document.master.tasks) : undefined;
  if (!current && !legacy) throw new Error("缺少 tasks 或 master.tasks");
  if (current && legacy && !isDeepStrictEqual(current, legacy)) {
    throw new Error("tasks 与 master.tasks 冲突，请人工确认后再更新");
  }
  const result = { ...document, tasks: current ?? legacy };
  if (result.master) {
    const { tasks: legacyTasks, ...metadata } = result.master;
    if (Object.keys(metadata).length) result.master = metadata;
    else delete result.master;
  }
  return result;
}

export function readTaskDocument(filePath) {
  return normalizeTaskDocument(JSON.parse(readFileSync(filePath, "utf8")));
}

if (process.argv[1] && existsSync(process.argv[1]) && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    if (process.argv.length !== 3) throw new Error("用法：node task-contract.mjs <tasks.json>");
    process.stdout.write(`${JSON.stringify(readTaskDocument(process.argv[2]), null, 2)}\n`);
  } catch (error) {
    process.stderr.write(`任务格式错误：${error.message}\n`);
    process.exitCode = 1;
  }
}
