import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const controller = path.join(root, 'skills/omp/scripts/continuation.mjs');
const hook = process.env.OMP_HOOK_UNDER_TEST ?? path.join(root, 'plugins/oh-my-paper-codex/scripts/codex-hook.mjs');
function setup(t, tasks = [{ id: 'write', stage: 'publication', status: 'pending', workflow: 'write', dependencies: [] }]) {
  const project = mkdtempSync(path.join(os.tmpdir(), 'omp-continuation-'));
  t.after(() => rmSync(project, { recursive: true, force: true }));
  for (const dir of ['docs', 'tasks', 'memory']) mkdirSync(path.join(project, '.pipeline', dir), { recursive: true });
  writeFileSync(path.join(project, '.pipeline/docs/research_brief.json'), JSON.stringify({ currentStage: 'publication', pipeline: { startStage: 'survey' } }));
  writeFileSync(path.join(project, '.pipeline/tasks/tasks.json'), JSON.stringify({ tasks }));
  command(project, 'start', ['--objective', 'Deliver the test manuscript', '--deliverable', 'manuscript.md']);
  return project;
}
function command(project, action, rest = [], expected = 0) {
  const result = spawnSync(process.execPath, [controller, action, '--project', project, '--session-id', 'session-a', ...rest], { encoding: 'utf8' });
  assert.equal(result.status, expected, result.stderr);
  return result.status === 0 ? JSON.parse(result.stdout) : result.stderr;
}
function stop(project, turn = '1', session = 'session-a') {
  const result = spawnSync(process.execPath, [hook], { cwd: project, input: JSON.stringify({ hook_event_name: 'Stop', session_id: session, turn_id: turn, cwd: project, last_assistant_message: `Work update ${turn}` }), encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}
function complete(project) {
  writeFileSync(path.join(project, 'manuscript.md'), '# Fictional test manuscript\n');
  writeFileSync(path.join(project, '.pipeline/tasks/tasks.json'), JSON.stringify({ tasks: [{ id: 'write', stage: 'publication', status: 'done', workflow: 'write', dependencies: [], artifacts: ['manuscript.md'], completionSummary: 'Verified test manuscript.' }] }));
}
test('提前收尾由 Stop 自动要求续行，不改任务或干扰其他会话', t => {
  const p = setup(t), before = readFileSync(path.join(p, '.pipeline/tasks/tasks.json'), 'utf8');
  assert.equal(stop(p).decision, 'block');
  assert.match(stop(p).reason, /Continue task write/);
  assert.deepEqual(stop(p, '1', 'another-session'), {});
  assert.equal(readFileSync(path.join(p, '.pipeline/tasks/tasks.json'), 'utf8'), before);
});
test('真实用户任务是合法停点，不能自动代做用户重绘', t => {
  const p = setup(t, [{ id: 'draw', stage: 'publication', status: 'pending', assignee: 'user', dependencies: [] }]);
  assert.deepEqual(stop(p), {});
  assert.equal(command(p, 'status').lastCheckpoint.taskId, 'draw');
});
test('明确暂停或外部阻塞可停，恢复后继续检查', t => {
  const p = setup(t);
  command(p, 'wait', ['--kind', 'external-blocker', '--reason', 'Required source file is not available']);
  assert.deepEqual(stop(p), {});
  command(p, 'resume'); assert.equal(stop(p).decision, 'block');
  command(p, 'pause', ['--reason', 'User requested a pause']);
  assert.deepEqual(stop(p), {});
});
test('不能靠结束声明越过未完成任务或缺失交付物', t => {
  const p = setup(t);
  command(p, 'finish', ['--summary', 'Not actually done'], 1);
  complete(p); rmSync(path.join(p, 'manuscript.md'));
  assert.equal(stop(p).decision, 'block');
  command(p, 'finish', ['--summary', 'Still missing'], 1);
});
test('完整产物和最终审查确认后结束，不进入无授权的 promotion', t => {
  const p = setup(t); complete(p);
  const f = path.join(p, '.pipeline/tasks/tasks.json'), data = JSON.parse(readFileSync(f));
  data.tasks.push({ id: 'slides', stage: 'promotion', status: 'pending', dependencies: ['write'] });
  writeFileSync(f, JSON.stringify(data));
  assert.equal(stop(p).decision, 'block');
  command(p, 'finish', ['--summary', 'Current manuscript and all in-scope checks verified']);
  assert.equal(command(p, 'status').status, 'complete');
  assert.deepEqual(stop(p, '2'), {});
});
test('重复投递不累加失败，连续无进展显式报停而不无限循环', t => {
  const p = setup(t);
  for (let i = 0; i < 4; i++) assert.equal(stop(p, 'same').decision, 'block');
  assert.equal(command(p, 'status').unchangedStops, 0);
  assert.equal(stop(p, 'second').decision, 'block');
  const third = stop(p, 'third');
  assert.match(third.systemMessage, /stalled/);
  assert.equal(command(p, 'status').status, 'stalled');
});
test('跨阶段有真实任务更新时自动继续，直到明确最终交付检查', t => {
  const stages = ['survey', 'ideation', 'experiment', 'publication'];
  const tasks = stages.map((stage, i) => ({ id: stage, stage, status: 'pending', dependencies: i ? [stages[i - 1]] : [] }));
  const p = setup(t, tasks);
  for (const task of tasks) {
    assert.equal(stop(p, task.stage).decision, 'block');
    writeFileSync(path.join(p, `${task.stage}.md`), `# Test artifact ${task.stage}\n`);
    Object.assign(task, { status: 'done', artifacts: [`${task.stage}.md`], completionSummary: `Checked ${task.stage}` });
    writeFileSync(path.join(p, '.pipeline/tasks/tasks.json'), JSON.stringify({ tasks }));
  }
  writeFileSync(path.join(p, 'manuscript.md'), '# Test delivery\n');
  assert.equal(stop(p, 'audit').decision, 'block');
  command(p, 'finish', ['--summary', 'All four in-scope stages and final delivery reviewed']);
  assert.deepEqual(stop(p, 'delivered'), {});
});
