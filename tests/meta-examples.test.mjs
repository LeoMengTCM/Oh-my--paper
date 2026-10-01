import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const text = readFileSync(path.join(root, "skills/systematic-review/references/meta-analysis-R.md"), "utf8");
const blocks = [...text.matchAll(/```r\n([\s\S]*?)```/g)].map((match) => match[1]);
const rAvailable = spawnSync("Rscript", ["--version"], { encoding: "utf8" }).status === 0;

function runR(t, code) {
  const dir = mkdtempSync(path.join(os.tmpdir(), "omp-r-example-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const file = path.join(dir, "check.R");
  writeFileSync(file, code);
  return spawnSync("Rscript", ["--vanilla", file], { cwd: dir, encoding: "utf8" });
}

test("文档内所有 R 示例通过真实 R 语法解析", { skip: !rAvailable && "未安装 R" }, (t) => {
  assert.ok(blocks.length >= 6);
  const code = blocks.map((block) => `parse(text = ${JSON.stringify(block)})`).join("\n");
  const result = runR(t, code);
  assert.equal(result.status, 0, result.stderr);
});

test("RR/OR/RD 示例的合并效应保持正确尺度", { skip: !rAvailable && "未安装 R" }, (t) => {
  const installed = spawnSync("Rscript", ["--vanilla", "-e",
    'quit(status = if (requireNamespace("metafor", quietly=TRUE)) 0 else 42)'], { encoding: "utf8" });
  if (installed.status === 42) return t.skip("未安装 metafor；统计计算和图形运行未验证");
  assert.equal(installed.status, 0, installed.stderr);
  // 合成的相同研究：RR=0.5、OR=0.375、RD=-0.2，期望值不由被测代码生成。
  for (const [measure, expected] of [["RR", 0.5], ["OR", 0.375], ["RD", -0.2]]) {
    assert.match(blocks[0], /measure <- "RR"/);
    const code = `
      df <- data.frame(author=paste0("fixture-", 1:6), year=2020,
                       ev_t=20, n_t=100, ev_c=40, n_c=100)
      pdf("example.pdf")
      ${blocks[0].replace('measure <- "RR"', `measure <- "${measure}"`)}
      dev.off()
      stopifnot(abs(pooled$pred - ${expected}) < 1e-7)
    `;
    const result = runR(t, code);
    assert.equal(result.status, 0, `${measure}: ${result.stderr}`);
  }
});
