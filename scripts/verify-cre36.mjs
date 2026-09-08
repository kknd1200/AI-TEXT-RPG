import { readFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const manifest = JSON.parse(readFileSync(resolve(root, 'public/assets/cre36/manifest.json'), 'utf8'));
const problems = [];
// An available release must route every absent action to the reviewed idle
// frame. The default command remains the full 288-animation completion gate.
const availableRelease = process.argv.includes('--available');
const missing = [];
let animationCount = 0;
const actions = ['idle', 'feed', 'mist', 'clean', 'play'];
const expectedIds = new Set(Array.from({ length: 36 }, (_, i) => `cre_${String(i + 1).padStart(3, '0')}`));
if (!manifest.complete && !availableRelease) problems.push('The 72-form animation set is incomplete.');
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
    if (!animation) {
      missing.push(`public/assets/cre36/${form.morphId}/${form.stage}/${action}.png`);
      if (!availableRelease || action === 'idle' || action === 'feed') problems.push(`${key}: ${action} frames are missing.`);
      continue;
    }
    if (animation.frames !== count || new Set(animation.frameSha256).size !== count || animation.row !== actions.indexOf(action) || animation.startColumn !== (form.stage === 'adult' ? 4 : 0)) problems.push(`${key}: ${action} frames or atlas coordinates are invalid.`);
    if (action !== 'idle') animationCount++;
  }
  if (!checkedSheets.has(form.sheet)) {
    checkedSheets.add(form.sheet);
    const path = resolve(root, 'public', form.sheet.replace(/^\//, ''));
    if (!existsSync(path)) problems.push(`Missing atlas: ${form.sheet}`);
    else if (createHash('sha256').update(readFileSync(path)).digest('hex') !== form.sheetSha256) problems.push(`Atlas bytes do not match the reviewed manifest: ${form.sheet}`);
  }
  const portrait = resolve(root, 'public', form.portrait.replace(/^\//, ''));
  if (!existsSync(portrait)) problems.push(`Missing portrait: ${form.portrait}`);
}
if (JSON.stringify([...missing].sort()) !== JSON.stringify([...manifest.missingFiles].sort())) problems.push('Manifest does not accurately declare all missing animations.');
let effectCount = 0;
for (const action of actions.slice(1)) {
  const present = existsSync(resolve(root, `public/assets/cre36/fx/${action}.png`));
  if (present) effectCount++;
  if (present === manifest.missingEffects.includes(action)) problems.push(`Care effect availability is incorrect: ${action}`);
  if (!present && !availableRelease) problems.push(`Missing care effect: ${action}`);
}
if (manifest.complete !== (missing.length === 0 && effectCount === 4)) problems.push('Manifest completeness flag does not match actual coverage.');
if (problems.length) {
  console.error(`Cre sprite release check blocked: ${problems.length} issues.\n${problems.slice(0, 12).join('\n')}`);
  process.exit(1);
}
console.log(`Cre sprite ${availableRelease ? 'available release' : 'full set'} check passed: 72 forms, ${animationCount}/288 body animations, ${effectCount}/4 care effects. ${missing.length} actions use idle until their artwork is ready.`);
