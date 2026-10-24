#!/usr/bin/env node
/**
 * sync-kimi-skills.mjs
 *
 * Kimi Code 的插件安全模型要求 manifest 声明的路径在符号链接解析后仍位于
 * 插件根目录内，且 `/plugins install` 会把插件目录整体拷贝到
 * $KIMI_CODE_HOME/plugins/managed/<id>/——因此 kimi 变体不能像 claude/codex
 * 变体那样用 skills 符号链接，必须持有实体副本。
 *
 * 本脚本以仓库根 `skills/` 为权威源，生成/校验
 * `plugins/oh-my-paper-kimi/skills/` 实体副本。该副本是构建产物，已在
 * .gitignore 排除；发布到 GitHub 供 `/plugins install <url>` 使用前需先运行
 * sync 并提交。
 *
 * 用法：
 *   node scripts/sync-kimi-skills.mjs sync     # 生成/刷新副本（默认）
 *   node scripts/sync-kimi-skills.mjs check    # 只校验不写入，漂移则退出码 1（适合 CI）
 */
import { cpSync, existsSync, readdirSync, readFileSync, rmSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const mode = process.argv[2] ?? "sync";
if (!["sync", "check"].includes(mode)) throw new Error("Usage: sync-kimi-skills.mjs <sync|check>");

const source = path.join(root, "skills");
const target = path.join(root, "plugins/oh-my-paper-kimi/skills");

function walk(dir, base = dir) {
  const files = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const abs = path.join(dir, entry.name);
    if (entry.isDirectory()) files.push(...walk(abs, base));
    else if (entry.isFile()) files.push(path.relative(base, abs));
  }
  return files.sort();
}

if (mode === "sync") {
  rmSync(target, { recursive: true, force: true });
  cpSync(source, target, { recursive: true });
  console.log(`Kimi skills 副本已生成：${path.relative(root, target)}`);
} else {
  const problems = [];
  if (!existsSync(target)) {
    console.log(`Kimi skills 副本不存在（${path.relative(root, target)}），运行 node scripts/sync-kimi-skills.mjs sync 生成；本次跳过校验。`);
    process.exit(0);
  }
  const srcFiles = walk(source);
  const dstFiles = walk(target);
  const srcSet = new Set(srcFiles);
  const dstSet = new Set(dstFiles);
  for (const f of srcFiles) if (!dstSet.has(f)) problems.push(`缺失: ${f}`);
  for (const f of dstFiles) if (!srcSet.has(f)) problems.push(`多余: ${f}`);
  for (const f of srcFiles) {
    if (!dstSet.has(f)) continue;
    const a = readFileSync(path.join(source, f));
    const b = readFileSync(path.join(target, f));
    if (a.length !== b.length || !a.equals(b)) problems.push(`内容不同: ${f}`);
  }
  if (problems.length) {
    console.error(`Kimi skills 副本与 skills/ 漂移，运行 node scripts/sync-kimi-skills.mjs sync：\n${problems.slice(0, 20).join("\n")}${problems.length > 20 ? `\n... 共 ${problems.length} 项` : ""}`);
    process.exit(1);
  }
  console.log(`Kimi skills 副本与 skills/ 一致（${srcFiles.length} 个文件）。`);
}
