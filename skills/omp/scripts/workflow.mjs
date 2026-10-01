#!/usr/bin/env node
// Read-only routing: inspect pipeline state before interpreting a downstream request.
import { existsSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { readTaskDocument } from '../../inno-pipeline-planner/scripts/task-contract.mjs';

const stages = ['survey', 'ideation', 'experiment', 'publication', 'promotion'];
const workflows = { survey: 'survey', ideation: 'ideate', experiment: 'experiment', publication: 'write', promotion: 'write' };
const intents = ['continue', 'choose-topic', 'setup', 'plan', 'survey', 'ideate', 'experiment', 'write', 'review', 'delegate', 'sync'];
function taskRoute(task) {
  const skills = (task.suggestedSkills ?? task.recommended_skills ?? []).map(name => String(name).split(':').at(-1));
  const special = ['submission-checker', 'integrity-auditor'].find(name => skills.includes(name));
  const reviewer = special ?? ['paper-reviewer', 'inno-paper-reviewer'].find(name => skills.includes(name));
  let workflow = task.workflow;
  if (!workflow) {
    workflow = reviewer || ['reviewer', 'omp-reviewer'].includes(task.assignee) ? 'review' : workflows[task.stage];
  }
  if (task.status === 'review' && task.stage === 'publication' && task.checkpointType !== 'user') workflow = 'review';
  return { workflow, skill: workflow === 'review' ? special ?? null : skills.includes('rebuttal-writer') ? 'rebuttal-writer' : null };
}
function main() {
  const args = { project: process.cwd(), intent: 'continue', standalone: false, through: 'promotion' };
  for (let i = 2; i < process.argv.length; i++) {
    const flag = process.argv[i];
    if (flag === '--standalone') args.standalone = true;
    else if (['--project', '--intent', '--through'].includes(flag) && process.argv[i + 1]) args[flag.slice(2)] = process.argv[++i];
    else throw new Error(`Unknown or incomplete argument: ${flag}`);
  }
  if (!intents.includes(args.intent)) throw new Error(`Unknown intent: ${args.intent}`);
  if (!stages.includes(args.through)) throw new Error(`Unknown terminal stage: ${args.through}`);
  const project = path.resolve(args.project);
  const result = { workflow: 'setup', action: 'initialize', canRecommendTopics: false, requiresStageMenu: false,
    evidenceToRead: [], note: 'This checks task structure and artifact availability; read the evidence to assess research quality and approvals.' };
  const emit = fields => console.log(JSON.stringify({ ...result, ...fields }, null, 2));
  if (args.standalone) return emit({ workflow: args.intent === 'choose-topic' ? 'ideate' : args.intent === 'continue' ? 'plan' : args.intent, action: 'standalone', note: 'Follow the explicitly scoped standalone task; do not claim completion of the full research pipeline.' });
  const briefFile = path.join(project, '.pipeline/docs/research_brief.json');
  const tasksFile = path.join(project, '.pipeline/tasks/tasks.json');
  if (!existsSync(briefFile) || !existsSync(tasksFile)) return emit({ next: 'Use existing project material and stated topic to initialize; do not recommend topics before survey.' });
  const brief = JSON.parse(readFileSync(briefFile, 'utf8'));
  const { tasks } = readTaskDocument(tasksFile);
  const current = brief.currentStage;
  const start = brief.pipeline?.startStage ?? current;
  if (!stages.includes(current) || !stages.includes(start)) throw new Error('Review currentStage/startStage before routing');
  const byId = new Map(tasks.map(task => [task.id, task]));
  const visited = new Set(), visiting = new Set();
  function check(task) {
    if (visiting.has(task.id)) throw new Error(`Dependency cycle at ${task.id}`);
    if (visited.has(task.id)) return;
    if (!stages.includes(task.stage) || !['pending', 'in-progress', 'review', 'done', 'deferred', 'cancelled'].includes(task.status)) throw new Error(`Invalid stage/status on task ${task.id}`);
    if (task.workflow !== undefined && !intents.includes(task.workflow)) throw new Error(`Invalid workflow on task ${task.id}`);
    if (task.checkpointType !== undefined && !['user', 'artifact'].includes(task.checkpointType)) throw new Error(`Invalid checkpointType on task ${task.id}`);
    for (const key of ['suggestedSkills', 'recommended_skills']) {
      if (task[key] !== undefined && (!Array.isArray(task[key]) || !task[key].every(name => typeof name === 'string'))) throw new Error(`Invalid ${key} on task ${task.id}`);
    }
    visiting.add(task.id);
    for (const id of task.dependencies) {
      if (!byId.has(id)) throw new Error(`Missing dependency ${id} of ${task.id}`);
      check(byId.get(id));
    }
    visiting.delete(task.id); visited.add(task.id);
  }
  tasks.forEach(check);
  result.currentStage = current;
  result.researchDesign = brief.projectContext?.researchType ?? brief.projectContext?.articleType ?? brief.researchType ?? brief.articleType ?? brief.pipeline?.track ?? 'unspecified';
  if (['setup', 'plan', 'sync'].includes(args.intent)) return emit({ workflow: args.intent, action: args.intent });
  if (!tasks.length) return emit({ workflow: 'plan', action: 'plan-tasks', next: 'Create tasks for the stated goal, starting with survey when choosing a topic.' });

  function evidence(task) {
    const paths = (Array.isArray(task.artifacts) ? task.artifacts : []).map(item => typeof item === 'string' ? item : item?.path).filter(item => typeof item === 'string');
    const available = paths.length > 0 && paths.every(file => {
      const absolute = path.resolve(project, file);
      return existsSync(absolute) && statSync(absolute).isFile() && statSync(absolute).size > 0;
    });
    return { paths, reviewed: available && typeof task.completionSummary === 'string' && Boolean(task.completionSummary.trim()) };
  }
  // Inspect every earlier in-scope stage before choosing a task from a later one.
  const first = args.intent === 'choose-topic' ? 0 : stages.indexOf(start);
  for (const stage of stages.slice(first, stages.indexOf(args.through) + 1)) {
    const stageTasks = tasks.filter(task => task.stage === stage && task.status !== 'cancelled');
    if (!stageTasks.length) {
      // Explicitly imported later-stage projects retain their approved starting point.
      if (stage === 'survey' && args.intent === 'choose-topic') return emit({ workflow: 'plan', action: 'plan-survey', next: 'Register and inspect existing survey evidence, or run survey before topic recommendations.' });
      continue;
    }
    for (const task of stageTasks.filter(task => task.status === 'done')) {
      const review = evidence(task);
      result.evidenceToRead.push(...review.paths);
      if (!review.reviewed) return emit({ ...taskRoute(task), action: 'verify-evidence', taskId: task.id,
        next: 'Read actual artifacts against task acceptance criteria; add artifact paths and an honest completionSummary only after checking. Reuse existing Survey/ or survey/ paths.' });
    }
    const outstanding = stageTasks.filter(task => task.status !== 'done');
    if (!outstanding.length) continue;
    const runnable = outstanding.filter(task => task.dependencies.every(id => byId.get(id).status === 'done'));
    const task = runnable.find(task => task.status === 'in-progress') ?? runnable[0];
    if (!task) return emit({ workflow: 'plan', action: 'resolve-dependencies', blockedTaskIds: outstanding.map(task => task.id) });
    for (const id of task.dependencies) {
      const dependency = byId.get(id), review = evidence(dependency);
      result.evidenceToRead.push(...review.paths);
      if (!review.reviewed) return emit({ ...taskRoute(dependency), action: 'verify-evidence', taskId: id, resumeTaskId: task.id,
        next: 'Inspect the dependency evidence before resuming this task; preserve existing progress.' });
    }
    const checkpoint = task.checkpointType === 'user' || task.assignee === 'user' || task.status === 'deferred' || (task.taskType === 'gate' && task.checkpointType !== 'artifact');
    const route = taskRoute(task);
    return emit({ ...route, workflow: checkpoint ? 'plan' : route.workflow, action: checkpoint ? 'review-checkpoint' : 'execute',
      taskId: task.id, taskTitle: task.title, nextActionPrompt: task.nextActionPrompt ?? null,
      canRecommendTopics: !checkpoint && stage === 'ideation',
      nextCheckpoint: stage === 'ideation' ? 'user-selects-direction-or-approves-protocol' : 'task-evidence-review',
      next: checkpoint ? 'Resolve this actual decision; do not re-ask for routine stage selection.' : 'Read the routed workflow and execute the task now; do not end with an unexecuted next-step promise.' });
  }
  return emit({ workflow: 'plan', action: 'review-completion-or-plan-next', next: 'Review the completed scope and plan any missing downstream tasks; do not stop just because the current task list ran out.' });
}
try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
