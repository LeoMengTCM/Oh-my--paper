#!/usr/bin/env node
// Codex lifecycle adapter. Research approvals and task completion remain explicit.
import { readFileSync, existsSync, writeFileSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { stopDecision } from '../skills/omp/scripts/continuation.mjs';

const scripts = path.dirname(fileURLToPath(import.meta.url));
function acquire(lock) {
  try { writeFileSync(lock, String(process.pid), { flag: 'wx' }); return true; }
  catch (error) { if (error.code !== 'EEXIST') throw error; }
  let pid;
  try { pid = Number(readFileSync(lock, 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') return false; throw error; }
  if (!Number.isInteger(pid) || pid <= 0) throw new Error('Incomplete hook lock; inspect .pipeline/.codex-hook-lock before retrying');
  try { process.kill(pid, 0); return false; }
  catch (error) { if (error.code !== 'ESRCH') throw error; }
  // Recover only after the owning process is confirmed absent.
  rmSync(lock, { force: true });
  try { writeFileSync(lock, String(process.pid), { flag: 'wx' }); return true; }
  catch (error) { if (error.code === 'EEXIST') return false; throw error; }
}
const input = [];
for await (const chunk of process.stdin) input.push(chunk);
try {
  const event = JSON.parse(Buffer.concat(input).toString('utf8'));
  const project = path.resolve(event.cwd ?? process.cwd());
  const pipeline = path.join(project, '.pipeline');
  const output = {};
  if (existsSync(pipeline)) {
    const run = (script, stdin = '') => execFileSync(process.execPath, [path.join(scripts, script)], {
      cwd: project, input: stdin, encoding: 'utf8', timeout: 10000, stdio: ['pipe', 'pipe', 'pipe'],
    }).trim();
    if (event.hook_event_name === 'SessionStart') {
      const context = run('on-session-start.mjs');
      if (context) output.hookSpecificOutput = { hookEventName: 'SessionStart', additionalContext: context };
    } else if (['PostToolUse', 'Stop', 'SubagentStop'].includes(event.hook_event_name)) {
      const lock = path.join(pipeline, '.codex-hook-lock');
      let acquired = false;
      try {
        acquired = acquire(lock);
        if (!acquired) { console.log(JSON.stringify(stopDecision(event, project))); process.exit(0); }
        const statePath = path.join(pipeline, '.codex-hook-state.json');
        const state = existsSync(statePath) ? JSON.parse(readFileSync(statePath, 'utf8')) : {};
        if (event.hook_event_name === 'PostToolUse') {
          const taskFile = path.join(pipeline, 'tasks/tasks.json');
          const briefFile = path.join(pipeline, 'docs/research_brief.json');
          if (existsSync(taskFile) && existsSync(briefFile)) {
            const signature = createHash('sha256').update(readFileSync(taskFile)).update(readFileSync(briefFile)).digest('hex');
            if (signature !== state.stageSignature) {
              const context = run('on-stage-transition.mjs');
              state.stageSignature = signature;
              if (context) output.hookSpecificOutput = { hookEventName: 'PostToolUse', additionalContext: context };
            }
          }
        } else {
          const message = event.last_assistant_message;
          if (typeof message === 'string' && message.includes('```omp_executor_report')) {
            const key = createHash('sha256').update(JSON.stringify([event.session_id, event.turn_id, event.agent_id, message])).digest('hex');
            if (!(state.reports ?? []).includes(key)) {
              run('on-task-complete.mjs', message);
              state.reports = [...(state.reports ?? []), key].slice(-100);
            }
          }
        }
        writeFileSync(statePath, JSON.stringify(state, null, 2) + '\n');
      } finally {
        if (acquired) rmSync(lock, { force: true });
      }
    }
  }
  Object.assign(output, stopDecision(event, project));
  console.log(JSON.stringify(output));
} catch (error) {
  console.error(`Oh My Paper hook: ${error.stderr?.toString().trim() || error.message}`);
  process.exitCode = 1;
}
