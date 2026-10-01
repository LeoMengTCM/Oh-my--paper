#!/usr/bin/env node
// Opt-in, session-bound continuation. Does not modify research tasks or hook trust.
import { existsSync, mkdirSync, readFileSync, writeFileSync, renameSync, statSync, realpathSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import path from 'node:path';

const directory = path.dirname(fileURLToPath(import.meta.url));
const terminal = 'review-completion-or-plan-next';
function statePath(project, sessionId) {
  if (typeof sessionId !== 'string' || !/^[a-zA-Z0-9_-]+$/.test(sessionId)) throw new Error('A valid Codex session ID is required (CODEX_THREAD_ID or --session-id)');
  return path.join(project, '.pipeline/.codex-continuation', `${sessionId}.json`);
}
function save(file, state) {
  mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  writeFileSync(tmp, JSON.stringify(state, null, 2) + '\n');
  renameSync(tmp, file);
}
function route(project, state) {
  return JSON.parse(execFileSync(process.execPath, [path.join(directory, 'workflow.mjs'), '--project', project, '--through', state.through], { encoding: 'utf8', timeout: 10000 }));
}
function deliveriesExist(project, state) {
  return state.deliverables.length > 0 && state.deliverables.every(file => {
    const absolute = path.resolve(project, file);
    return existsSync(absolute) && statSync(absolute).isFile() && statSync(absolute).size > 0;
  });
}

export function stopDecision(event, project) {
  if (event.hook_event_name !== 'Stop' || typeof event.session_id !== 'string') return {};
  const file = statePath(project, event.session_id);
  if (!existsSync(file)) return {};
  const state = JSON.parse(readFileSync(file, 'utf8'));
  if (state.status !== 'active') return {};
  const next = route(project, state);
  if (next.action === 'review-checkpoint') {
    state.lastCheckpoint = { taskId: next.taskId, title: next.taskTitle };
    save(file, state);
    return {};
  }
  const signature = createHash('sha256');
  for (const relative of ['.pipeline/tasks/tasks.json', '.pipeline/docs/research_brief.json', '.pipeline/memory/project_truth.md', '.pipeline/memory/execution_context.md']) {
    const target = path.join(project, relative);
    if (existsSync(target)) signature.update(readFileSync(target));
  }
  for (const relative of [...(next.evidenceToRead ?? []), ...state.deliverables]) {
    const target = path.resolve(project, relative);
    if (existsSync(target) && statSync(target).isFile()) signature.update(`${target}:${statSync(target).mtimeMs}:${statSync(target).size}`);
  }
  const digest = signature.digest('hex');
  // Repeated delivery of one hook event must not count as another failed attempt.
  const eventId = `${event.turn_id ?? ''}:${event.last_assistant_message ?? ''}`;
  if (state.lastEvent !== eventId) {
    state.unchangedStops = state.lastSignature === digest ? (state.unchangedStops ?? 0) + 1 : 0;
    state.lastEvent = eventId;
    state.lastSignature = digest;
  }
  if (state.unchangedStops >= 2) {
    state.status = 'stalled';
    state.reason = 'Repeated continuation made no recorded progress. Inspect the actual failure; remaining work is not complete.';
    save(file, state);
    return { systemMessage: `Oh My Paper continuation stalled: ${state.reason}` };
  }
  save(file, state);
  const finish = next.action === terminal
    ? `Review the authorized objective and current deliverables. ${deliveriesExist(project, state) ? 'If the complete scope is satisfied, run continuation.mjs finish with a concrete completion summary.' : 'Required deliverables are still missing; produce or repair them.'} Do not invent extra stages beyond the requested scope.`
    : `Continue task ${next.taskId ?? '(planning)'} via ${next.workflow}: ${next.next ?? next.action}.`;
  return { decision: 'block', reason: `The user already authorized this OMP workflow through ${state.through}: ${state.objective}. ${finish} Do the work now without asking for another workflow reminder. Stop for a real user decision or external blocker; record that reason using continuation.mjs wait. Do not mark work done merely to exit.` };
}

function main() {
  const args = { project: process.cwd(), sessionId: process.env.CODEX_THREAD_ID, through: 'publication', deliverables: [] };
  const [command, ...rest] = process.argv.slice(2);
  if (!['start', 'status', 'wait', 'resume', 'pause', 'finish'].includes(command)) throw new Error('Usage: continuation.mjs start|status|wait|resume|pause|finish --project PATH [--session-id ID] [--objective TEXT --through STAGE --deliverable PATH] [--reason TEXT]');
  const flags = { '--project': 'project', '--session-id': 'sessionId', '--objective': 'objective', '--through': 'through', '--reason': 'reason', '--kind': 'kind', '--summary': 'summary' };
  for (let i = 0; i < rest.length; i++) {
    const flag = rest[i];
    if (flag === '--deliverable' && rest[i + 1]) args.deliverables.push(rest[++i]);
    else if (flags[flag] && rest[i + 1]) args[flags[flag]] = rest[++i];
    else throw new Error(`Unknown or incomplete argument: ${flag}`);
  }
  const project = path.resolve(args.project), file = statePath(project, args.sessionId);
  let state = existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : null;
  if (command === 'status') { console.log(JSON.stringify(state ?? { status: 'inactive' }, null, 2)); return; }
  if (command === 'start') {
    if (!args.objective?.trim() || !args.deliverables.length || !['survey', 'ideation', 'experiment', 'publication', 'promotion'].includes(args.through)) throw new Error('Start requires objective, valid through stage and at least one deliverable');
    if (state?.status === 'active') {
      if (state.objective !== args.objective || state.through !== args.through || JSON.stringify(state.deliverables) !== JSON.stringify(args.deliverables)) throw new Error('An active workflow exists; finish or explicitly pause it before changing scope');
      console.log(JSON.stringify(state, null, 2)); return;
    }
    state = { schema_version: 1, sessionId: args.sessionId, status: 'active', objective: args.objective, through: args.through, deliverables: args.deliverables, unchangedStops: 0 };
    route(project, state); // Validate before arming.
  } else {
    if (!state) throw new Error('This session has no registered OMP workflow');
    if (command === 'finish') {
      if (route(project, state).action !== terminal || !deliveriesExist(project, state) || !args.summary?.trim()) throw new Error('Cannot finish: pending tasks, missing deliverables or missing completion summary');
      state.status = 'complete'; state.completionSummary = args.summary;
    } else if (command === 'resume') {
      state.status = 'active'; state.unchangedStops = 0; delete state.lastSignature; delete state.lastEvent; delete state.reason;
    } else {
      if (!args.reason?.trim()) throw new Error('A concrete reason is required');
      if (command === 'wait' && !['user-decision', 'external-blocker'].includes(args.kind)) throw new Error('Wait requires --kind user-decision|external-blocker');
      state.status = command === 'pause' ? 'paused' : 'waiting'; state.reason = args.reason; state.waitKind = args.kind;
    }
  }
  save(file, state);
  console.log(JSON.stringify(state, null, 2));
}
if (process.argv[1] && existsSync(process.argv[1]) && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
}
