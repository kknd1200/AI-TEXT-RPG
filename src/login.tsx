import { useState, type FormEvent } from 'react';
import { Leaf } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { normalizeUsername, validateCredentials } from '@/lib/credentials';
import { accountRequest } from '@/services/auth';

export default function Login({ done, initialError = '' }: { done(): Promise<void>; initialError?: string }) {
  const [mode, setMode] = useState<'login' | 'signup' | 'reset'>('login');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initialError);
  const [notice, setNotice] = useState('');
  const [recovery, setRecovery] = useState('');
  const [newWindow, setNewWindow] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const username = normalizeUsername(form.get('username'));
    const password = form.get('password');
    const invalid = validateCredentials(username, password, mode !== 'login');
    if (invalid) { setError(invalid); return; }
    if (mode !== 'login' && password !== form.get('confirmation')) { setError('비밀번호가 서로 달라요. 다시 확인해 주세요.'); return; }
    setBusy(true); setError(''); setNotice(''); setNewWindow(false);
    try {
      // Browsers that block embedded storage should offer a working standalone login.
      try {
        localStorage.setItem('cre-storage-check', '1');
        if (localStorage.getItem('cre-storage-check') !== '1') throw new Error('Storage unavailable');
        localStorage.removeItem('cre-storage-check');
      } catch { throw new Error('이 창에서 로그인을 유지하지 못했어요. 새 창에서 로그인해 주세요.'); }
      const result = await accountRequest(mode === 'reset'
        ? { action: mode, username, recoveryCode: form.get('recoveryCode'), newPassword: password }
        : { action: mode, username, password });
      if (mode === 'reset') {
        setMode('login'); formElement.reset();
        setNotice(result.message || '비밀번호가 변경되었어요. 새 비밀번호로 로그인해 주세요.');
      } else if (mode === 'signup' && result.recovery_code) {
        // Do not enter the game from SIGNED_IN before the user has saved this code.
        setRecovery(result.recovery_code);
      } else { await done(); }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '연결이 원활하지 않아요. 다시 시도해 주세요.');
      setNewWindow(true);
    } finally { setBusy(false); }
  }

  async function finishSignup() {
    setBusy(true); setError('');
    try { await done(); } catch (cause) { setError(cause instanceof Error ? cause.message : '다시 시도해 주세요.'); }
    finally { setBusy(false); }
  }

  return <main className="login-shell">
    <a href="/" className="brand"><span className="brand-mark"><Leaf size={23}/></span>크레키우기</a>
    <section className="login-card">
      <div className="login-art"><img className="login-room" src="/assets/terrarium.png" alt="작은 크레가 기다리는 도트 사육장"/><img className="login-cre" src="/assets/morphs/flame/frame-0.png" alt="오렌지 크레스티드 게코"/></div>
      <div className="login-content">{recovery ? <>
        <h1>새로운 집사가 되었어요!</h1>
        <p className="auth-intro">비밀번호를 잊었을 때 필요한 복구 코드예요. 이 화면을 닫으면 다시 표시되지 않으니 안전한 곳에 적어 두세요.</p>
        <code className="recovery-code">{recovery}</code>
        {error && <p className="login-error" role="alert">{error}</p>}
        <Button className="auth-submit" disabled={busy} onClick={() => void finishSignup()}>복구 코드를 저장했어요 · 알 만나기</Button>
      </> : <>
        <h1>{mode === 'signup' ? '새로운 크레 집사 되기' : mode === 'reset' ? '비밀번호 다시 정하기' : '내 크레 만나러 가기'}</h1>
        <p className="auth-intro">{mode === 'signup' ? '아이디와 비밀번호만 있으면 시작할 수 있어요.' : mode === 'reset' ? '가입할 때 받은 복구 코드를 입력해 주세요.' : '로그인하고 키우던 크레를 만나보세요.'}</p>
        <form className="account-form" onSubmit={submit} aria-busy={busy}>
          <label htmlFor="username">아이디</label>
          <Input id="username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} required minLength={4} maxLength={20} placeholder="영문·숫자·밑줄 4~20자" disabled={busy}/>
          {mode === 'reset' && <><label htmlFor="recoveryCode">복구 코드</label><Input id="recoveryCode" name="recoveryCode" autoComplete="off" required minLength={12} maxLength={12} placeholder="가입할 때 받은 12자리 코드" disabled={busy}/></>}
          <label htmlFor="password">{mode === 'reset' ? '새 비밀번호' : '비밀번호'}</label>
          <Input id="password" name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={8} maxLength={72} placeholder="영문과 숫자를 포함한 8자 이상" disabled={busy}/>
          {mode !== 'login' && <><label htmlFor="confirmation">비밀번호 확인</label><Input id="confirmation" name="confirmation" type="password" autoComplete="new-password" required minLength={8} maxLength={72} placeholder="비밀번호를 한 번 더 입력해 주세요" disabled={busy}/></>}
          {error && <p className="login-error" role="alert">{error}</p>}
          {notice && <p className="auth-notice" role="status">{notice}</p>}
          {newWindow && <a className="auth-open-window" href="/login" target="_blank" rel="noopener noreferrer">새 창에서 로그인</a>}
          <Button className="auth-submit" disabled={busy}>{busy ? '계정을 확인하고 있어요…' : mode === 'signup' ? '가입하고 알 만나기' : mode === 'reset' ? '비밀번호 변경' : '로그인'}</Button>
        </form>
        <p className="auth-switch">{mode === 'login' ? '처음 오셨나요?' : '이미 계정이 있나요?'} <Button type="button" disabled={busy} onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); setNotice(''); }}>{mode === 'login' ? '회원가입' : '로그인'}</Button></p>
        {mode === 'login' && <button className="recovery-link" disabled={busy} onClick={() => { setMode('reset'); setError(''); setNotice(''); }}>비밀번호를 잊으셨나요?</button>}
        {mode === 'signup' && <p className="signup-note">지금은 이메일 없이 가입할 수 있어요.</p>}
      </>}</div>
    </section>
  </main>;
}
