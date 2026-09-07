import { createClient } from 'npm:@supabase/supabase-js@2.115.0';
import { normalizeUsername, validateCredentials } from '../_shared/credentials.ts';

const projectUrl = Deno.env.get('SUPABASE_URL')!;
const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const anonKey = Deno.env.get('SUPABASE_ANON_KEY')!;
const options = { auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false } };
const reply = (value: unknown, status = 200) => Response.json(value, { status, headers: { 'Cache-Control': 'no-store' } });
async function digest(value: string) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))))
    .map(byte => byte.toString(16).padStart(2, '0')).join('');
}
function createRecoveryCode() {
  const alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const bytes=crypto.getRandomValues(new Uint8Array(12));
  return Array.from(bytes,b=>alphabet[b%alphabet.length]).join('');
}
Deno.serve(async (request: Request) => {
  if (request.method !== 'POST') return reply({ error: '허용되지 않은 요청이에요.' }, 405);
  try {
    // Signup is public; login verifies the password with Supabase Auth and reset verifies the recovery code.
    // Only these three account operations are exposed. Admin keys stay inside this function.
    const admin = createClient(projectUrl, serviceKey, options);
    const raw = await request.text();
    if (raw.length > 4096) return reply({ error: '입력 내용이 너무 길어요.' }, 413);
    let body: Record<string, unknown>;
    try { body = JSON.parse(raw); } catch { return reply({ error: '입력 내용을 확인해 주세요.' }, 400); }
    const action=String(body.action||'');
    if (!['signup','login','reset'].includes(action)) return reply({ error: '요청을 확인해 주세요.' }, 400);
    const username = normalizeUsername(body.username);
    const forwarded = request.headers.get('x-forwarded-for')?.split(',').at(-1)?.trim();
    const ip = (request.headers.get('cf-connecting-ip') || request.headers.get('x-real-ip') || forwarded || 'unknown').slice(0,80);

    const limits = action==='signup' ? [5,15] : action==='reset' ? [6,20] : [12,80];
    for (const [bucket, limit] of [
      ['user:' + await digest(username), limits[0]],
      ['ip:' + await digest(ip), limits[1]],
    ] as const) {
      const { data: allowed, error } = await admin.rpc('cre_take_auth_attempt', {
        p_bucket: action + ':' + bucket, p_limit: limit, p_window_seconds: 600,
      });
      if (error) return reply({ error: '계정 연결이 원활하지 않아요.' }, 503);
      if (!allowed) return reply({ error: '시도가 너무 많아요. 10분 뒤 다시 시도해 주세요.' }, 429);
    }

    const { data: existing, error: lookupError } = await admin.from('cre_accounts')
      .select('id,username').eq('username', username).maybeSingle();
    if (lookupError) return reply({ error: '계정을 확인하지 못했어요.' }, 503);

    if(action==='reset'){
      const newPassword=body.newPassword;
      const invalid=validateCredentials(username,newPassword,true);
      if(invalid) return reply({error:invalid},400);
      const recoveryCode=typeof body.recoveryCode==='string'?body.recoveryCode.trim().toUpperCase():'';
      if(!existing || !/^[A-Z0-9]{12}$/.test(recoveryCode)) return reply({error:'아이디 또는 복구 코드가 맞지 않아요.'},400);
      const suppliedHash=await digest(username+':'+recoveryCode);
      const {data:rec,error:recErr}=await admin.from('cre_account_recovery')
        .select('user_id,recovery_hash,failed_attempts,locked_until').eq('username',username).maybeSingle();
      if(recErr) return reply({error:'비밀번호 재설정을 처리하지 못했어요.'},503);
      if(rec?.locked_until && new Date(rec.locked_until).getTime()>Date.now()) return reply({error:'복구 코드 입력을 여러 번 실패했습니다. 15분 뒤 다시 시도해 주세요.'},429);
      const expectedHash=rec?.recovery_hash;
      const good=!!expectedHash && suppliedHash===expectedHash;
      if(!good){
        if(rec){
          const n=(rec.failed_attempts||0)+1;
          const patch:any={failed_attempts:n,updated_at:new Date().toISOString()};
          if(n>=5){patch.failed_attempts=0;patch.locked_until=new Date(Date.now()+15*60*1000).toISOString();}
          await admin.from('cre_account_recovery').update(patch).eq('user_id',rec.user_id);
          return reply({error:n>=5?'복구 코드를 5회 실패했습니다. 15분 동안 잠깁니다.':'아이디 또는 복구 코드가 맞지 않아요.'},401);
        }
        return reply({error:'아이디 또는 복구 코드가 맞지 않아요.'},401);
      }
      const {error:updateErr}=await admin.auth.admin.updateUserById(existing.id,{password:newPassword as string});
      if(updateErr) return reply({error:updateErr.code==='weak_password'?'더 안전한 비밀번호를 입력해 주세요.':'비밀번호를 변경하지 못했어요.'},400);
      await admin.from('cre_account_recovery').upsert({
        user_id:existing.id,username,recovery_hash:suppliedHash,failed_attempts:0,locked_until:null,updated_at:new Date().toISOString()
      },{onConflict:'user_id'});
      return reply({ok:true,message:'비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요.'});
    }

    const signup = action === 'signup';
    const invalid = validateCredentials(username, body.password, signup);
    if (invalid) return reply({ error: invalid }, 400);
    const password = body.password as string;
    let email: string, accountId: string;
    let recoveryCode: string|undefined;
    if (signup) {
      if (existing) return reply({ error: '이미 사용 중인 아이디예요. 다른 아이디를 입력해 주세요.' }, 409);
      email = 'cre-' + (await digest(username)).slice(0,40) + '@accounts.cre-growing.invalid';
      const { data, error } = await admin.auth.admin.createUser({
        email, password, email_confirm: true,
        app_metadata: { cre_game: true }, user_metadata: { nickname: username },
      });
      if (error || !data.user) {
        if (error?.code === 'email_exists' || error?.code === 'user_already_exists') return reply({ error: '이미 사용 중인 아이디예요.' }, 409);
        if (error?.code === 'weak_password') return reply({ error: '더 안전한 비밀번호를 입력해 주세요.' }, 400);
        return reply({ error: '가입을 완료하지 못했어요. 잠시 후 다시 시도해 주세요.' }, 503);
      }
      accountId = data.user.id;
      const { error: insertError } = await admin.from('cre_accounts').insert({ id: accountId, username });
      if (insertError) {
        await admin.auth.admin.deleteUser(accountId);
        return reply({ error: insertError.code === '23505' ? '이미 사용 중인 아이디예요.' : '가입을 완료하지 못했어요.' }, insertError.code === '23505' ? 409 : 503);
      }
      recoveryCode=createRecoveryCode();
      const {error:recInsert}=await admin.from('cre_account_recovery').insert({
        user_id:accountId,username,recovery_hash:await digest(username+':'+recoveryCode)
      });
      if(recInsert){
        await admin.from('cre_accounts').delete().eq('id',accountId);
        await admin.auth.admin.deleteUser(accountId);
        return reply({error:'복구 코드 생성에 실패해 가입을 취소했어요. 다시 시도해 주세요.'},503);
      }
    } else {
      if (!existing) return reply({ error: '아이디 또는 비밀번호가 맞지 않아요.' }, 400);
      accountId = existing.id;
      const { data, error } = await admin.auth.admin.getUserById(accountId);
      if (error || !data.user?.email) return reply({ error: '아이디 또는 비밀번호가 맞지 않아요.' }, 400);
      email = data.user.email;
    }
    const client = createClient(projectUrl, anonKey, options);
    const { data, error } = await client.auth.signInWithPassword({ email, password });
    if (error || !data.session || data.user?.id !== accountId) {
      return reply({ error: signup ? '가입했어요. 로그인 화면에서 다시 로그인해 주세요.' : '아이디 또는 비밀번호가 맞지 않아요.' }, 400);
    }
    return reply({ access_token: data.session.access_token, refresh_token: data.session.refresh_token, recovery_code: recoveryCode });
  } catch (e) {
    console.error('cre public account service unavailable');
    return reply({ error: '계정 연결이 원활하지 않아요. 잠시 후 다시 시도해 주세요.' }, 503);
  }
});

