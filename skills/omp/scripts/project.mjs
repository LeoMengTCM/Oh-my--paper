#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { readTaskDocument } from '../../inno-pipeline-planner/scripts/task-contract.mjs';

const skill = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const stages = ['survey', 'ideation', 'experiment', 'publication', 'promotion'];
const tracks = ['ml', 'clinical', 'systematic-review', 'bioinformatics'];
const start = '<!-- oh-my-paper:begin -->';
const end = '<!-- oh-my-paper:end -->';
const memories = ['project_truth', 'orchestrator_state', 'execution_context', 'experiment_ledger',
  'figure_ledger', 'result_summary', 'review_log', 'literature_bank', 'agent_handoff', 'decision_log'];

function readJson(file) { return JSON.parse(readFileSync(file, 'utf8')); }
function contentHash(content) { return createHash('sha256').update(content).digest('hex'); }
function managedBlock() {
  return `${start}
## Oh My Paper — Codex research workflow

Read .pipeline/codex.json to locate the installed omp skill and its resources.
At session start, read .pipeline/docs/research_brief.json and validate
.pipeline/tasks/tasks.json with the task-contract.mjs path in that file.
Before choosing a workflow, read the omp skill and run its scripts/workflow.mjs
with --project . --intent continue (choose-topic for broad topic selection).
Check current tasks and actual evidence first. Topic selection begins with survey
unless its existing evidence has been checked. Read the routed workflow and role.

Five stages: survey → ideation → experiment → publication → promotion.
Resume from current artifacts and live process handles, not old completion markers.
After each verified subtask, update its task record (artifacts and completionSummary)
and project_truth.md. Re-run the preflight and execute the next authorized task;
do not wait for the user to remind you to follow OMP. Survey counts or a done flag
alone are insufficient. Reuse existing Survey/ or survey/ files at their actual paths.
Stop for real research decisions such as final topic selection or protocol approval,
not a routine stage menu. Honor explicitly scoped standalone work.
Standard OMP ideation follows omp-ideate: five directions, confirmed evaluation
scope, inno-idea-eval, then final user selection. Do not replace it with the
standalone 2–4-candidate Research Idea Convergence workflow.
After selection, hand off to evidence integration/experiments, then drafting,
integrity checks, scientific review, revision and re-review. publication is not
always writing: use task.workflow and suggestedSkills to route the operation.
Distinguish checkpointType=artifact from checkpointType=user. Routine checks and
authorized revisions continue without a stage menu; protocol/topic changes remain
user decisions. Unresolved review issues block submission/promotion. A completed
review report does not mean the manuscript passed. Promotion/submission are scoped,
and external submission or uploading needs its own authorization.
Use projectContext.researchType/articleType to interpret legacy track values:
narrative-review means evidence integration, not ML training or RCT/Meta analysis.
Preserve task IDs and legacy document structure. A task marked done is not
evidence of protocol approval. Review applicable gates before stage advancement.
For systematic-review, use systematic-review/references/rct-pairwise-profile.md
under the configured skills directory: exploratory survey → approved protocol/SAP
→ formal retrieval, screening, extraction and synthesis → writing and reporting.
Confirmatory analysis follows the approved plan; record deviations and approvals.
Never invent human reviewers, decisions, citations or results.

Project roles are in .codex/agents/omp-*.toml and inherit the current model.
Use native subagents only for requested or already-authorized delegation.
Optional plugin hooks restore context and record reminders after host trust review.
If unavailable, perform the same task/memory checks explicitly. Hooks do not approve
research decisions and do not mark tasks complete automatically.
For the authorized full project, register this session with the omp skill's
scripts/continuation.mjs start (CODEX_THREAD_ID), the actual objective, last requested
stage and final deliverable paths. Inspect status on resume; do not restart its
registration each task. Continue inspect/execute/verify/record/route until the real
deliverable or user decision. Use wait only for a specific real decision/resource,
pause only on the user's request, and finish only after completion audit. Trusted
Stop hooks reject premature final responses in that registered session. Untrusted
hooks are not running; never report them as active.
${end}`;
}

function parse(argv) {
  const command = argv.shift();
  if (!['init', 'status'].includes(command)) throw new Error('Usage: project.mjs <init|status> [--project PATH] [--topic TEXT] [--track ml|clinical|systematic-review|bioinformatics] [--stage STAGE]');
  const args = { command };
  while (argv.length) {
    const flag = argv.shift();
    if (!['--project', '--topic', '--track', '--stage'].includes(flag) || !argv.length) throw new Error(`Invalid argument: ${flag}`);
    args[flag.slice(2)] = argv.shift();
  }
  if (args.stage && !stages.includes(args.stage)) throw new Error(`Invalid stage: ${args.stage}`);
  if (args.track && !tracks.includes(args.track)) throw new Error(`Invalid track: ${args.track}`);
  return args;
}

function main() {
  const args = parse(process.argv.slice(2));
  const project = path.resolve(args.project ?? process.cwd());
  const briefPath = path.join(project, '.pipeline/docs/research_brief.json');
  const tasksPath = path.join(project, '.pipeline/tasks/tasks.json');
  const existing = existsSync(briefPath) ? readJson(briefPath) : null;
  const tasks = existsSync(tasksPath) ? readTaskDocument(tasksPath) : null;
  const roleNames = readdirSync(path.join(skill, 'roles')).filter(name => name.endsWith('.toml'));
  if (args.command === 'status') {
    const required = ['AGENTS.md', '.pipeline/codex.json', '.pipeline/docs/research_brief.json', '.pipeline/tasks/tasks.json',
      ...roleNames.map(name => `.codex/agents/omp-${name}`), ...memories.map(name => `.pipeline/memory/${name}.md`)];
    const missing = required.filter(name => !existsSync(path.join(project, name)));
    const configPath = path.join(project, '.pipeline/codex.json');
    const config = existsSync(configPath) ? readJson(configPath) : null;
    const resourcesAvailable = Boolean(config && [config.skill, config.taskContract].every(file => typeof file === 'string' && existsSync(file)));
    console.log(JSON.stringify({ project, initialized: missing.length === 0 && resourcesAvailable, missing, resourcesAvailable,
      topic: existing?.topic ?? null, stage: existing?.currentStage ?? null,
      track: existing?.pipeline?.track ?? existing?.track ?? null, taskCount: tasks?.tasks.length ?? null }, null, 2));
    return;
  }
  if (existing && (typeof existing !== 'object' || Array.isArray(existing))) throw new Error('Existing research brief must be an object');
  const topic = existing?.topic ?? args.topic;
  const track = existing?.pipeline?.track ?? existing?.track ?? args.track ?? 'ml';
  const stage = existing?.currentStage ?? args.stage ?? 'survey';
  if (typeof topic !== 'string' || !topic.trim()) throw new Error('A research topic is required (--topic)');
  if (!tracks.includes(track) || !stages.includes(stage)) throw new Error('Existing track or stage needs review; no files changed');
  for (const [key, value] of [['topic', topic], ['track', track], ['stage', stage]]) {
    if (args[key] && args[key] !== value) throw new Error(`Existing ${key} differs; use the plan workflow to revise it, not init`);
  }

  // Prepare all writes before modifying the project; existing research files stay intact.
  const writes = new Map();
  const create = (relative, content) => { if (!existsSync(path.join(project, relative))) writes.set(relative, content); };
  create('.pipeline/docs/research_brief.json', JSON.stringify({ topic, goal: '', currentStage: stage,
    pipeline: { track, analysisMode: ['clinical', 'systematic-review'].includes(track) ? 'confirmatory' : 'exploratory', startStage: stage } }, null, 2) + '\n');
  create('.pipeline/tasks/tasks.json', JSON.stringify({ version: 1, tasks: [] }, null, 2) + '\n');
  for (const name of memories) create(`.pipeline/memory/${name}.md`, `# ${name.split('_').join(' ')}\n${name === 'project_truth' ? `\nResearch topic: ${topic}\n` : ''}`);
  if (['clinical', 'systematic-review'].includes(track)) {
    create('.pipeline/docs/protocol.md', '# Protocol\n\nStatus: draft — research decisions and approval pending.\n');
    create('.pipeline/docs/sap.md', '# Statistical analysis plan\n\nStatus: draft — methods and approval pending.\n');
    create('.pipeline/memory/protocol_deviations.md', '# Protocol deviations\n');
  }
  const existingConfigPath = path.join(project, '.pipeline/codex.json');
  const previousRoles = existsSync(existingConfigPath) ? readJson(existingConfigPath).managedRoles ?? {} : {};
  const config = { schema_version: 1, skill: path.join(skill, 'SKILL.md'), skills: path.dirname(skill), managedRoles: {},
    taskContract: path.resolve(skill, '../inno-pipeline-planner/scripts/task-contract.mjs'),
    workflow: path.join(skill, 'scripts/workflow.mjs') };
  config.continuation = path.join(skill, 'scripts/continuation.mjs');
  const agentsPath = path.join(project, 'AGENTS.md');
  const original = existsSync(agentsPath) ? readFileSync(agentsPath, 'utf8') : '';
  const first = original.indexOf(start), last = original.indexOf(end);
  if ((first >= 0) !== (last >= 0) || (first >= 0 && (last < first || original.indexOf(start, first + 1) >= 0 || original.indexOf(end, last + 1) >= 0))) {
    throw new Error('AGENTS.md has conflicting Oh My Paper blocks; no files changed');
  }
  const agents = first < 0 ? `${original}${original && !original.endsWith('\n') ? '\n' : ''}\n${managedBlock()}\n`
    : original.slice(0, first) + managedBlock() + original.slice(last + end.length);
  writes.set('AGENTS.md', agents);
  const preservedRoles = [];
  for (const name of roleNames) {
    const relative = `.codex/agents/omp-${name}`;
    const content = readFileSync(path.join(skill, 'roles', name), 'utf8');
    const current = existsSync(path.join(project, relative)) ? readFileSync(path.join(project, relative), 'utf8') : null;
    if (current !== null && current !== content && previousRoles[relative] !== contentHash(current)) {
      preservedRoles.push(relative);
      if (previousRoles[relative]) config.managedRoles[relative] = previousRoles[relative];
    } else {
      writes.set(relative, content);
      config.managedRoles[relative] = contentHash(content);
    }
  }
  writes.set('.pipeline/codex.json', JSON.stringify(config, null, 2) + '\n');
  const changed = [];
  for (const [relative, content] of writes) {
    const file = path.join(project, relative);
    if (existsSync(file) && readFileSync(file, 'utf8') === content) continue;
    mkdirSync(path.dirname(file), { recursive: true });
    writeFileSync(file, content);
    changed.push(relative);
  }
  console.log(JSON.stringify({ project, topic, track, stage, changed, preservedRoles,
    next: 'Start a new Codex session to load project roles; ask Oh My Paper to plan the next task.' }, null, 2));
}

try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
