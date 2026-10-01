#!/usr/bin/env node
// Optional, read-only check against the installed Codex app-server. No model turn.
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import os from 'node:os';
import { readdirSync, readFileSync } from 'node:fs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const checkInstalled = process.argv[2] === '--installed';
const requireHooks = process.argv.includes('--require-hooks');
const projectIndex = process.argv.indexOf('--project');
const project = projectIndex >= 0 ? path.resolve(process.argv[projectIndex + 1]) : os.homedir();
const marketplacePath = checkInstalled ? path.join(os.homedir(), '.agents/plugins/marketplace.json')
  : path.resolve(process.argv[2] ?? path.join(root, '.agents/plugins/marketplace.json'));
const child = spawn(process.platform === 'win32' ? 'codex.cmd' : 'codex', ['app-server'], { stdio: ['pipe', 'pipe', 'pipe'], shell: process.platform === 'win32' });
const pending = new Map();
let nextId = 0, buffer = '';
function rejectAll(error) { for (const call of pending.values()) call.reject(error); pending.clear(); }
child.on('error', rejectAll);
child.on('exit', () => rejectAll(new Error('Codex app-server exited before replying')));
child.stdin.on('error', rejectAll);
child.stderr.resume();
child.stdout.on('data', data => {
  buffer += data.toString();
  while (buffer.includes('\n')) {
    const split = buffer.indexOf('\n'), line = buffer.slice(0, split);
    buffer = buffer.slice(split + 1);
    let message;
    try { message = JSON.parse(line); } catch { continue; }
    const call = pending.get(message.id);
    if (!call) continue;
    pending.delete(message.id);
    if (message.error) call.reject(new Error(message.error.message));
    else call.resolve(message.result);
  }
});
function request(method, params) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Timed out: ${method}`)); }, 20000);
    pending.set(id, { resolve: value => { clearTimeout(timer); resolve(value); }, reject: error => { clearTimeout(timer); reject(error); } });
    child.stdin.write(JSON.stringify({ id, method, params }) + '\n');
  });
}
try {
  await request('initialize', { clientInfo: { name: 'omp-runtime-check', version: '1.0' }, capabilities: { experimentalApi: true } });
  const { plugin } = await request('plugin/read', { marketplacePath, pluginName: 'oh-my-paper-codex' });
  const expected = [];
  function scan(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) scan(file);
      else if (entry.name === 'SKILL.md') {
        const name = readFileSync(file, 'utf8').match(/^name:\s*(.+)$/m)?.[1].replace(/^["']|["']$/g, '');
        if (name) expected.push(`oh-my-paper-codex:${name}`);
      }
    }
  }
  scan(path.join(root, 'skills'));
  const actual = plugin.skills.map(skill => skill.name);
  const missing = expected.filter(name => !actual.includes(name));
  if (missing.length) throw new Error(`Codex did not discover bundled skills: ${missing.join(', ')}`);
  const hooks = plugin.hooks.map(hook => hook.eventName).sort();
  if (JSON.stringify(hooks) !== JSON.stringify(['postToolUse', 'sessionStart', 'stop', 'subagentStop'].sort())) throw new Error('Codex did not discover the four lifecycle hooks');
  let hookReadiness = null;
  if (checkInstalled) {
    if (!plugin.summary.installed || !plugin.summary.enabled) throw new Error('Personal Oh My Paper plugin is not installed and enabled');
    const listing = await request('skills/list', { cwds: [os.homedir()], forceReload: true });
    const active = listing.data.flatMap(entry => entry.skills ?? []).filter(skill => skill.name === 'oh-my-paper-codex:omp' && skill.enabled);
    if (!active.length) throw new Error('The active session skill loader does not expose the omp entrypoint');
    const resources = ['SKILL.md', 'scripts/workflow.mjs', 'scripts/project.mjs', 'scripts/continuation.mjs',
      ...readdirSync(path.join(root, 'skills/omp/references')).filter(name => name.endsWith('.md')).map(name => `references/${name}`),
      ...readdirSync(path.join(root, 'skills/omp/roles')).filter(name => name.endsWith('.toml')).map(name => `roles/${name}`)];
    for (const skill of active) {
      for (const relative of resources) {
        if (readFileSync(path.join(path.dirname(skill.path), relative), 'utf8') !== readFileSync(path.join(root, 'skills/omp', relative), 'utf8')) {
          throw new Error(`Installed omp content is stale: ${relative}. Reinstall and start a new session.`);
        }
      }
      const cachedRoot = path.resolve(path.dirname(skill.path), '../..');
      if (readFileSync(path.join(cachedRoot, 'scripts/codex-hook.mjs'), 'utf8') !== readFileSync(path.join(root, 'plugins/oh-my-paper-codex/scripts/codex-hook.mjs'), 'utf8')) throw new Error('Installed hook implementation is stale');
    }
    const observed = await request('hooks/list', { cwds: [project] });
    hookReadiness = observed.data.flatMap(entry => entry.hooks ?? [])
      .filter(hook => hook.pluginId === plugin.summary.id)
      .map(hook => ({ event: hook.eventName, enabled: hook.enabled, trustStatus: hook.trustStatus, ready: hook.enabled && (hook.isManaged || hook.trustStatus === 'trusted') }));
  }
  const automaticContinuationReady = Boolean(hookReadiness?.some(hook => hook.event === 'stop' && hook.ready));
  console.log(JSON.stringify({ verified: true, installedContentVerified: checkInstalled, discoveredSkills: actual.length, entrypoint: 'oh-my-paper-codex:omp', hooks, hookReadiness, automaticContinuationReady, modelTurnsStarted: 0 }, null, 2));
  if (requireHooks && !automaticContinuationReady) {
    console.error('OMP Stop hook is not active. Review and trust the Oh My Paper definitions in Codex /hooks; content installation alone does not enable automatic continuation.');
    process.exitCode = 2;
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  rejectAll(new Error('Runtime check finished'));
  child.kill();
}
