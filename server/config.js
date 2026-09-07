export const projectUrl = () => (process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL || 'https://buapfwbukpremwaksahr.supabase.co').replace(/\/$/, '');
export const publishableKey = () => process.env.SUPABASE_PUBLISHABLE_KEY || process.env.VITE_SUPABASE_PUBLISHABLE_KEY || 'sb_publishable_BJOfOKFAjZBiuD2oywCglQ_iO4aAyuI';

export function trustedOrigin(req) {
  const origin = req.headers.origin;
  if (!origin) return false;
  const hosts = [process.env.VERCEL_URL, process.env.VERCEL_PROJECT_PRODUCTION_URL, process.env.APP_ORIGIN]
    .filter(Boolean).map(value => new URL(value.startsWith('http') ? value : 'https://' + value).origin);
  // On Vercel the request Host is routed by the platform to this deployment.
  const host = req.headers.host;
  if (host && /^[a-zA-Z0-9.-]+(?::[0-9]+)?$/.test(host)) hosts.push('https://' + host);
  if (process.env.NODE_ENV !== 'production' && host && /^(localhost|127\.0\.0\.1)(:\d+)?$/.test(host)) hosts.push('http://' + host);
  return hosts.includes(origin);
}
