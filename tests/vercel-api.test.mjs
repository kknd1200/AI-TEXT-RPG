import test from 'node:test';
import assert from 'node:assert/strict';
import account from '../api/cre-account.js';
import pet from '../api/pet.js';

function response() {
  return { headers: {}, code: 200, setHeader(k, v) { this.headers[k] = v; }, status(c) { this.code = c; return this; }, json(v) { this.body = v; return this; } };
}
test('Vercel account proxy needs only a publishable key and passes credentials to the account service', async t => {
  let posted;
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert(url.endsWith('/functions/v1/cre-public-account'));
    assert.equal(init.headers['x-cre-server-key'], undefined);
    posted = JSON.parse(init.body);
    return Response.json({ access_token: 'test-access', refresh_token: 'test-refresh', recovery_code: 'EXAMPLE12345' });
  });
  const res = response();
  await account({ method: 'POST', headers: { host: 'game.vercel.app', origin: 'https://game.vercel.app', 'x-forwarded-for': '192.0.2.8' }, body: { action: 'signup', username: 'player', password: 'TestPass123', clientIp: 'forged' } }, res);
  assert.equal(res.code, 200); assert.equal(posted.clientIp, undefined);
  assert.equal(res.body.recovery_code, 'EXAMPLE12345'); assert(!JSON.stringify(res.body).includes('test-server-key'));
  assert.match(res.headers['Cache-Control'], /no-store/);
});
test('Vercel write endpoints reject other origins and pet requests require bearer authentication', async () => {
  let res = response();
  await account({ method: 'POST', headers: { host: 'game.vercel.app', origin: 'https://other.test' }, body: {} }, res);
  assert.equal(res.code, 403);
  res = response(); await pet({ method: 'GET', headers: {} }, res); assert.equal(res.code, 401);
  res = response(); await pet({ method: 'POST', headers: { host: 'game.vercel.app', authorization: 'Bearer test', origin: 'https://other.test' }, body: {} }, res); assert.equal(res.code, 403);
});
