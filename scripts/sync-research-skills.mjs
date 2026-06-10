/**
 * sync-research-skills.mjs
 *
 * 以本仓库的 `skills/` 目录为权威源，反向生成研究技能的目录文件：
 *   - skills/research-catalog.json   （自动生成：每个 skill 一个 manifest）
 *   - skills/research-scope.json     （自动生成：所有 skill id 列表）
 *
 * `skills/research-stage-map.json` 是**人工策划**的数据（哪个阶段推荐哪些技能、
 * 按 taskType 分类），脚本只读取它来推断每个 skill 的 stages 并做引用校验，
 * 不会自动重写它。
 *
 * 此前的版本依赖原作者本地的外部 `dr-claw` 仓库（写死路径
 * /Users/donkfeng/Desktop/dr-claw）做单向同步，fork 维护者无法运行，导致
 * catalog 长期停留在 27 个、与实际 35 个 skill 脱节。现已改为只依赖本仓库。
 *
 * 用法：
 *   node scripts/sync-research-skills.mjs sync     # 生成并写入（默认）
 *   node scripts/sync-research-skills.mjs check     # 只校验不写，漂移则退出码 1（适合 CI）
 *   node scripts/sync-research-skills.mjs report     # 打印将生成的内容摘要与自检结果
 */
import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";

const VALID_STAGES = ["survey", "ideation", "experiment", "publication", "promotion"];

// 没有出现在 research-stage-map.json、且 frontmatter 也未声明合法 stage 时的兜底归属。
const STAGE_FALLBACKS = {
  "academic-researcher": ["survey", "publication"],
  "biorxiv-database": ["survey"],
  "bioinformatics-init-analysis": ["experiment"],
  "claude-code-dispatch": ["experiment"],
  "codex-dispatch": ["experiment"],
  "dataset-discovery": ["survey", "ideation", "experiment"],
  "gemini-deep-research": ["survey"],
  "inno-code-survey": ["ideation", "experiment"],
  "inno-deep-research": ["survey", "ideation", "experiment", "publication"],
  "inno-experiment-analysis": ["experiment"],
  "inno-experiment-dev": ["experiment"],
  "inno-figure-gen": ["publication"],
  "inno-grant-proposal": ["publication"],
  "inno-idea-eval": ["ideation"],
  "inno-idea-generation": ["ideation"],
  "inno-paper-reviewer": ["publication"],
  "inno-paper-writing": ["publication"],
  "inno-pipeline-planner": ["survey", "ideation", "experiment", "publication", "promotion"],
  "inno-prepare-resources": ["survey", "ideation"],
  "inno-rclone-to-overleaf": ["publication"],
  "inno-reference-audit": ["publication"],
  "literature-pdf-ocr-library": ["survey", "ideation"],
  "making-academic-presentations": ["promotion"],
  "ml-paper-writing": ["publication"],
  "paper-analyzer": ["survey", "publication"],
  "paper-finder": ["survey"],
  "paper-image-extractor": ["publication"],
  "remote-experiment": ["experiment"],
  "research-experiment-driver": ["experiment"],
  "research-idea-convergence": ["ideation"],
  "research-literature-trace": ["survey"],
  "research-news": ["survey"],
  "research-paper-handoff": ["publication"],
  "research-pipeline-planner": ["survey", "ideation", "experiment", "publication", "promotion"],
  "scientific-writing": ["publication"],
  "pubmed-search": ["survey", "ideation"],
  "clinicaltrials-gov": ["survey", "ideation"],
  "systematic-review": ["survey", "publication"],
  "clinical-study-design": ["ideation", "experiment"],
};

const DEFAULT_TOOLS = ["read_file", "search_project", "write_file"];

const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const skillsRoot = path.join(repoRoot, "skills");
const catalogPath = path.join(skillsRoot, "research-catalog.json");
const scopePath = path.join(skillsRoot, "research-scope.json");
const stageMapPath = path.join(skillsRoot, "research-stage-map.json");

function main() {
  const mode = parseMode(process.argv.slice(2));

  const stageMap = readJson(stageMapPath);
  const skillIds = discoverSkillIds();
  const manifests = skillIds.map((id) => buildManifest(id, stageMap));

  const catalog = {
    schema: "omp-research-catalog-v1",
    generatedAt: new Date().toISOString(),
    upstream: { repo: "Oh-my--paper", revision: getGitRevision() },
    skills: manifests,
    stageSkillMap: stageMap,
  };
  const scope = {
    schema: "omp-research-scope-v1",
    generatedAt: catalog.generatedAt,
    skills: skillIds,
  };

  const issues = lint(skillIds, stageMap);

  if (mode === "report") {
    process.stdout.write(formatReport(skillIds, issues));
    process.stdout.write(formatDrift(catalog, scope));
    process.exitCode = issues.errors.length ? 1 : 0;
    return;
  }

  if (mode === "check") {
    const drift = computeDrift(catalog, scope);
    process.stdout.write(formatReport(skillIds, issues));
    process.stdout.write(formatDrift(catalog, scope));
    if (issues.errors.length || drift.length) {
      process.stderr.write(
        `\nFAIL: ${issues.errors.length} error(s), ${drift.length} drifted file(s). ` +
          `Run \`npm run skills:research:sync\` to regenerate.\n`,
      );
      process.exitCode = 1;
      return;
    }
    process.stdout.write("\nResearch skills are in sync.\n");
    return;
  }

  // sync
  writeJson(catalogPath, catalog);
  writeJson(scopePath, scope);

  process.stdout.write(formatReport(skillIds, issues));
  process.stdout.write(
    `\nWrote ${manifests.length} skills to ${rel(catalogPath)} and ${rel(scopePath)}.\n`,
  );
  if (issues.errors.length) {
    process.stderr.write(`\nWARNING: ${issues.errors.length} error(s) — see above.\n`);
    process.exitCode = 1;
  }
}

function parseMode(args) {
  for (const arg of args) {
    if (arg === "sync" || arg === "check" || arg === "report") return arg;
    throw new Error(`Unknown argument: ${arg}`);
  }
  return "sync";
}

function discoverSkillIds() {
  const ids = [];
  for (const entry of readdirSync(skillsRoot)) {
    const dir = path.join(skillsRoot, entry);
    if (!statSync(dir).isDirectory()) continue;
    if (!existsSync(path.join(dir, "SKILL.md"))) continue;
    ids.push(entry);
  }
  return ids.sort();
}

function buildManifest(id, stageMap) {
  const dir = path.join(skillsRoot, id);
  const fm = parseFrontmatter(readFileSync(path.join(dir, "SKILL.md"), "utf8"));
  const resourceFlags = scanResourceFlags(dir);
  const stages = inferStages(id, stageMap, fm);
  const summary = textValue(fm.summary) || textValue(fm.description) || id;
  const description = firstSentence(textValue(fm.description) || summary);

  return {
    id,
    name: textValue(fm.name) || id,
    version: normalizeVersion(textValue(fm.version)),
    description,
    summary,
    stages,
    tools: listValue(fm.tools) || inferTools(resourceFlags),
    primaryIntent: textValue(fm.primaryIntent) || "research",
    intents: listValue(fm.intents) || [textValue(fm.primaryIntent) || "research"],
    capabilities: listValue(fm.capabilities) || inferCapabilities(stages),
    domains: listValue(fm.domains) || inferDomains(id),
    keywords: listValue(fm.keywords) || [id, ...stages],
    source: "builtin",
    status: textValue(fm.status) || "verified",
    resourceFlags,
  };
}

function inferStages(id, stageMap, fm) {
  // 1) research-stage-map.json 里被引用的阶段（人工策划，最权威）
  const fromMap = [];
  for (const [stage, config] of Object.entries(stageMap)) {
    const inBase = (config.base || []).includes(id);
    const inTasks = Object.values(config.byTaskType || {}).some((list) => list.includes(id));
    if (inBase || inTasks) fromMap.push(stage);
  }
  if (fromMap.length) return VALID_STAGES.filter((s) => fromMap.includes(s));

  // 2) frontmatter 声明的合法阶段
  const fromFm = (listValue(fm.stages) || []).filter((s) => VALID_STAGES.includes(s));
  if (fromFm.length) return VALID_STAGES.filter((s) => fromFm.includes(s));

  // 3) 兜底表，再不行归到 survey
  return STAGE_FALLBACKS[id] || ["survey"];
}

function inferTools(resourceFlags) {
  const tools = [...DEFAULT_TOOLS];
  if (resourceFlags.hasScripts) tools.push("run_terminal");
  return tools;
}

function inferCapabilities(stages) {
  if (stages.includes("publication")) return ["research-planning", "visualization-reporting"];
  if (stages.includes("experiment")) return ["research-planning", "data-processing"];
  return ["search-retrieval", "research-planning"];
}

function inferDomains(id) {
  if (/clinic|pubmed|trial|systematic-review|study-design|medic|epi|cochrane|prisma/.test(id)) {
    return ["clinical-medicine"];
  }
  return id.includes("bio") ? ["bioinformatics"] : ["cs-ai"];
}

function scanResourceFlags(dir) {
  const refs = countFiles(path.join(dir, "references"));
  const scripts = countFiles(path.join(dir, "scripts"));
  const templates = countFiles(path.join(dir, "templates"));
  const assets = countFiles(path.join(dir, "assets"));
  return {
    hasReferences: refs > 0,
    hasScripts: scripts > 0,
    hasTemplates: templates > 0,
    hasAssets: assets > 0,
    referenceCount: refs,
    scriptCount: scripts,
    templateCount: templates,
    assetCount: assets,
    optionalScripts: scripts > 0,
  };
}

function countFiles(dir) {
  if (!existsSync(dir) || !statSync(dir).isDirectory()) return 0;
  let count = 0;
  for (const entry of readdirSync(dir)) {
    if (entry === ".DS_Store" || entry === "__pycache__") continue;
    const full = path.join(dir, entry);
    const stats = statSync(full);
    if (stats.isDirectory()) {
      count += countFiles(full);
    } else if (!full.endsWith(".pyc")) {
      count += 1;
    }
  }
  return count;
}

// ---- 校验 / 自检 ----

function lint(skillIds, stageMap) {
  const errors = [];
  const warnings = [];
  const idSet = new Set(skillIds);

  for (const id of skillIds) {
    const fm = parseFrontmatter(readFileSync(path.join(skillsRoot, id, "SKILL.md"), "utf8"));
    if (!textValue(fm.name)) warnings.push(`${id}: SKILL.md frontmatter 缺少 name`);
    if (!textValue(fm.description)) errors.push(`${id}: SKILL.md frontmatter 缺少 description`);
  }

  // stage-map 不能引用不存在的 skill
  for (const [stage, config] of Object.entries(stageMap)) {
    const refs = [...(config.base || []), ...Object.values(config.byTaskType || {}).flat()];
    for (const ref of refs) {
      if (!idSet.has(ref)) errors.push(`research-stage-map.json: 阶段 ${stage} 引用了不存在的 skill "${ref}"`);
    }
  }

  // README 徽章数量与实际一致
  const commandCount = countCommands();
  for (const readme of ["README.md", "README.zh.md"]) {
    const p = path.join(repoRoot, readme);
    if (!existsSync(p)) continue;
    const text = readFileSync(p, "utf8");
    const skillBadge = Number(text.match(/badge\/skills-(\d+)/)?.[1]);
    const cmdBadge = Number(text.match(/badge\/commands-(\d+)/)?.[1]);
    if (skillBadge && skillBadge !== skillIds.length) {
      errors.push(`${readme}: skills 徽章为 ${skillBadge}，实际 ${skillIds.length}`);
    }
    if (cmdBadge && commandCount && cmdBadge !== commandCount) {
      errors.push(`${readme}: commands 徽章为 ${cmdBadge}，实际 ${commandCount}`);
    }
  }

  return { errors, warnings };
}

function countCommands() {
  const dir = path.join(repoRoot, "plugins", "oh-my-paper", "commands");
  if (!existsSync(dir)) return 0;
  return readdirSync(dir).filter((f) => f.endsWith(".md")).length;
}

// 比较"实质内容"是否与磁盘一致，忽略 generatedAt / upstream.revision 等易变元数据
function computeDrift(catalog, scope) {
  const drift = [];
  if (!sameContent(catalogPath, canonicalCatalog(catalog))) drift.push(rel(catalogPath));
  if (!sameContent(scopePath, canonicalScope(scope))) drift.push(rel(scopePath));
  return drift;
}

function canonicalCatalog(catalog) {
  return { schema: catalog.schema, skills: catalog.skills, stageSkillMap: catalog.stageSkillMap };
}

function canonicalScope(scope) {
  return { schema: scope.schema, skills: scope.skills };
}

function sameContent(filePath, canonicalExpected) {
  if (!existsSync(filePath)) return false;
  let actual;
  try {
    actual = JSON.parse(readFileSync(filePath, "utf8"));
  } catch {
    return false;
  }
  const canonicalActual =
    "stageSkillMap" in canonicalExpected
      ? canonicalCatalog(actual)
      : canonicalScope(actual);
  return JSON.stringify(canonicalActual) === JSON.stringify(canonicalExpected);
}

// ---- 输出 ----

function formatReport(skillIds, issues) {
  const lines = [`Discovered ${skillIds.length} skills under ${rel(skillsRoot)}.`];
  for (const w of issues.warnings) lines.push(`  warn: ${w}`);
  for (const e of issues.errors) lines.push(`  ERROR: ${e}`);
  return lines.join("\n") + "\n";
}

function formatDrift(catalog, scope) {
  const drift = computeDrift(catalog, scope);
  if (!drift.length) return "On-disk catalog/scope match generated content.\n";
  return "Drifted (need regenerate): " + drift.join(", ") + "\n";
}

// ---- frontmatter 解析（最小 YAML 子集，仓库未安装 YAML 库）----

function parseFrontmatter(content) {
  const norm = content.replace(/\r\n/g, "\n");
  if (!norm.startsWith("---\n")) return {};
  const end = norm.indexOf("\n---", 3);
  if (end === -1) return {};
  return parseYamlBlock(norm.slice(4, end));
}

function parseYamlBlock(block) {
  const lines = block.split("\n");
  const result = {};
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim() || line.trimStart().startsWith("#") || line.startsWith(" ") || line.startsWith("\t")) {
      i += 1;
      continue;
    }
    const m = line.match(/^([A-Za-z0-9_]+):(.*)$/);
    if (!m) {
      i += 1;
      continue;
    }
    const key = m[1];
    const rest = m[2].trim();

    if (rest === "|" || rest === "|-" || rest === ">" || rest === ">-") {
      const buf = [];
      i += 1;
      while (i < lines.length && (lines[i].startsWith("  ") || !lines[i].trim())) {
        buf.push(lines[i].replace(/^ {2}/, ""));
        i += 1;
      }
      result[key] = buf.join("\n").trim();
      continue;
    }

    if (rest === "") {
      const items = [];
      let nested = false;
      i += 1;
      while (i < lines.length && (lines[i].startsWith("  ") || lines[i].startsWith("\t") || !lines[i].trim())) {
        const t = lines[i].trim();
        if (!t) {
          i += 1;
          continue;
        }
        if (t.startsWith("- ")) items.push(stripQuotes(t.slice(2).trim()));
        else nested = true; // 嵌套 map（如 upstream/resourceFlags）— 忽略，由脚本重算
        i += 1;
      }
      result[key] = items.length ? items : nested ? {} : "";
      continue;
    }

    if (rest.startsWith("[") && rest.endsWith("]")) {
      result[key] = rest
        .slice(1, -1)
        .split(",")
        .map((s) => stripQuotes(s.trim()))
        .filter((s) => s.length > 0);
      i += 1;
      continue;
    }

    result[key] = stripQuotes(rest);
    i += 1;
  }
  return result;
}

function stripQuotes(s) {
  const t = String(s).trim();
  if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) {
    return t.slice(1, -1);
  }
  return t;
}

function textValue(v) {
  if (typeof v === "string") return v.trim();
  return "";
}

function listValue(v) {
  if (Array.isArray(v) && v.length) return v;
  return null;
}

function normalizeVersion(v) {
  if (!v) return "1.0.0";
  const m = String(v).trim().match(/^(\d+)(?:\.(\d+))?(?:\.(\d+))?$/);
  if (!m) return String(v).trim();
  return `${m[1]}.${m[2] || 0}.${m[3] || 0}`;
}

function firstSentence(input) {
  const normalized = String(input || "").replace(/\s+/g, " ").trim();
  if (!normalized) return "";
  const match = normalized.match(/^(.+?[.!?。！？])(\s|$)/);
  return match ? match[1] : normalized;
}

// ---- 通用工具 ----

function readJson(filePath) {
  return JSON.parse(readFileSync(filePath, "utf8"));
}

function writeJson(filePath, value) {
  mkdirSync(path.dirname(filePath), { recursive: true });
  writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

function getGitRevision() {
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], { cwd: repoRoot, encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
}

function rel(filePath) {
  return path.relative(repoRoot, filePath).replaceAll(path.sep, "/");
}

main();
