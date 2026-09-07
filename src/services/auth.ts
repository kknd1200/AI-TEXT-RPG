import { supabase, accountName } from '@/lib/supabase';

export type AccountResult = { recovery_code?: string; message?: string };
export async function accountRequest(payload: Record<string, unknown>): Promise<AccountResult> {
  const response = await fetch('/api/cre-account', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload), signal: AbortSignal.timeout(30000),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || !body) throw new Error(body?.error || '계정에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.');
  if (payload.action === 'reset') return body;
  if (typeof body.access_token !== 'string' || typeof body.refresh_token !== 'string') throw new Error('로그인 응답을 확인하지 못했어요.');
  const { error } = await supabase.auth.setSession({ access_token: body.access_token, refresh_token: body.refresh_token });
  if (error) throw new Error('로그인을 유지하지 못했어요. 새 창에서 다시 로그인해 주세요.');
  if (!await accountName()) throw new Error('로그인 상태를 확인하지 못했어요.');
  return body;
}
