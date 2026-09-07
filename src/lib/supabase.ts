import { createClient } from '@supabase/supabase-js';
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL || 'https://buapfwbukpremwaksahr.supabase.co',
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || 'sb_publishable_BJOfOKFAjZBiuD2oywCglQ_iO4aAyuI',
  { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false } },
);

export async function accountName(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) return null;
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) throw new Error('로그인 상태를 확인하지 못했어요. 다시 로그인해 주세요.');
  const { data, error: profileError } = await supabase.from('cre_accounts').select('username').eq('id', user.id).maybeSingle();
  if (profileError) throw new Error('계정 정보를 불러오지 못했어요. 다시 시도해 주세요.');
  if (!data) throw new Error('크레키우기 계정이 필요해요. 아이디로 로그인해 주세요.');
  return data.username;
}

export async function petFetch(init?: RequestInit) {
  const { data: { session }, error } = await supabase.auth.getSession();
  if (error || !session) return Response.json({ error: '로그인 후 크레를 만날 수 있어요.' }, { status: 401 });
  const headers = new Headers(init?.headers);
  headers.set('Authorization', 'Bearer ' + session.access_token);
  return fetch('/api/pet', { ...init, headers, cache: 'no-store', signal: AbortSignal.timeout(30000) });
}
