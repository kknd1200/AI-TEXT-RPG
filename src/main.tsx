import { lazy, Suspense, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { supabase, accountName } from '@/lib/supabase';
import Login from './login';
import './styles.css';

const Game = lazy(() => import('./game'));
const GalleryPage = lazy(() => import('./components/morph-gallery').then(module=>({default:module.MorphGalleryPage})));

function App() {
  const [name, setName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    accountName().then(value => { if (active) setName(value); })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : '로그인 상태를 확인하지 못했어요.'); })
      .finally(() => { if (active) setLoading(false); });
    const { data: { subscription } } = supabase.auth.onAuthStateChange(event => {
      if (event === 'SIGNED_OUT') { setName(null); setError(''); }
    });
    return () => { active = false; subscription.unsubscribe(); };
  }, []);
  async function enter() {
    const current = await accountName();
    if (!current) throw new Error('로그인 상태를 확인하지 못했어요.');
    setError(''); setName(current); window.history.replaceState(null, '', '/');
  }
  async function logout() {
    const { error: cause } = await supabase.auth.signOut({ scope: 'local' });
    if (cause) { setError('로그아웃하지 못했어요. 연결을 확인하고 다시 눌러 주세요.'); return; }
    setName(null); setError(''); window.history.replaceState(null, '', '/login');
  }
  if (loading) return <main className="session-loading" role="status">나의 크레를 만나러 가는 중…</main>;
  if (!name) return <Login done={enter} initialError={error}/>;
  return <>{error && <p className="session-error" role="alert">{error}</p>}<Suspense fallback={<main className="session-loading" role="status">사육장을 준비하고 있어요…</main>}><Game key={name} accountName={name} onLogout={logout}/></Suspense></>;
}

createRoot(document.getElementById('root')!).render(window.location.pathname==='/morphs'?<Suspense fallback={<main className="session-loading">도감을 펼치는 중…</main>}><GalleryPage/></Suspense>:<App/>);
