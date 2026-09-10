#!/usr/bin/env node
/**
 * check-plugin-consistency.mjs
 *
 * 仓库一致性自检（CI 与本地均可跑）：
 *   1. 版本号一致：package.json、两个 plugin.json、marketplace.json（两处）
 *   2. 所有被 git 跟踪的 .json 文件可解析
 *   3. 所有被 git 跟踪的 .mjs 脚本通过 node --check 语法检查
 *   4. commands/agents/prompts 的 frontmatter 必备字段齐全
 *   5. hooks.json 引用的脚本文件真实存在
 *   6. 两个插件目录下的 skills 符号链接可解析
 *   7. claude 版（commands+agents）与 codex 版（prompts+agents）关键概念平价：
 *      改动一侧的核心机制时必须同步另一侧，此检查防止静默漂移
 *   8. 双插件结构对应：commands/<x>.md ↔ prompts/omp-<x>.md，agents/<x>.md ↔ agents/<x>.toml
 *   9. README 徽章数字（skills/commands/agents）与仓库实际数量一致
 *
 * 用法：node scripts/check-plugin-consistency.mjs
 * 退出码：0 = 全部通过；1 = 有失败项
 */
import { execFileSync } from "node:child_process";
import { existsSync, lstatSync, readdirSync, readFileSync, realpathSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const failures = [];
let checks = 0;

function fail(message) {
  failures.push(message);
}

function readJson(rel) {
  return JSON.parse(readFileSync(path.join(repoRoot, rel), "utf8"));
}

function trackedFiles(pattern) {
  const out = execFileSync("git", ["ls-files", pattern], { cwd: repoRoot, encoding: "utf8" });
  return out.split("\n").filter(Boolean);
}

// ---------- 1. 版本号一致 ----------
{
  checks++;
  const sources = [
    ["package.json", () => readJson("package.json").version],
    ["plugins/oh-my-paper/.claude-plugin/plugin.json", () => readJson("plugins/oh-my-paper/.claude-plugin/plugin.json").version],
    ["plugins/oh-my-paper-codex/.codex-plugin/plugin.json", () => readJson("plugins/oh-my-paper-codex/.codex-plugin/plugin.json").version],
    [".claude-plugin/marketplace.json (metadata)", () => readJson(".claude-plugin/marketplace.json").metadata?.version],
    [".claude-plugin/marketplace.json (plugins[0])", () => readJson(".claude-plugin/marketplace.json").plugins?.[0]?.version],
  ];
  const versions = new Map();
  for (const [label, get] of sources) {
    let v;
    try { v = get(); } catch (e) { fail(`版本检查：读取 ${label} 失败 — ${e.message}`); continue; }
    if (!v) { fail(`版本检查：${label} 缺少 version 字段`); continue; }
    versions.set(label, v);
  }
  const unique = [...new Set(versions.values())];
  if (unique.length > 1) {
    const detail = [...versions].map(([l, v]) => `  ${v}  ${l}`).join("\n");
    fail(`版本号不一致（应全部相同）：\n${detail}`);
  }
}

// ---------- 2. 跟踪的 JSON 全部可解析 ----------
{
  checks++;
  for (const rel of trackedFiles("*.json")) {
    try { readJson(rel); } catch (e) { fail(`JSON 解析失败：${rel} — ${e.message}`); }
  }
}

// ---------- 3. 跟踪的 .mjs 语法检查 ----------
{
  checks++;
  for (const rel of trackedFiles("*.mjs")) {
    try {
      execFileSync(process.execPath, ["--check", rel], { cwd: repoRoot, stdio: "pipe" });
    } catch (e) {
      fail(`语法检查失败：${rel}\n${e.stderr?.toString().trim() ?? e.message}`);
    }
  }
}

// ---------- 4. frontmatter 必备字段 ----------
function parseFrontmatter(rel) {
  const text = readFileSync(path.join(repoRoot, rel), "utf8");
  if (!text.startsWith("---\n")) return null;
  const end = text.indexOf("\n---", 4);
  if (end === -1) return null;
  const fields = {};
  for (const line of text.slice(4, end).split("\n")) {
    const m = line.match(/^([A-Za-z_-]+):\s*(.*)$/);
    if (m) fields[m[1]] = m[2].trim();
  }
  return fields;
}

function checkFrontmatter(globPattern, requiredKeys) {
  for (const rel of trackedFiles(globPattern)) {
    const fm = parseFrontmatter(rel);
    if (!fm) { fail(`frontmatter 缺失或格式错误：${rel}`); continue; }
    for (const key of requiredKeys) {
      if (!fm[key]) fail(`frontmatter 缺少 ${key}：${rel}`);
    }
  }
}
{
  checks++;
  checkFrontmatter("plugins/oh-my-paper/commands/*.md", ["name", "description"]);
  checkFrontmatter("plugins/oh-my-paper/agents/*.md", ["name", "description"]);
  checkFrontmatter("plugins/oh-my-paper-codex/prompts/*.md", ["description"]);
}

// ---------- 5. hooks.json 引用的脚本存在 ----------
{
  checks++;
  const hooksRel = "plugins/oh-my-paper/hooks/hooks.json";
  try {
    const config = readJson(hooksRel);
    const commands = [];
    for (const entries of Object.values(config.hooks ?? {})) {
      for (const entry of entries) {
        for (const hook of entry.hooks ?? []) {
          if (hook.command) commands.push(hook.command);
        }
      }
    }
    if (!commands.length) fail(`${hooksRel} 未注册任何 hook 命令，检查是否被误改`);
    for (const command of commands) {
      const m = command.match(/\$\{CLAUDE_PLUGIN_ROOT\}\/([^"']+)/);
      if (!m) continue;
      const target = path.join(repoRoot, "plugins/oh-my-paper", m[1]);
      if (!existsSync(target)) fail(`${hooksRel} 引用的脚本不存在：${m[1]}`);
    }
  } catch (e) {
    fail(`读取 ${hooksRel} 失败 — ${e.message}`);
  }
}

// ---------- 6. skills 符号链接可解析 ----------
{
  checks++;
  for (const rel of ["plugins/oh-my-paper/skills", "plugins/oh-my-paper-codex/skills"]) {
    const abs = path.join(repoRoot, rel);
    try {
      if (!lstatSync(abs).isSymbolicLink()) { fail(`${rel} 应为符号链接`); continue; }
      realpathSync(abs);
    } catch {
      fail(`符号链接失效：${rel}`);
    }
  }
}

// ---------- 7. 双插件关键概念平价 ----------
// 这些是研究管线的核心机制标识。若在一侧新增/移除了某个机制，
// 必须同步另一侧后把这里的清单一并更新。
const PARITY_KEYWORDS = [
  "figure_ledger",
  "experiment_ledger",
  "result_summary.md",
  "review_log.md",
  "orchestrator_state.md",
  "research_brief.json",
  "tasks.json",
  "literature_bank",
  "project_truth",
  "execution_context",
];
function corpusOf(patterns) {
  let text = "";
  for (const pattern of patterns) {
    for (const rel of trackedFiles(pattern)) {
      text += readFileSync(path.join(repoRoot, rel), "utf8");
    }
  }
  return text;
}
{
  checks++;
  const claudeCorpus = corpusOf(["plugins/oh-my-paper/commands/*.md", "plugins/oh-my-paper/agents/*.md"]);
  const codexCorpus = corpusOf(["plugins/oh-my-paper-codex/prompts/*.md", "plugins/oh-my-paper-codex/agents/*.toml"]);
  for (const kw of PARITY_KEYWORDS) {
    const inClaude = claudeCorpus.includes(kw);
    const inCodex = codexCorpus.includes(kw);
    if (inClaude !== inCodex) {
      fail(`双插件漂移：关键概念 "${kw}" 只出现在 ${inClaude ? "claude 版（commands/agents）" : "codex 版（prompts/agents）"}，另一侧缺失`);
    }
    if (!inClaude && !inCodex) {
      fail(`平价清单过期：关键概念 "${kw}" 两侧都不存在，请更新 PARITY_KEYWORDS`);
    }
  }
}

// ---------- 8. 双插件结构对应 ----------
{
  checks++;
  const commands = trackedFiles("plugins/oh-my-paper/commands/*.md").map((f) => path.basename(f, ".md"));
  const prompts = trackedFiles("plugins/oh-my-paper-codex/prompts/*.md").map((f) => path.basename(f, ".md"));
  for (const cmd of commands) {
    if (!prompts.includes(`omp-${cmd}`)) fail(`command "${cmd}" 缺少对应的 codex prompt（prompts/omp-${cmd}.md）`);
  }
  for (const prompt of prompts) {
    const cmd = prompt.replace(/^omp-/, "");
    if (!commands.includes(cmd)) fail(`codex prompt "${prompt}" 缺少对应的 command（commands/${cmd}.md）`);
  }

  const mdAgents = trackedFiles("plugins/oh-my-paper/agents/*.md").map((f) => path.basename(f, ".md"));
  const tomlAgents = trackedFiles("plugins/oh-my-paper-codex/agents/*.toml").map((f) => path.basename(f, ".toml"));
  for (const a of mdAgents) {
    if (!tomlAgents.includes(a)) fail(`agent "${a}" 缺少 codex 版（agents/${a}.toml）`);
  }
  for (const a of tomlAgents) {
    if (!mdAgents.includes(a)) fail(`codex agent "${a}" 缺少 claude 版（agents/${a}.md）`);
  }
}

// ---------- 9. README 徽章数字与实际一致 ----------
{
  checks++;
  // 与 sync-research-skills.mjs 口径一致：只数含 SKILL.md 的目录。
  // `skills/_shared/` 是被多个 skill 引用的共享参考，不是 skill。
  const skillCount = readdirSync(path.join(repoRoot, "skills"), { withFileTypes: true })
    .filter((d) => d.isDirectory() && existsSync(path.join(repoRoot, "skills", d.name, "SKILL.md")))
    .length;
  const commandCount = trackedFiles("plugins/oh-my-paper/commands/*.md").length;
  const agentCount = trackedFiles("plugins/oh-my-paper/agents/*.md").length;
  const actual = { skills: skillCount, commands: commandCount, agents: agentCount };
  for (const readme of ["README.md", "README.zh.md"]) {
    const text = readFileSync(path.join(repoRoot, readme), "utf8");
    for (const [kind, count] of Object.entries(actual)) {
      const m = text.match(new RegExp(`badge/${kind}-(\\d+)`));
      if (!m) { fail(`${readme} 缺少 ${kind} 徽章`); continue; }
      if (Number(m[1]) !== count) {
        fail(`${readme} 徽章数字过期：${kind} 写的是 ${m[1]}，实际是 ${count}`);
      }
    }
  }
}

// ---------- 汇总 ----------
if (failures.length) {
  process.stderr.write(`\n一致性检查未通过（${failures.length} 项）：\n\n`);
  for (const f of failures) process.stderr.write(`✗ ${f}\n\n`);
  process.exit(1);
}
process.stdout.write(`一致性检查全部通过（${checks} 类检查）。\n`);
