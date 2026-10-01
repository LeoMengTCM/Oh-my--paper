#!/usr/bin/env node
// The plugin prompts/agents are canonical; the skill bundles portable copies.
import { readFileSync, readdirSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const mode = process.argv[2] ?? 'check';
if (!['sync', 'check'].includes(mode)) throw new Error('Usage: sync-codex-workflows.mjs <sync|check>');
const drift = [];
for (const [source, target, extension] of [['prompts', 'references', '.md'], ['agents', 'roles', '.toml']]) {
  const from = path.join(root, 'plugins/oh-my-paper-codex', source);
  const to = path.join(root, 'skills/omp', target);
  const names = readdirSync(from).filter(name => name.endsWith(extension));
  for (const name of names) {
    const content = readFileSync(path.join(from, name), 'utf8');
    const output = path.join(to, name);
    if (mode === 'sync') {
      mkdirSync(to, { recursive: true });
      writeFileSync(output, content);
    } else if (!existsSync(output) || readFileSync(output, 'utf8') !== content) {
      drift.push(path.relative(root, output));
    }
  }
  if (existsSync(to)) {
    for (const name of readdirSync(to).filter(name => name.endsWith(extension))) {
      if (!names.includes(name)) drift.push(`Unexpected workflow resource: ${name}`);
    }
  }
}
if (drift.length) {
  console.error(`Codex workflow resources differ; run npm run codex:sync:\n${drift.join('\n')}`);
  process.exitCode = 1;
} else console.log(`Codex workflow resources ${mode === 'sync' ? 'synced' : 'verified'} (9 workflows, 5 roles).`);
