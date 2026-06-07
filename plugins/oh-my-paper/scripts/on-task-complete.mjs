/**
 * on-task-complete.mjs
 * Stop hook — 从 transcript 里解析 omp_executor_report 块，追加到 review_log.md
 *
 * 注意：Stop hook 通过 stdin 收到的是 JSON（含 transcript_path、session_id、
 * stop_hook_active 等），并不包含对话正文。助手的回复正文在 transcript_path
 * 指向的 JSONL 文件里，需要读取后从最近一条 assistant 消息中提取 report。
 * （此前的版本把 stdin 当纯文本直接正则搜索代码块，永远匹配不到，hook 静默失效。）
 */
import fs from "node:fs/promises";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const PROJECT = process.cwd();

async function main() {
  const stdin = await readStdin();
  if (!stdin.trim()) return;

  const transcriptText = resolveTranscriptText(stdin);
  if (!transcriptText) return;

  const report = extractExecutorReport(transcriptText);
  if (!report) return;

  const reviewLogPath = path.join(PROJECT, ".pipeline", "memory", "review_log.md");
  const ts = new Date().toISOString().slice(0, 16).replace("T", " ");
  const entry = [
    `\n## Executor Report — ${ts}`,
    `**Task**: ${report.taskId || "unknown"}`,
    `**Summary**: ${report.summary || ""}`,
    `**Confidence**: ${report.confidence || "unknown"}`,
    report.artifacts?.length ? `**Artifacts**: ${report.artifacts.join(", ")}` : "",
    report.issues?.length ? `**Issues**: ${report.issues.join("; ")}` : "",
    "**Status**: ⏳ pending-review",
    "",
  ].filter(Boolean).join("\n");

  await fs.mkdir(path.dirname(reviewLogPath), { recursive: true });
  await fs.appendFile(reviewLogPath, entry + "\n", "utf8");

  // hook-event 通知
  const eventsDir = path.join(PROJECT, ".pipeline", ".hook-events");
  await fs.mkdir(eventsDir, { recursive: true });
  await fs.writeFile(
    path.join(eventsDir, `${Date.now()}.json`),
    JSON.stringify({ type: "executor-report", taskId: report.taskId, timestamp: Date.now() }),
    "utf8"
  );
}

/**
 * Stop hook 的 stdin 是 JSON：{ transcript_path, session_id, stop_hook_active, ... }
 * 读取 transcript（JSONL，每行一个事件），返回最近一条含 executor report 的
 * assistant 文本；若没有任何 report 标记，则返回最后一条 assistant 文本。
 * 若 stdin 不是 JSON（格式变化时的兜底），回退为把 stdin 本身当作文本。
 */
function resolveTranscriptText(stdin) {
  let payload;
  try {
    payload = JSON.parse(stdin);
  } catch {
    return stdin;
  }

  const transcriptPath = payload.transcript_path;
  if (!transcriptPath || !existsSync(transcriptPath)) return "";

  let raw;
  try {
    raw = readFileSync(transcriptPath, "utf8");
  } catch {
    return "";
  }

  const assistantTexts = [];
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    let evt;
    try {
      evt = JSON.parse(line);
    } catch {
      continue;
    }
    if (evt.type !== "assistant" || !evt.message) continue;
    const content = evt.message.content;
    let text = "";
    if (typeof content === "string") {
      text = content;
    } else if (Array.isArray(content)) {
      text = content
        .filter((block) => block?.type === "text")
        .map((block) => block.text || "")
        .join("\n");
    }
    if (text.trim()) assistantTexts.push(text);
  }

  for (let i = assistantTexts.length - 1; i >= 0; i -= 1) {
    if (assistantTexts[i].includes("omp_executor_report")) return assistantTexts[i];
  }
  return assistantTexts.length ? assistantTexts[assistantTexts.length - 1] : "";
}

function extractExecutorReport(text) {
  const matches = [...text.matchAll(/```omp_executor_report\s*([\s\S]*?)```/g)];
  if (!matches.length) return null;
  try {
    return JSON.parse(matches[matches.length - 1][1].trim());
  } catch {
    return null;
  }
}

async function readStdin() {
  if (process.stdin.isTTY) return "";
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

main().catch(() => process.exit(0));
