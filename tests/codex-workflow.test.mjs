import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, existsSync, readdirSync, rmSync, lstatSync, chmodSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import test from 'node:test';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const setup = path.join(root, 'skills/omp/scripts/project.mjs');
const manager = path.join(root, 'scripts/manage-codex-plugin.mjs');
const hook = path.join(root, 'plugins/oh-my-paper-codex/scripts/codex-hook.mjs');
function temp(t) {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'omp codex test '));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}
function run(file, args = [], options = {}) {
  return spawnSync(process.execPath, [file, ...args], { encoding: 'utf8', ...options });
}
function ok(result) { assert.equal(result.status, 0, result.stderr); return result.stdout ? JSON.parse(result.stdout) : null; }
function init(project, track = 'systematic-review', file = setup) {
  return ok(run(file, ['init', '--project', project, '--topic', '干预效果 review', '--track', track]));
}
function event(project, hook_event_name, data = {}, file = hook) {
  return run(file, [], { cwd: root, input: JSON.stringify({ cwd: project, hook_event_name, ...data }) });
}

test('Codex setup supports every research track, real TOML roles and repeated initialization', t => {
  for (const track of ['ml', 'clinical', 'systematic-review', 'bioinformatics']) {
    const project = temp(t);
    writeFileSync(path.join(project, 'AGENTS.md'), '# Existing conventions\nKeep this line.\n');
    init(project, track);
    const state = ok(run(setup, ['status', '--project', project]));
    assert.equal(state.initialized, true);
    assert.equal(state.track, track);
    assert.equal(state.taskCount, 0);
    const brief = JSON.parse(readFileSync(path.join(project, '.pipeline/docs/research_brief.json')));
    assert.equal(brief.pipeline.analysisMode, ['clinical', 'systematic-review'].includes(track) ? 'confirmatory' : 'exploratory');
    assert.equal(existsSync(path.join(project, '.pipeline/docs/protocol.md')), ['clinical', 'systematic-review'].includes(track));
    assert.deepEqual(init(project, track).changed, []);
    assert.match(readFileSync(path.join(project, 'AGENTS.md'), 'utf8'), /^# Existing conventions\nKeep this line\./);
    const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
    const parsed = spawnSync(python, ['-c', 'import pathlib,sys,tomllib; files=list(pathlib.Path(sys.argv[1]).glob("*.toml")); assert len(files)==5\nfor f in files:\n d=tomllib.loads(f.read_text()); assert d["name"]==f.stem; assert isinstance(d["developer_instructions"],str); assert "model" not in d', path.join(project, '.codex/agents')], { encoding: 'utf8' });
    assert.equal(parsed.status, 0, parsed.stderr);
  }
});

test('Setup retains old tasks, approved plans, customized roles and external instructions', t => {
  const project = temp(t); init(project);
  const files = {
    '.pipeline/tasks/tasks.json': JSON.stringify({ master: { tasks: [{ id: 17, title: 'Preserved', stage: 'survey', status: 'done', dependsOn: [] }] }, metadata: 'keep' }),
    '.pipeline/docs/protocol.md': 'Existing approved protocol\n',
    '.pipeline/memory/project_truth.md': 'Existing evidence\n',
    '.codex/agents/omp-reviewer.toml': 'name = "custom-reviewer"\n',
  };
  for (const [name, contents] of Object.entries(files)) writeFileSync(path.join(project, name), contents);
  assert.deepEqual(init(project).preservedRoles, ['.codex/agents/omp-reviewer.toml']);
  for (const [name, contents] of Object.entries(files)) assert.equal(readFileSync(path.join(project, name), 'utf8'), contents);
  const before = readFileSync(path.join(project, 'AGENTS.md'), 'utf8');
  assert.equal(run(setup, ['init', '--project', project, '--topic', 'Different topic']).status, 1);
  assert.equal(readFileSync(path.join(project, 'AGENTS.md'), 'utf8'), before);
});

test('Reinitialization upgrades a previously generated role while preserving custom roles', t => {
  const project = temp(t); init(project);
  const relative = '.codex/agents/omp-paper-writer.toml';
  const configPath = path.join(project, '.pipeline/codex.json');
  const config = JSON.parse(readFileSync(configPath));
  const previousVersion = 'name = "omp-paper-writer"\ndescription = "Previous generated role"\ndeveloper_instructions = "Old workflow"\n';
  writeFileSync(path.join(project, relative), previousVersion);
  config.managedRoles[relative] = createHash('sha256').update(previousVersion).digest('hex');
  writeFileSync(configPath, JSON.stringify(config));
  const updated = init(project);
  assert.ok(updated.changed.includes(relative));
  assert.equal(readFileSync(path.join(project, relative), 'utf8'), readFileSync(path.join(root, 'skills/omp/roles/paper-writer.toml'), 'utf8'));
});

test('Conflicting tasks or malformed managed instructions fail before setup writes', t => {
  const project = temp(t);
  mkdirSync(path.join(project, '.pipeline/tasks'), { recursive: true });
  const tasks = JSON.stringify({ tasks: [], master: { tasks: [{ id: 'old', status: 'done' }] } });
  writeFileSync(path.join(project, '.pipeline/tasks/tasks.json'), tasks);
  assert.equal(run(setup, ['init', '--project', project, '--topic', 'test']).status, 1);
  assert.equal(existsSync(path.join(project, 'AGENTS.md')), false);
  assert.equal(readFileSync(path.join(project, '.pipeline/tasks/tasks.json'), 'utf8'), tasks);
  rmSync(path.join(project, '.pipeline'), { recursive: true });
  writeFileSync(path.join(project, 'AGENTS.md'), '<!-- oh-my-paper:begin -->\nBroken');
  assert.equal(run(setup, ['init', '--project', project, '--topic', 'test']).status, 1);
  assert.equal(existsSync(path.join(project, '.pipeline')), false);
});

test('Native hook envelopes restore fresh context, detect shell edits and deduplicate reports', t => {
  const project = temp(t); init(project);
  for (const topic of ['First topic', 'Updated topic']) {
    writeFileSync(path.join(project, '.pipeline/docs/research_brief.json'), JSON.stringify({ topic, currentStage: 'survey', pipeline: { track: 'systematic-review' } }));
    assert.match(ok(event(project, 'SessionStart')).hookSpecificOutput.additionalContext, new RegExp(topic));
  }
  const taskPath = path.join(project, '.pipeline/tasks/tasks.json');
  writeFileSync(taskPath, JSON.stringify({ tasks: [{ id: 's1', stage: 'survey', status: 'pending' }] }));
  assert.deepEqual(ok(event(project, 'PostToolUse', { tool_name: 'Bash' })), {});
  writeFileSync(taskPath, JSON.stringify({ tasks: [{ id: 's1', stage: 'survey', status: 'done' }] }));
  assert.equal(ok(event(project, 'PostToolUse', { tool_name: 'Bash' })).hookSpecificOutput.hookEventName, 'PostToolUse');
  assert.deepEqual(ok(event(project, 'PostToolUse', { tool_name: 'apply_patch' })), {});
  const reminders = readFileSync(path.join(project, '.pipeline/memory/orchestrator_state.md'), 'utf8');
  assert.equal((reminders.match(/所有任务已完成/g) ?? []).length, 1);
  assert.match(reminders, /仅提醒/);
  const report = { session_id: 's', turn_id: 't', last_assistant_message: '```omp_executor_report\n{"taskId":"s1","summary":"Computed","artifacts":["out.csv"]}\n```' };
  assert.deepEqual(ok(event(project, 'Stop', report)), {});
  assert.deepEqual(ok(event(project, 'Stop', report)), {});
  assert.equal((readFileSync(path.join(project, '.pipeline/memory/review_log.md'), 'utf8').match(/Executor Report/g) ?? []).length, 1);
  assert.deepEqual(JSON.parse(readFileSync(taskPath)), { tasks: [{ id: 's1', stage: 'survey', status: 'done' }] });
});

test('Hook failures are visible, pending tasks stay pending and non-project sessions stay untouched', t => {
  const project = temp(t);
  assert.deepEqual(ok(event(project, 'SessionStart')), {});
  assert.deepEqual(readdirSync(project), []);
  init(project);
  writeFileSync(path.join(project, '.pipeline/tasks/tasks.json'), '{bad');
  assert.equal(event(project, 'PostToolUse').status, 1);
  const report = { last_assistant_message: '```omp_executor_report\n{"summary":"missing task ID"}\n```' };
  assert.equal(event(project, 'SubagentStop', report).status, 1);
});

test('Hooks recover a terminated owner and never steal a live process lock', t => {
  const project = temp(t); init(project);
  const owner = spawnSync(process.execPath, ['-e', ''], { encoding: 'utf8' }).pid;
  assert.throws(() => process.kill(owner, 0), error => error.code === 'ESRCH');
  const lock = path.join(project, '.pipeline/.codex-hook-lock');
  writeFileSync(lock, String(owner));
  assert.deepEqual(ok(event(project, 'PostToolUse')), {});
  assert.equal(existsSync(lock), false);
  writeFileSync(lock, String(process.pid));
  assert.deepEqual(ok(event(project, 'PostToolUse')), {});
  assert.equal(readFileSync(lock, 'utf8'), String(process.pid));
});

test('Installed standalone bundle includes all workflows, initializes a project and preserves marketplace entries', t => {
  const home = temp(t);
  const marketplace = path.join(home, '.agents/plugins/marketplace.json');
  mkdirSync(path.dirname(marketplace), { recursive: true });
  const unrelated = { name: 'another-plugin', source: { source: 'local', path: './plugins/another' } };
  writeFileSync(marketplace, JSON.stringify({ name: 'personal', interface: { displayName: 'Mine' }, owner: 'retained', plugins: [unrelated] }));
  const plugin = path.join(home, 'custom plugins/omp');
  const args = ['--home', home, '--plugin-dir', plugin, '--skip-app-server'];
  assert.equal(run(manager, ['install', ...args]).status, 0);
  const entry = JSON.parse(readFileSync(marketplace));
  assert.equal(entry.owner, 'retained');
  assert.deepEqual(entry.plugins[0], unrelated);
  assert.equal(entry.plugins[1].source.path, './custom plugins/omp');
  assert.equal(lstatSync(path.join(plugin, 'skills')).isSymbolicLink(), false);
  assert.equal(readdirSync(path.join(plugin, 'skills/omp/references')).length, 9);
  const project = path.join(home, 'research project');
  init(project, 'systematic-review', path.join(plugin, 'skills/omp/scripts/project.mjs'));
  assert.equal(ok(run(path.join(plugin, 'skills/omp/scripts/project.mjs'), ['status', '--project', project])).initialized, true);
  assert.equal(ok(event(project, 'SessionStart', {}, path.join(plugin, 'scripts/codex-hook.mjs'))).hookSpecificOutput.hookEventName, 'SessionStart');
  assert.equal(run(manager, ['install', ...args]).status, 0);
  assert.equal(run(manager, ['uninstall', ...args]).status, 0);
  assert.equal(existsSync(plugin), false);
  assert.deepEqual(JSON.parse(readFileSync(marketplace)).plugins, [unrelated]);
  assert.equal(existsSync(path.join(project, '.pipeline/tasks/tasks.json')), true);
});

test('Installer refuses unrelated destinations and invalid marketplaces without deleting files', t => {
  const home = temp(t), plugin = path.join(home, 'plugins/oh-my-paper-codex');
  mkdirSync(plugin, { recursive: true });
  writeFileSync(path.join(plugin, 'keep.txt'), 'Keep');
  for (const action of ['install', 'uninstall']) assert.equal(run(manager, [action, '--home', home, '--skip-app-server']).status, 1);
  assert.equal(readFileSync(path.join(plugin, 'keep.txt'), 'utf8'), 'Keep');
  rmSync(plugin, { recursive: true });
  const marketplace = path.join(home, '.agents/plugins/marketplace.json');
  mkdirSync(path.dirname(marketplace), { recursive: true });
  writeFileSync(marketplace, '{bad');
  assert.equal(run(manager, ['install', '--home', home, '--skip-app-server']).status, 1);
  assert.equal(existsSync(plugin), false);
  writeFileSync(marketplace, '{"plugins":{"keep":"entry"}}');
  assert.equal(run(manager, ['install', '--home', home, '--skip-app-server']).status, 1);
  assert.equal(readFileSync(marketplace, 'utf8'), '{"plugins":{"keep":"entry"}}');
});

test('Auto-install verifies the exact marketplace entry and does not claim unconfirmed activation', t => {
  const home = temp(t), bin = path.join(home, 'bin'), log = path.join(home, 'rpc.jsonl');
  mkdirSync(bin);
  writeFileSync(path.join(bin, 'package.json'), '{"type":"module"}\n');
  const stub = path.join(bin, 'codex-stub.mjs');
  writeFileSync(stub, `#!/usr/bin/env node
import { createInterface } from 'node:readline';
import { appendFileSync } from 'node:fs';
for await (const line of createInterface({ input: process.stdin })) {
  const call = JSON.parse(line);
  appendFileSync(process.env.OMP_TEST_RPC_LOG, JSON.stringify(call) + '\\n');
  const result = call.method === 'plugin/read' ? { plugin: { summary: { id: 'exact-entry', installed: true, enabled: process.env.OMP_TEST_ENABLED === '1' } } } : {};
  console.log(JSON.stringify({ id: call.id, result }));
}
`);
  const command = path.join(bin, process.platform === 'win32' ? 'codex.cmd' : 'codex');
  if (process.platform === 'win32') writeFileSync(command, `@"${process.execPath}" "${stub}" %*\r\n`);
  else { writeFileSync(command, readFileSync(stub)); chmodSync(command, 0o755); }
  const env = { ...process.env, PATH: `${bin}${path.delimiter}${process.env.PATH}`, OMP_TEST_RPC_LOG: log, OMP_TEST_ENABLED: '0' };
  const args = ['install', '--home', home];
  const partial = run(manager, args, { env });
  assert.equal(partial.status, 0, partial.stderr);
  assert.doesNotMatch(partial.stdout, /Installed and enabled/);
  assert.match(partial.stdout, /without a verified installed\/enabled entry/);
  const complete = run(manager, args, { env: { ...env, OMP_TEST_ENABLED: '1' } });
  assert.equal(complete.status, 0, complete.stderr);
  assert.match(complete.stdout, /Installed and enabled/);
  const requests = readFileSync(log, 'utf8').trim().split('\n').map(line => JSON.parse(line));
  const reads = requests.filter(call => call.method === 'plugin/read');
  assert.equal(reads.length, 2);
  for (const call of reads) assert.deepEqual(call.params, { marketplacePath: path.join(home, '.agents/plugins/marketplace.json'), pluginName: 'oh-my-paper-codex' });
});
