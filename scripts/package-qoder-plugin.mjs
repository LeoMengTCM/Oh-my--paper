#!/usr/bin/env node
/**
 * Package plugins/oh-my-paper as a Qoder plugin ZIP.
 *
 * Qoder requires `.qoder-plugin/` at the ZIP root. The repo's `skills` entry is
 * a symlink, so the staging copy dereferences it into real files; Qoder's local
 * installer skips symlinks that escape the plugin root.
 */
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pluginDir = path.join(repoRoot, "plugins/oh-my-paper");
const manifestPath = path.join(pluginDir, ".qoder-plugin/plugin.json");
const outDir = path.join(repoRoot, "dist");
const stagingDir = path.join(outDir, ".qoder-plugin-build");

function fail(message) {
  console.error(`Qoder 打包失败：${message}`);
  process.exit(1);
}

if (!existsSync(manifestPath)) fail("缺少 plugins/oh-my-paper/.qoder-plugin/plugin.json");
if (!existsSync(path.join(pluginDir, "hooks/qoder-hooks.json"))) fail("缺少 plugins/oh-my-paper/hooks/qoder-hooks.json");

const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const pkg = JSON.parse(readFileSync(path.join(repoRoot, "package.json"), "utf8"));
if (manifest.version !== pkg.version) {
  fail(`版本不一致：package.json=${pkg.version}, .qoder-plugin/plugin.json=${manifest.version}`);
}

for (const rel of ["commands", "agents", "skills", "scripts", "hooks/qoder-hooks.json"]) {
  if (!existsSync(path.join(pluginDir, rel))) fail(`清单引用的路径不存在：${rel}`);
}

const hooksText = readFileSync(path.join(pluginDir, "hooks/qoder-hooks.json"), "utf8");
if (!hooksText.includes("${QODER_PLUGIN_ROOT}")) fail("qoder-hooks.json 未使用 ${QODER_PLUGIN_ROOT}");
if (hooksText.includes("${CLAUDE_PLUGIN_ROOT}")) fail("qoder-hooks.json 不应包含 ${CLAUDE_PLUGIN_ROOT}");

rmSync(stagingDir, { recursive: true, force: true });
mkdirSync(stagingDir, { recursive: true });

const isExcluded = (src) => {
  const name = path.basename(src);
  return name === ".DS_Store" || name === "__pycache__" || name.endsWith(".pyc");
};

for (const rel of [".qoder-plugin", "commands", "agents", "scripts"]) {
  cpSync(path.join(pluginDir, rel), path.join(stagingDir, rel), {
    recursive: true,
    dereference: true,
    filter: (src) => !isExcluded(src),
  });
}
mkdirSync(path.join(stagingDir, "hooks"), { recursive: true });
cpSync(path.join(pluginDir, "hooks/qoder-hooks.json"), path.join(stagingDir, "hooks/qoder-hooks.json"));
cpSync(path.join(pluginDir, "skills"), path.join(stagingDir, "skills"), {
  recursive: true,
  dereference: true,
  filter: (src) => !isExcluded(src),
});
cpSync(path.join(repoRoot, "LICENSE"), path.join(stagingDir, "LICENSE"));

const zipPath = path.join(outDir, `omp-qoder-${manifest.version}.zip`);
rmSync(zipPath, { force: true });
execFileSync("zip", ["-qr", zipPath, ".", "-x", "*.DS_Store", "*__pycache__*", "*.pyc"], {
  cwd: stagingDir,
  stdio: "inherit",
});
rmSync(stagingDir, { recursive: true, force: true });

const size = statSync(zipPath).size;
console.log(`\nQoder 插件包：${zipPath}`);
console.log(`大小：${(size / 1024 / 1024).toFixed(1)} MB`);
console.log("安装：Qoder → Extensions → Plugins → Add Plugin → Upload Plugin，选择该 ZIP。");
