import assert from 'node:assert/strict';
import test from 'node:test';
import { existsSync, readFileSync } from 'node:fs';
import { spriteAsset, spriteCell, spriteStage, spriteEffect, SPRITE_ACTIONS } from '../src/lib/sprites.ts';

const manifest = JSON.parse(readFileSync(new URL('../public/assets/cre36/manifest.json', import.meta.url)));

test('every morph, growth stage and care action resolves to an existing reviewed frame', () => {
  for (const form of manifest.forms) {
    for (const xp of form.stage === 'adult' ? [240, 500] : [0, 79, 80, 239]) {
      const creature = { phase: 'hatched', morphId: form.morphId, xp };
      for (const action of SPRITE_ACTIONS) {
        const asset = spriteAsset(creature, action);
        const animation = form.animations[asset.action];
        assert.ok(animation, `${form.id}/${action} must never select an empty atlas row`);
        assert.equal(asset.url, form.sheet);
        assert.ok(existsSync(new URL('../public' + asset.url, import.meta.url)));
        if (!form.animations[action]) assert.equal(asset.action, 'idle');
        for (let frame = 0; frame < 4; frame++) {
          const cell = spriteCell(spriteStage(xp), asset.action, frame);
          assert.equal(cell.row, animation.row);
          assert.ok(cell.col >= animation.startColumn && cell.col < animation.startColumn + animation.frames);
        }
      }
    }
  }
});

test('missing effects never produce broken requests; eggs and legacy tiger keep their own art', () => {
  for (const action of SPRITE_ACTIONS) {
    const effect = spriteEffect(action);
    if (effect) assert.ok(existsSync(new URL('../public' + effect, import.meta.url)));
    if (action === 'idle' || manifest.missingEffects.includes(action)) assert.equal(effect, null);
  }
  assert.deepEqual(spriteAsset({ phase: 'egg', xp: 0 }, 'feed'), { url: '/assets/morphs/egg/frame-0.png', atlas: false, action: 'idle' });
  assert.deepEqual(spriteAsset({ phase: 'hatched', morphId: 'tiger', xp: 300 }, 'play'), { url: '/assets/morphs/tiger/frame-0.png', atlas: false, action: 'idle' });
  assert.equal(spriteAsset({ phase: 'hatched', morphId: 'patternless', xp: 0 }).url, '/assets/cre36/atlases/cre_009.png');
});
