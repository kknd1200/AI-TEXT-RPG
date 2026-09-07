import { projectUrl, publishableKey, trustedOrigin } from '../server/config.js';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  if (req.method !== 'POST') return res.status(405).json({ error: '허용되지 않은 요청이에요.' });
  if (!trustedOrigin(req)) return res.status(403).json({ error: '요청을 확인할 수 없어요.' });
  let body = req.body;
  try { if (typeof body === 'string') body = JSON.parse(body); } catch { return res.status(400).json({ error: '입력 내용을 확인해 주세요.' }); }
  if (!body || JSON.stringify(body).length > 4096) return res.status(400).json({ error: '입력 내용을 확인해 주세요.' });
  const { action, username, password, recoveryCode, newPassword } = body;
  if (!['signup', 'login', 'reset'].includes(action)) return res.status(400).json({ error: '요청을 확인해 주세요.' });
  try {
    const remote = await fetch(projectUrl() + '/functions/v1/cre-public-account', {
      method: 'POST', headers: { 'Content-Type': 'application/json', apikey: publishableKey() },
      body: JSON.stringify({ action, username, password, recoveryCode, newPassword }),
      signal: AbortSignal.timeout(25000),
    });
    return res.status(remote.status).json(await remote.json());
  } catch {
    return res.status(503).json({ error: '계정 연결이 원활하지 않아요. 잠시 후 다시 시도해 주세요.' });
  }
}
