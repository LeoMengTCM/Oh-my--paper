import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const router = path.join(root, 'skills/omp/scripts/workflow.mjs');
function fixture(t, tasks) {
  const project = mkdtempSync(path.join(os.tmpdir(), 'omp-routing-'));
  t.after(() => rmSync(project, { recursive: true, force: true }));
  mkdirSync(path.join(project, '.pipeline/docs'), { recursive: true });
  mkdirSync(path.join(project, '.pipeline/tasks'), { recursive: true });
  writeFileSync(path.join(project, '.pipeline/docs/research_brief.json'), JSON.stringify({ topic: '肿瘤领域叙述性综述选题', currentStage: 'survey', pipeline: { startStage: 'survey' } }));
  writeFileSync(path.join(project, '.pipeline/tasks/tasks.json'), JSON.stringify(tasks));
  return project;
}
function route(project, intent = 'continue', extra = []) {
  const result = spawnSync(process.execPath, [router, '--project', project, '--intent', intent, ...extra], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}
const pending = [
  { id: 'survey', stage: 'survey', title: '文献全景与已有综述重合', status: 'pending', dependencies: [] },
  { id: 'ideas', stage: 'ideation', title: '选题比较', status: 'pending', dependencies: ['survey'] },
];
test('用户说从肿瘤领域选题，未做 survey 时必须先调研', t => {
  const project = fixture(t, { tasks: pending });
  const before = readFileSync(path.join(project, '.pipeline/tasks/tasks.json'), 'utf8');
  const result = route(project, 'choose-topic');
  assert.equal(result.workflow, 'survey');
  assert.equal(result.taskId, 'survey');
  assert.equal(result.canRecommendTopics, false);
  assert.equal(readFileSync(path.join(project, '.pipeline/tasks/tasks.json'), 'utf8'), before);
});
test('只有 done 和检索数量，缺少核查产物时不能转入选题', t => {
  const project = fixture(t, { tasks: [{ ...pending[0], status: 'done' }, pending[1]] });
  const result = route(project, 'choose-topic');
  assert.equal(result.workflow, 'survey');
  assert.equal(result.action, 'verify-evidence');
  assert.equal(result.canRecommendTopics, false);
});
test('survey 已核查后，继续会直接衔接选题比较并保留用户选题决定', t => {
  const project = fixture(t, { tasks: [{ ...pending[0], status: 'done', artifacts: ['Survey/survey_report.md', 'Survey/paper_bank.json'], completionSummary: '已核读报告和书目，比较已有综述、原始证据、全文阅读范围和未决问题。' }, pending[1]] });
  mkdirSync(path.join(project, 'Survey'));
  writeFileSync(path.join(project, 'Survey/survey_report.md'), '# 软件测试材料\n已核查调研依据与不确定性。');
  writeFileSync(path.join(project, 'Survey/paper_bank.json'), '{"purpose":"software_validation"}');
  const result = route(project);
  assert.equal(result.workflow, 'ideate');
  assert.equal(result.taskId, 'ideas');
  assert.equal(result.nextCheckpoint, 'user-selects-direction-or-approves-protocol');
  assert.equal(result.requiresStageMenu, false);
  assert.ok(result.evidenceToRead.includes('Survey/survey_report.md'));
});
test('旧任务格式、ID 类型和已有后期起点保留', t => {
  const project = fixture(t, { master: { tasks: [{ id: 19, stage: 'publication', status: 'pending', dependsOn: [] }] } });
  writeFileSync(path.join(project, '.pipeline/docs/research_brief.json'), JSON.stringify({ currentStage: 'publication', pipeline: { startStage: 'publication' } }));
  assert.equal(route(project).workflow, 'write');
  assert.equal(route(project).taskId, 19);
});
test('明确的一次性任务不被强迫跑整条流水线', t => {
  const project = fixture(t, { tasks: pending });
  assert.equal(route(project, 'review', ['--standalone']).workflow, 'review');
});
test('空任务表需要规划，不等于 survey 已完成', t => {
  const project = fixture(t, { tasks: [] });
  const result = route(project, 'choose-topic');
  assert.equal(result.workflow, 'plan');
  assert.equal(result.canRecommendTopics, false);
});
test('缺失依赖不能当作已经满足', t => {
  const project = fixture(t, { tasks: [{ ...pending[0], dependencies: ['missing'] }] });
  const result = spawnSync(process.execPath, [router, '--project', project], { encoding: 'utf8' });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /missing/);
});

function publicationFixture(t, next) {
  const project = fixture(t, { tasks: [
    { id: 'draft', stage: 'publication', status: 'done', dependencies: [], artifacts: ['draft.md'], completionSummary: '已核对当前稿件与证据。' },
    { id: 'next', stage: 'publication', status: 'pending', dependencies: ['draft'], ...next },
  ] });
  writeFileSync(path.join(project, 'draft.md'), '# Software validation draft\n');
  writeFileSync(path.join(project, '.pipeline/docs/research_brief.json'), JSON.stringify({ currentStage: 'publication', pipeline: { startStage: 'publication', track: 'ml' }, projectContext: { articleType: 'narrative-review' } }));
  return project;
}
test('写作完成后按任务进入同行评审，而不是再次写作', t => {
  const project = publicationFixture(t, { suggestedSkills: ['paper-reviewer'], taskType: 'analysis' });
  assert.equal(route(project).workflow, 'review');
});
test('引用核验与投稿检查走各自的处理技能', t => {
  for (const skill of ['integrity-auditor', 'submission-checker']) {
    const project = publicationFixture(t, { suggestedSkills: [skill] });
    const result = route(project);
    assert.equal(result.workflow, 'review');
    assert.equal(result.skill, skill);
  }
});
test('返修任务进入写作，复审任务返回评审', t => {
  const project = publicationFixture(t, { workflow: 'write', suggestedSkills: ['paper-writing'], title: '按已核实评审意见返修' });
  assert.equal(route(project).workflow, 'write');
  const tasksFile = path.join(project, '.pipeline/tasks/tasks.json');
  const data = JSON.parse(readFileSync(tasksFile));
  data.tasks[1] = { ...data.tasks[1], workflow: 'review', suggestedSkills: ['paper-reviewer'], title: '核查返修是否解决问题' };
  writeFileSync(tasksFile, JSON.stringify(data));
  assert.equal(route(project).workflow, 'review');
});
test('自动产物检查与研究者批准分别处理', t => {
  const automatic = publicationFixture(t, { taskType: 'gate', checkpointType: 'artifact', suggestedSkills: ['submission-checker'] });
  assert.equal(route(automatic).workflow, 'review');
  assert.equal(route(automatic).action, 'execute');
  const human = publicationFixture(t, { taskType: 'gate', checkpointType: 'user', suggestedSkills: ['submission-checker'] });
  assert.equal(route(human).action, 'review-checkpoint');
});
test('publication 中待审的正文交给评审，不要求重复阶段选择', t => {
  const project = publicationFixture(t, { status: 'review', workflow: 'write' });
  assert.equal(route(project).workflow, 'review');
  assert.equal(route(project).requiresStageMenu, false);
});
test('兼容值 ml 不覆盖明确的叙述性综述类型', t => {
  const project = publicationFixture(t, { workflow: 'write' });
  assert.equal(route(project).researchDesign, 'narrative-review');
});
test('审稿退回补证时也核对后期阶段的依赖报告', t => {
  const project = fixture(t, { tasks: [
    { id: 'evidence-fix', stage: 'experiment', status: 'pending', workflow: 'experiment', dependencies: ['review'] },
    { id: 'review', stage: 'publication', status: 'done', workflow: 'review', dependencies: [], artifacts: ['missing-review.md'], completionSummary: '此前评审完成。' },
  ] });
  const result = route(project);
  assert.equal(result.workflow, 'review');
  assert.equal(result.action, 'verify-evidence');
  assert.equal(result.resumeTaskId, 'evidence-fix');
});
