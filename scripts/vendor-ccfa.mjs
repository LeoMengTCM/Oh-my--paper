#!/usr/bin/env node
/**
 * vendor-ccfa.mjs
 *
 * 把 CCFA-Skills（https://github.com/mikubaka88/CCFA-Skills，MIT）中 OMP 缺失或明显
 * 更强的部分一次性并入本仓库的 `skills/`。这是 **vendoring**，不是子模块：并入后按
 * OMP 的 frontmatter 规范改写，之后的维护以本仓库为准；来源 commit 记录在每个
 * SKILL.md 的 `upstream` 字段里，将来要跟上游 diff 时以此为基准。
 *
 * 吸收 7 个 skill（去掉 `ccf-` 前缀——该前缀指中国计算机学会分级，对本仓库的
 * clinical / bioinformatics track 是误导），并替换 OMP 中 5 个更弱的同类 skill。
 * CCFA 的家族内务模块（common / pipeline-orchestrator / project-scaffolder /
 * skill-forger）与检索、选题、实验设计、绘图类 skill 不吸收——OMP 这几块更强。
 * 但 ccf-common/references/ 被吸收方引用约 90 次，故取其内容落到 `skills/_shared/`。
 *
 * 用法：
 *   node scripts/vendor-ccfa.mjs --src /path/to/CCFA-Skills [--dry-run]
 *
 * 幂等：重复执行会覆盖目标目录。
 */
import { execFileSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillsRoot = path.join(repoRoot, "skills");

// ---------- 参数 ----------
const argv = process.argv.slice(2);
const dryRun = argv.includes("--dry-run");
const srcIdx = argv.indexOf("--src");
if (srcIdx === -1 || !argv[srcIdx + 1]) {
  console.error("用法: node scripts/vendor-ccfa.mjs --src /path/to/CCFA-Skills [--dry-run]");
  process.exit(2);
}
const src = path.resolve(argv[srcIdx + 1]);
if (!existsSync(path.join(src, "ccf-common"))) {
  console.error(`--src 不像是 CCFA-Skills 仓库（缺 ccf-common/）：${src}`);
  process.exit(2);
}

const upstreamRevision = (() => {
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], { cwd: src, encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
})();

// ---------- 吸收清单 ----------
// stages/intents 等按 OMP 的 research-catalog schema 人工归类；paper 相关全部落在
// publication 阶段。keywords 保留中文触发词，OMP 用户多为中文提问。
const SKILLS = [
  {
    from: "ccf-paper-writer",
    to: "paper-writing",
    // 不取代 scientific-writing：那个是通用科学写作 + 临床/综述报告规范（IMRaD、
    // CONSORT/PRISMA/STROBE/STARD，domains: general），与本 skill 的 CS 顶会导向不重叠。
    replaces: ["ml-paper-writing", "inno-paper-writing"],
    stages: ["publication"],
    primaryIntent: "writing",
    intents: ["writing", "research"],
    capabilities: ["research-planning", "visualization-reporting"],
    keywords: ["paper writing", "manuscript", "draft", "rewrite", "polish", "compress",
      "abstract", "introduction", "related work", "method", "latex", "venue", "cvpr",
      "neurips", "icml", "iclr", "acl", "论文写作", "润色", "改写", "压缩"],
    descriptionSuffix:
      "For clinical, epidemiological, or systematic-review manuscripts that must follow " +
      "IMRaD and reporting guidelines (CONSORT/PRISMA/STROBE/STARD), use scientific-writing instead.",
  },
  {
    from: "ccf-paper-reviewer",
    to: "paper-reviewer",
    // 不取代 inno-paper-reviewer：那个覆盖临床试验与 grant 评审的报告规范合规
    // （CONSORT/STROBE），本 skill 面向 CS 顶会的科学评审与版本比较。
    replaces: [],
    stages: ["publication"],
    primaryIntent: "review",
    intents: ["review", "research"],
    capabilities: ["research-planning"],
    keywords: ["peer review", "scientific review", "scoring", "rebuttal readiness",
      "version comparison", "desk check", "评审", "审稿", "打分", "版本对比"],
    descriptionSuffix:
      "Clinical-trial or grant review requiring reporting-standards compliance " +
      "(CONSORT/STROBE) belongs to inno-paper-reviewer.",
  },
  {
    from: "ccf-integrity-auditor",
    to: "integrity-auditor",
    replaces: ["inno-reference-audit"],
    stages: ["publication"],
    primaryIntent: "review",
    intents: ["review"],
    capabilities: ["research-planning"],
    keywords: ["integrity", "claim check", "citation audit", "number consistency",
      "terminology", "figure check", "一致性核验", "引用核查"],
  },
  {
    from: "ccf-humanization",
    to: "paper-humanization",
    replaces: [],
    stages: ["publication"],
    primaryIntent: "writing",
    intents: ["writing"],
    capabilities: ["research-planning"],
    keywords: ["humanization", "academic prose", "defensive writing", "ai tells",
      "去除 ai 味", "自然表达", "学术语言"],
  },
  {
    from: "ccf-rebuttal-writer",
    to: "rebuttal-writer",
    replaces: [],
    stages: ["publication"],
    primaryIntent: "writing",
    intents: ["writing", "review"],
    capabilities: ["research-planning"],
    keywords: ["rebuttal", "response letter", "reviewer response", "revision note",
      "审稿回复", "答辩"],
  },
  {
    from: "ccf-submission-checker",
    to: "submission-checker",
    replaces: [],
    stages: ["publication"],
    primaryIntent: "review",
    intents: ["review", "delivery"],
    capabilities: ["research-planning"],
    keywords: ["submission", "camera ready", "anonymity", "page limit", "template check",
      "supplementary", "投稿检查", "匿名", "页数"],
  },
  {
    from: "ccf-paper-to-exemplar",
    to: "paper-to-exemplar",
    replaces: [],
    stages: ["publication"],
    primaryIntent: "writing",
    intents: ["writing", "research"],
    capabilities: ["search-retrieval", "research-planning"],
    keywords: ["exemplar", "reference paper", "writing pattern", "narrative structure",
      "范文", "写作范式"],
  },
];

// ccf-common/references/ 中被吸收方实际引用的部分 → skills/_shared/
// 丢弃 routing.md、skill-trigger-registry.yaml（CCFA 家族路由，OMP 用 research-stage-map
// + conductor agent）与 ccfa-yaml-contract.md（与 OMP 的 .pipeline/ 状态冲突）。
const SHARED_FILES = [
  "artifact-contracts.md",
  "ccf-a-venue-map.md",
  "handoff-modes.md",
  "privacy-and-evidence.md",
  "review-output-standards.md",
  "source-registry.yaml",
  "task-modes.md",
];

// ---------- 文本重写规则（按顺序执行）----------
// 1) 路径引用：../ccf-common/references/X → ../_shared/X，其余 ../ccf-<x>/ → ../<新名>/
// 2) 裸名称：指向未吸收 skill 的提名，重定向到 OMP 的对应能力
const REWRITES = [
  [/\.\.\/ccf-common\/references\//g, "../_shared/"],
  [/`?ccf-common\/references\//g, "`_shared/"],
  ...SKILLS.map(({ from, to }) => [new RegExp(`\\.\\./${from}/`, "g"), `../${to}/`]),
  // 未吸收的 CCFA skill → OMP 对应能力
  [/`ccf-visual-composer`/g, "`inno-figure-gen`"],
  [/`ccf-literature-searcher`/g, "`inno-deep-research`"],
  [/`ccf-literature-monitor`/g, "`research-news`"],
  [/`ccf-experiment-designer`/g, "`inno-experiment-dev`"],
  [/`ccf-idea-optimizer`/g, "`inno-idea-generation`"],
  [/`ccf-idea-reviewer`/g, "`inno-idea-eval`"],
  [/`ccf-pipeline-orchestrator`/g, "the conductor agent"],
  [/`ccf-project-scaffolder`/g, "`/omp:setup`"],
  [/`ccf-skill-forger`/g, "`npm run check`"],
  [/`ccf-latex-templates\//g, "`paper-writing/templates/"],
  [/ccf-latex-templates\//g, "paper-writing/templates/"],
  // 已吸收的 skill：裸名称也要改（放在路径规则之后，避免破坏路径）
  ...SKILLS.map(({ from, to }) => [new RegExp(`\`${from}\``, "g"), `\`${to}\``]),
  // 兜底：剩余未加反引号的提名
  ...SKILLS.map(({ from, to }) => [new RegExp(`\\b${from}\\b`, "g"), to]),
  [/\bccf-visual-composer\b/g, "inno-figure-gen"],
  [/\bccf-literature-searcher\b/g, "inno-deep-research"],
  [/\bccf-literature-monitor\b/g, "research-news"],
  [/\bccf-experiment-designer\b/g, "inno-experiment-dev"],
  [/\bccf-idea-optimizer\b/g, "inno-idea-generation"],
  [/\bccf-idea-reviewer\b/g, "inno-idea-eval"],
  [/\bccf-common\b/g, "_shared"],
  // 裸名残留：路由清单、示例文本、目录层说明
  [/\bccf-pipeline-orchestrator\b/g, "the conductor agent (`/omp:plan`)"],
  [/\bccf-project-scaffolder\b/g, "`/omp:setup`"],
  [/\bccf-skill-forger\b/g, "`npm run check`"],
  [/\bccf-expt-designer\b/g, "inno-experiment-dev"],
  [/`ccf-conference-skills\/<venue>\/SKILL\.md`/g, "per-venue runtime skills"],
  // CCFA v0.4.0 时期从 `ccf-conference-skills/` 迁移的注记：指向上游早已不存在的
  // 目录结构，对本仓库无意义，但后半句说明文件定位，保留改写。
  [
    /^> Migrated from the legacy `ccf-conference-skills\/[a-z0-9-]+\/SKILL\.md` runtime skill during v[\d.]+\. This file is now reference material for (.*?), not a standalone skill\.$/gm,
    "> Venue reference material for $1, not a standalone skill.",
  ],
  // source-registry.yaml 的 `used_by:` 列表里指向未吸收 skill 的条目
  [
    /used_by:\s*\[([^\]]*)\]/g,
    (_m, inner) => {
      const kept = inner
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s && !/^ccf-/.test(s));
      return `used_by: [${kept.join(", ")}]`;
    },
  ],
];

const TEXT_EXT = new Set([".md", ".yaml", ".yml", ".txt", ".py", ".json"]);

function rewriteText(text) {
  let out = text;
  for (const [pattern, replacement] of REWRITES) out = out.replace(pattern, replacement);
  return out;
}

function walk(dir, fn) {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, fn);
    else fn(full);
  }
}

function rewriteTree(root) {
  let touched = 0;
  walk(root, (file) => {
    if (!TEXT_EXT.has(path.extname(file))) return;
    const before = readFileSync(file, "utf8");
    const after = rewriteText(before);
    if (before !== after) {
      writeFileSync(file, after);
      touched += 1;
    }
  });
  return touched;
}

// ---------- frontmatter 转换 ----------
// CCFA 用 `metadata.ccf_skill_controls` 嵌套块；OMP 的 sync 脚本只认顶层键，且靠
// id/stages/intents/keywords 做阶段推荐。这里重建 frontmatter，正文原样保留。
function convertFrontmatter(skillPath, spec) {
  const file = path.join(skillPath, "SKILL.md");
  const raw = readFileSync(file, "utf8").replace(/\r\n/g, "\n");
  if (!raw.startsWith("---\n")) throw new Error(`${spec.to}: SKILL.md 缺少 frontmatter`);
  const end = raw.indexOf("\n---", 3);
  if (end === -1) throw new Error(`${spec.to}: frontmatter 未闭合`);
  const head = raw.slice(4, end);
  const body = raw.slice(end + 4).replace(/^\n+/, "\n");

  // 取出原 description（CCFA 写成 name: / description: "..." 单行双引号）
  const descMatch = head.match(/^description:\s*"([\s\S]*?)"\s*$/m);
  let description = (descMatch ? descMatch[1] : spec.to).replace(/\s+/g, " ").trim();
  // 上游以 "CCF paper" 指代 CS 顶会投稿；本仓库还服务临床/生信 track，改用学科中性说法
  description = description
    .replace(/\bCCF papers\b/g, "CS conference and journal papers")
    .replace(/\bCCF paper\b/g, "CS conference or journal paper")
    .replace(/\bCCF conference\b/g, "CS conference")
    .replace(/\bCCF\/AI\b/g, "CS\/AI")
    .replace(/\bCCF venue\b/g, "CS venue");
  if (spec.descriptionSuffix) description += " " + spec.descriptionSuffix;

  // 保留 CCFA 的 handoff 控制值（正文仍引用它），转成顶层扁平键以便被解析器读到
  const handoff = head.match(/handoff_question_mode:\s*(\S+)/)?.[1] ?? "partial";
  const privacy = head.match(/private_material_safety:\s*(\S+)/)?.[1] ?? "moderate";

  const yamlList = (items) => items.map((k) => `  - ${JSON.stringify(k)}`).join("\n");
  const fm = [
    "---",
    `id: ${spec.to}`,
    `name: ${spec.to}`,
    "version: 1.0.0",
    "description: |-",
    `  ${description}`,
    "stages:",
    yamlList(spec.stages),
    "primaryIntent: " + spec.primaryIntent,
    "intents:",
    yamlList(spec.intents),
    "capabilities:",
    yamlList(spec.capabilities),
    "domains:",
    yamlList(["cs-ai"]),
    "keywords:",
    yamlList([...new Set([spec.to, ...spec.keywords])]),
    "source: builtin",
    "status: verified",
    "handoffQuestionMode: " + handoff,
    "privateMaterialSafety: " + privacy,
    "upstream:",
    "  repo: mikubaka88/CCFA-Skills",
    `  path: ${spec.from}`,
    `  revision: ${upstreamRevision}`,
    "  license: MIT",
    "---",
  ].join("\n");

  writeFileSync(file, fm + body);
}

// ---------- 相对路径深度修正 ----------
// 上游把 `references/` 子目录里的跨 skill 引用也写成 `../<skill>/...`（相对 skill 根），
// 但按文件实际位置解析会少一级。这里把能在 skills/ 根下解析到的引用改写为真实相对路径。
function fixRelativeDepth(root) {
  let fixed = 0;
  walk(root, (file) => {
    if (!TEXT_EXT.has(path.extname(file))) return;
    const dir = path.dirname(file);
    const before = readFileSync(file, "utf8");
    const after = before.replace(
      // 锚定整段相对路径（含全部前导 `../`），否则多级 `../` 会被从中间匹配、叠加出错路径
      /(?<![.\/\w])((?:\.\.\/)+)([A-Za-z0-9_-]+\/[A-Za-z0-9/_.-]*\.(?:md|py|yaml|yml))/g,
      (match, _ups, rest) => {
        if (existsSync(path.resolve(dir, match))) return match; // 本来就对
        const fromSkillsRoot = path.join(skillsRoot, rest);
        if (!existsSync(fromSkillsRoot)) return match; // 目标真不存在，留给人工
        const corrected = path.relative(dir, fromSkillsRoot).replaceAll(path.sep, "/");
        fixed += 1;
        return corrected;
      },
    );
    if (before !== after) writeFileSync(file, after);
  });
  return fixed;
}

// ---------- 执行 ----------
const plan = [];

// 1. 7 个 skill
for (const spec of SKILLS) {
  const from = path.join(src, spec.from);
  const to = path.join(skillsRoot, spec.to);
  if (!existsSync(from)) throw new Error(`源缺失：${spec.from}`);
  plan.push(`copy   ${spec.from} → skills/${spec.to}`);
  if (dryRun) continue;
  rmSync(to, { recursive: true, force: true });
  cpSync(from, to, {
    recursive: true,
    filter: (s) => {
      const base = path.basename(s);
      // agents/openai.yaml 是 CCFA 给 Codex 用的 agent 定义，OMP 有自己的 5 个 agent
      if (base === "agents" && statSync(s).isDirectory()) return false;
      return !s.endsWith(".pdf") && base !== ".DS_Store";
    },
  });
  convertFrontmatter(to, spec);
}

// 2. _shared
const sharedDir = path.join(skillsRoot, "_shared");
plan.push(`copy   ccf-common/references/{${SHARED_FILES.length} files} → skills/_shared/`);
if (!dryRun) {
  rmSync(sharedDir, { recursive: true, force: true });
  mkdirSync(sharedDir, { recursive: true });
  for (const f of SHARED_FILES) {
    cpSync(path.join(src, "ccf-common", "references", f), path.join(sharedDir, f));
  }
  writeFileSync(
    path.join(sharedDir, "README.md"),
    [
      "# 共享参考（vendored from CCFA-Skills）",
      "",
      "本目录不是 skill（没有 SKILL.md，不会进 `research-catalog.json`）。这里放的是被",
      "多个论文类 skill 引用的共享规则，来自 CCFA-Skills 的 `ccf-common/references/`。",
      "",
      `来源：https://github.com/mikubaka88/CCFA-Skills @ \`${upstreamRevision}\`（MIT）`,
      "",
      "引用方式：从 skill 目录用 `../_shared/<file>` 引用。",
      "",
      "未吸收的上游文件：`routing.md`、`skill-trigger-registry.yaml`（CCFA 家族内部路由，",
      "本仓库用 `research-stage-map.json` + conductor agent 代替）、`ccfa-yaml-contract.md`",
      "（与本仓库的 `.pipeline/` 状态模型冲突）。",
      "",
    ].join("\n"),
  );
}

// 3. LaTeX 模板 → paper-writing/templates/
// 剔除 .dtx/.ins（宏包带文档源码；同目录已有 .cls/.sty 时编译用不到）与示例图。
const tplDst = path.join(skillsRoot, "paper-writing", "templates");
plan.push(`copy   ccf-latex-templates/ → skills/paper-writing/templates/（瘦身）`);
if (!dryRun) {
  const tplSrc = path.join(src, "ccf-latex-templates");
  rmSync(tplDst, { recursive: true, force: true });
  const hasBuilt = new Set();
  walk(tplSrc, (f) => {
    const ext = path.extname(f);
    if (ext === ".cls" || ext === ".sty") hasBuilt.add(path.dirname(f));
  });
  walk(tplSrc, (f) => {
    const ext = path.extname(f);
    const base = path.basename(f);
    if (base === ".DS_Store") return;
    if (ext === ".pdf") return;
    if ((ext === ".dtx" || ext === ".ins") && hasBuilt.has(path.dirname(f))) return;
    const rel = path.relative(tplSrc, f);
    const dst = path.join(tplDst, rel);
    mkdirSync(path.dirname(dst), { recursive: true });
    cpSync(f, dst);
  });
}

// 4. 文本重写（skill + _shared 全量）
if (!dryRun) {
  let touched = 0;
  for (const spec of SKILLS) touched += rewriteTree(path.join(skillsRoot, spec.to));
  touched += rewriteTree(sharedDir);
  plan.push(`rewrite ${touched} 个文件的路径与 skill 名引用`);

  // 重写后再修正相对深度（此时 _shared 与新 skill 目录都已就位）
  let depth = 0;
  for (const spec of SKILLS) depth += fixRelativeDepth(path.join(skillsRoot, spec.to));
  depth += fixRelativeDepth(sharedDir);
  plan.push(`fix     ${depth} 处相对路径深度`);
}

// 5. 删除被替换的旧 skill
for (const spec of SKILLS) {
  for (const old of spec.replaces) {
    const dir = path.join(skillsRoot, old);
    if (!existsSync(dir)) continue;
    plan.push(`remove skills/${old}（由 ${spec.to} 取代）`);
    if (!dryRun) rmSync(dir, { recursive: true, force: true });
  }
}

process.stdout.write(plan.map((l) => (dryRun ? `[dry] ${l}` : l)).join("\n") + "\n");
process.stdout.write(`\n上游 commit: ${upstreamRevision}\n`);
