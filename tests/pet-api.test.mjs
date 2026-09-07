import test from 'node:test';
import assert from 'node:assert/strict';
import { createPetHandler } from '../supabase/functions/_shared/pet-handler.ts';

function fixture() {
  const saves = new Map();
  let now = 200000;
  const handler = createPetHandler({
    authenticate: async request => ({ 'Bearer test-a': 'a', 'Bearer test-b': 'b' })[request.headers.get('authorization')] ?? null,
    ensure: async (id, state) => { if (!saves.has(id)) saves.set(id, { state: structuredClone(state), revision: 0 }); },
    read: async id => structuredClone(saves.get(id)),
    write: async (id, revision, state) => {
      if (saves.get(id)?.revision !== revision) return false;
      saves.set(id, { state: structuredClone(state), revision: revision + 1 }); return true;
    },
    now: () => now, roll: () => .999,
  });
  const request = async (token = 'test-a', body) => {
    const response = await handler(new Request('https://example.test/pet', {
      method: body ? 'POST' : 'GET', headers: { authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }));
    return { status: response.status, ...await response.json() };
  };
  return { request, saves, time: ms => { now += ms; } };
}

test('authenticated load, care, hatch, rename, save and a fresh session retain one result', async () => {
  const f = fixture();
  let r = await f.request(); assert.equal(r.pet.phase, 'egg');
  f.time(4000);
  r = await f.request('test-a', { action: 'warm', revision: r.revision }); assert.equal(r.pet.careCount, 1);
  f.time(180000);
  r = await f.request('test-a', { action: 'hatch', revision: r.revision, roll: 0, morphId: 'patternless' });
  assert.equal(r.pet.morphId, 'axanthic'); const creature = r.pet.id;
  r = await f.request('test-a', { action: 'rename', name: '나의 크레', revision: r.revision });
  f.time(4000);
  r = await f.request('test-a', { action: 'feed', revision: r.revision }); assert(r.pet.xp >= 10);
  r = await f.request('test-a', { action: 'save', revision: r.revision });
  const reloaded = await f.request();
  assert.equal(reloaded.pet.id, creature); assert.equal(reloaded.pet.name, '나의 크레');
  assert.equal(reloaded.pet.morphId, 'axanthic'); assert.equal(reloaded.revision, r.revision);
});

test('unverified callers are rejected and supplied owner/state cannot read or overwrite another player', async () => {
  const f = fixture();
  assert.equal((await f.request('forged')).status, 401);
  await f.request(); await f.request('test-b');
  await f.request('test-a', { action: 'rename', revision: 0, name: 'A의 크레', owner: 'b', state: { xp: 9999 } });
  assert.equal((await f.request('test-b')).pet.name, '새로운 알');
  assert.equal((await f.request()).pet.xp, 0);
});

test('simultaneous hatch requests commit once; stale retries return the stored result', async () => {
  const f = fixture(); await f.request(); f.time(180000);
  const results = await Promise.all([
    f.request('test-a', { action: 'hatch', revision: 0 }),
    f.request('test-a', { action: 'hatch', revision: 0 }),
  ]);
  assert.deepEqual(results.map(r => r.status).sort(), [200, 409]);
  assert.equal(results[0].pet.id, results[1].pet.id);
  assert.equal(results[0].pet.morphId, results[1].pet.morphId);
  assert.equal(f.saves.get('a').revision, 1);
  assert.equal((await f.request('test-a', { action: 'save', revision: -1 })).status, 400);
});
