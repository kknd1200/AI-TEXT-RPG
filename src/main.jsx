import React,{useEffect,useMemo,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {supabase} from './lib/supabase'
import {account,logout,resetPassword} from './services/auth'
import {loadGame,hatch,careAction,setActiveGecko} from './services/game'
import PixelGecko from './components/PixelGecko'
import './styles.css'
const R=r=>({common:'일반',uncommon:'고급',rare:'희귀',epic:'영웅',legendary:'전설'}[r]||r)

function Login({done}){
  const[m,setM]=useState('login'),[u,setU]=useState(''),[p,setP]=useState(''),[code,setCode]=useState(''),[p2,setP2]=useState(''),[msg,setMsg]=useState(''),[recovery,setRecovery]=useState(''),[busy,setBusy]=useState(false)
  const submit=async e=>{
    e.preventDefault();setMsg('');setBusy(true)
    try{
      if(m==='reset'){
        if(p!==p2) throw new Error('새 비밀번호 확인이 일치하지 않아요.')
        const r=await resetPassword(u,code,p)
        setMsg(r.message||'비밀번호가 변경되었습니다.')
        setM('login');setCode('');setP('');setP2('')
        return
      }
      const r=await account(m,u,p)
      if(m==='signup'&&r.recovery_code){setRecovery(r.recovery_code);setMsg('회원가입 완료! 아래 복구 코드를 안전한 곳에 보관해 주세요.');return}
      done()
    }catch(x){setMsg(x.message)}finally{setBusy(false)}
  }
  if(recovery)return <main className="auth"><section className="panel login"><h1>🔐 복구 코드</h1><p>비밀번호를 잊었을 때 필요한 코드예요. 이 화면을 닫으면 다시 표시되지 않습니다.</p><div className="recovery-code">{recovery}</div><button className="primary" onClick={()=>done()}>복구 코드를 저장했어요</button></section></main>
  return <main className="auth"><section className="panel login"><h1>🥚 크레키우기</h1><p>알에서 태어나는 나만의 픽셀 크레</p><form onSubmit={submit}><input value={u} onChange={e=>setU(e.target.value)} placeholder="아이디" autoComplete="username"/>{m==='reset'&&<input value={code} onChange={e=>setCode(e.target.value.toUpperCase())} placeholder="복구 코드 12자리" maxLength={12} autoCapitalize="characters"/>}<input type="password" value={p} onChange={e=>setP(e.target.value)} placeholder={m==='reset'?'새 비밀번호':'비밀번호'} autoComplete={m==='login'?'current-password':'new-password'}/>{m==='reset'&&<input type="password" value={p2} onChange={e=>setP2(e.target.value)} placeholder="새 비밀번호 확인" autoComplete="new-password"/>}<button disabled={busy}>{busy?'처리 중...':m==='login'?'로그인':m==='signup'?'회원가입':'비밀번호 변경'}</button></form>{msg&&<p className="auth-msg">{msg}</p>}<div className="auth-links">{m==='login'?<><button className="link" onClick={()=>{setM('signup');setMsg('')}}>처음 오셨나요? 회원가입</button><button className="link" onClick={()=>{setM('reset');setMsg('')}}>비밀번호를 잊으셨나요?</button></>:<button className="link" onClick={()=>{setM('login');setMsg('');setCode('');setP('');setP2('')}}>로그인으로 돌아가기</button>}</div>{m==='reset'&&<small className="help">복구 코드는 회원가입 때 한 번 표시됩니다. 기존 계정은 발급된 초기 복구 코드를 사용하세요.</small>}</section></main>
}

function App(){const[s,setS]=useState(null),[g,setG]=useState(null),[tab,setTab]=useState('home'),[note,setNote]=useState(''),[busy,setBusy]=useState(false);const refresh=async()=>setG(await loadGame());useEffect(()=>{supabase.auth.getSession().then(({data})=>setS(data.session));const{data:{subscription}}=supabase.auth.onAuthStateChange((_,x)=>setS(x));return()=>subscription.unsubscribe()},[]);useEffect(()=>{if(s)refresh();else setG(null)},[s]);const owned=useMemo(()=>new Set(g?.geckos?.map(x=>x.morph_id)||[]),[g]);if(!s)return <Login done={()=>supabase.auth.getSession().then(({data})=>setS(data.session))}/>;if(!g)return <main className="loading">불러오는 중...</main>;const active=g.geckos.find(x=>x.id===g.state?.active_gecko_id)||g.geckos[0],m=active?.cre_morphs,care=g.state?.care||{satiety:80,clean:80,happy:80,humidity:70};const doCare=async a=>{try{setBusy(true);const r=await careAction(a);if(r?.stage==='adult'&&active?.stage!=='adult')setNote('🎉 성체로 성장했어요!');await refresh()}catch(e){setNote(e.message)}finally{setBusy(false)}};return <main className="game"><header><div><b>크레키우기</b><small>PIXEL TERRARIUM</small></div><div>🥚 {g.state?.eggs??0}　🪙 {g.state?.coins??0}　<button onClick={async()=>{await logout();setS(null)}}>로그아웃</button></div></header><nav><button onClick={()=>setTab('home')}>사육장</button><button onClick={()=>setTab('mine')}>내 크레</button><button onClick={()=>setTab('dex')}>도감 36</button></nav>{tab==='home'&&<><section className="panel terrarium"><div className="scene"><PixelGecko morph={m} stage={active?.stage||'baby'}/></div><aside><h2>{m?.name_ko||'부화를 기다리는 알'}</h2>{m&&<p><b className={'tag '+m.rarity}>{R(m.rarity)}</b> · {m.name_en}</p>}{active&&<div className="growth">성장 {active.stage==='adult'?'성체':`${active.growth_xp}/100`}</div>}{[['포만감','satiety'],['청결','clean'],['행복','happy'],['습도','humidity']].map(([n,k])=><div className="meter" key={k}><span>{n}</span><div><i style={{width:`${care[k]||0}%`}}/></div><b>{care[k]||0}</b></div>)}<button className="hatch" disabled={busy||!g.state?.eggs} onClick={async()=>{try{setBusy(true);const r=await hatch();setNote(`✨ ${r.name_ko} 부화!`);await refresh()}catch(e){setNote(e.message)}finally{setBusy(false)}}}>🥚 알 부화하기</button></aside></section><section className="care"><button onClick={()=>doCare('feed')}>🍽️<b>먹이</b></button><button onClick={()=>doCare('spray')}>💧<b>분무</b></button><button onClick={()=>doCare('clean')}>🧹<b>청소</b></button><button onClick={()=>doCare('play')}>🪀<b>놀기</b></button></section></>}{note&&<div className="toast">{note}</div>}{tab==='mine'&&<section className="panel collection"><h2>내 크레 · {g.geckos.length}마리</h2><div className="cards">{g.geckos.map(x=><button key={x.id} className="card" onClick={async()=>{await setActiveGecko(x.id);await refresh()}}><PixelGecko morph={x.cre_morphs} stage={x.stage}/><b>{x.cre_morphs.name_ko}</b><small>{R(x.cre_morphs.rarity)} · {x.stage==='adult'?'성체':`아기 ${x.growth_xp}/100`}</small></button>)}</div></section>}{tab==='dex'&&<section className="panel collection"><h2>크레 도감 · 발견 {owned.size}/36</h2><div className="dex">{g.morphs.map(x=><article className={owned.has(x.id)?'found':'locked'} key={x.id}><span>#{String(x.display_order).padStart(2,'0')}</span><b className={'tag '+x.rarity}>{R(x.rarity)}</b><PixelGecko morph={x} stage="adult"/><h3>{x.name_ko}</h3><small>{x.name_en}</small><p>{x.description_ko}</p><footer>부화확률 {Number(x.hatch_rate).toFixed(1)}%</footer></article>)}</div></section>}</main>}
createRoot(document.getElementById('root')).render(<App/>)
