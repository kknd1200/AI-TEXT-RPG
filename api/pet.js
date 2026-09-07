import { projectUrl, publishableKey, trustedOrigin } from '../server/config.js';

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'private, no-store');
  if (!['GET', 'POST'].includes(req.method)) return res.status(405).json({ error: '허용되지 않은 요청이에요.' });
  const authorization = req.headers.authorization;
  if (typeof authorization !== 'string' || !authorization.startsWith('Bearer ') || authorization.length > 8192) {
    return res.status(401).json({ error: '로그인 후 크레를 만날 수 있어요.' });
  }
  if (req.method === 'POST' && !trustedOrigin(req)) return res.status(403).json({ error: '요청을 확인할 수 없어요.' });
  const body = req.method === 'POST' ? typeof req.body === 'string' ? req.body : JSON.stringify(req.body) : undefined;
  if (body && Buffer.byteLength(body) > 4096) return res.status(413).json({ error: '입력 내용이 너무 길어요.' });
  try {
    const response = await fetch(projectUrl() + '/functions/v1/cre-terrarium', {
      method: req.method, headers: { authorization, apikey: publishableKey(), 'Content-Type': 'application/json' },
      body, signal: AbortSignal.timeout(25000),
    });
    return res.status(response.status).json(await response.json());
  } catch {
    return res.status(503).json({ error: '크레의 기록을 연결하지 못했어요. 다시 불러와 주세요.' });
  }
}
