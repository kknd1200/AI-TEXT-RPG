import { readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const manifest = JSON.parse(readFileSync(resolve(root, 'public/assets/cre36/manifest.json'), 'utf8'));
const problems = [];
const actions = ['idle', 'feed', 'mist', 'clean', 'play'];
const expectedIds = new Set(Array.from({ length: 36 }, (_, i) => `cre_${String(i + 1).padStart(3, '0')}`));
if (!manifest.complete) problems.push('The 72-form animation set is incomplete.');
if (manifest.forms.length !== 72) problems.push(`Expected 72 forms; found ${manifest.forms.length}.`);
const seen = new Set();
const checkedSheets = new Set();
for (const form of manifest.forms) {
  const key = `${form.morphId}-${form.stage}`;
  if (seen.has(key) || !expectedIds.has(form.morphId) || !['baby', 'adult'].includes(form.stage)) problems.push(`Invalid form: ${key}`);
  seen.add(key);
  for (const action of actions) {
    const animation = form.animations[action];
    const count = action === 'idle' ? 1 : 4;
    if (!animation || animation.frames !== count || new Set(animation.frameSha256).size !== count) problems.push(`${key}: ${action} frames are missing or duplicated.`);
  }
  if (!checkedSheets.has(form.sheet)) {
    checkedSheets.add(form.sheet);
    const path = resolve(root, 'public', form.sheet.replace(/^\//, ''));
    if (!existsSync(path)) problems.push(`Missing atlas: ${form.sheet}`);
    else if (createHash('sha256').update(readFileSync(path)).digest('hex') !== form.sheetSha256) problems.push(`Atlas bytes do not match the reviewed manifest: ${form.sheet}`);
  }
}
for (const action of actions.slice(1)) {
  if (!existsSync(resolve(root, `public/assets/cre36/fx/${action}.png`))) problems.push(`Missing care effect: ${action}`);
}
if (problems.length) {
  console.error(`Cre sprite release check blocked: ${problems.length} issues.\n${problems.slice(0, 12).join('\n')}`);
  process.exit(1);
}
console.log('Cre sprite release check passed: 72 forms, 288 body animations, 4 care effects.');
