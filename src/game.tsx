'use client';
import { useEffect, useRef, useState } from 'react';
import { Heart, Droplets, Sparkles, Utensils, Save, Pencil, Leaf, Check, RefreshCw, Egg, Flame, Plus } from 'lucide-react';
import { petFetch } from '@/lib/supabase';
import { Progress } from '@/components/ui/progress';
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogTrigger } from '@/components/ui/dialog';
import { morphOf, stageNames, stageOf, type Pet, type Creature, type Action } from '@/lib/pet';
import { CreSprite, CareEffect, useSpriteFrame } from '@/components/cre-sprite';
import { MorphGalleryDialog } from '@/components/morph-gallery';
import { spriteAsset, isSpriteAction } from '@/lib/sprites';
type PetResponse={pet?:Pet;revision:number;message:string;error:string};
const petActions=[{id:'feed',label:'먹이 주기',sub:'냠냠, 한 입',Icon:Utensils},{id:'mist',label:'분무하기',sub:'촉촉한 우리 집',Icon:Droplets},{id:'clean',label:'청소하기',sub:'반짝반짝 깨끗하게',Icon:Sparkles},{id:'play',label:'놀아주기',sub:'조금 더 가까이',Icon:Heart}] as const;
const eggActions=[{id:'warm',label:'온기 전하기',sub:'부화 준비 +12%',Icon:Flame},{id:'mist',label:'분무하기',sub:'부화 준비 +12%',Icon:Droplets},{id:'clean',label:'청소하기',sub:'부화 준비 +12%',Icon:Sparkles}] as const;
export default function Game({accountName,onLogout}:{accountName:string;onLogout:()=>Promise<void>}){
 const [pet,setPet]=useState<Pet|null>(null),[revision,setRevision]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(''),[auth,setAuth]=useState(false),[message,setMessage]=useState('어떤 크레를 만나게 될까요?'),[action,setAction]=useState('idle'),[renaming,setRenaming]=useState(false),[name,setName]=useState(''),[saved,setSaved]=useState(''),[cooldown,setCooldown]=useState(false),[clock,setClock]=useState(0),[hatching,setHatching]=useState(false),[hatchFrame,setHatchFrame]=useState(0),[reveal,setReveal]=useState<Creature|null>(null);
 const visualAction=isSpriteAction(action)?action:'idle';
 const frame=useSpriteFrame(visualAction);
 const locked=useRef(false),timers=useRef<ReturnType<typeof setTimeout>[]>([]),latest=useRef({pet,revision});latest.current={pet,revision};
 function later(fn:()=>void,ms:number){timers.current.push(setTimeout(fn,ms));}
 function accept(d:PetResponse){if(d.pet){latest.current={pet:d.pet,revision:d.revision};setPet(d.pet);setRevision(d.revision);setClock(Date.now());}}
 async function load(){if(locked.current)return;locked.current=true;setError('');setBusy(true);try{const r=await petFetch(),d=await r.json() as PetResponse;if(!r.ok){setAuth(r.status===401);throw Error(d.error);}accept(d);setMessage(d.pet?.lastAction??'반가워요!');setSaved('성장 기록 불러옴');}catch(e){setError(e instanceof Error?e.message:'다시 시도해 주세요.');}finally{setBusy(false);locked.current=false;}}
 async function doAction(a:Action,value?:string){
  if(locked.current||!latest.current.pet)return;const previous=latest.current.pet;locked.current=true;setBusy(true);setError('');
  try{const r=await petFetch({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a,name:value,revision:latest.current.revision})}),d=await r.json() as PetResponse;
   accept(d);if(!r.ok){if(r.status===401)window.location.assign('/login');throw Error(d.error);}setSaved(new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit'})+' 저장됨');
   if(a!=='save')setMessage(d.message);
   if(a==='hatch'&&previous.phase==='egg'&&d.pet?.phase==='hatched'){
    const born=d.pet;setHatching(true);setHatchFrame(0);for(let i=1;i<4;i++)later(()=>setHatchFrame(i),i*360);later(()=>{setHatching(false);setReveal(born);},1600);
   }else if(d.pet&&d.pet.lastCare>previous.lastCare&&a!=='save'){
    setAction(a);setCooldown(true);later(()=>{setAction('idle');setCooldown(false);},3000);
   }
   if(['rename','newEgg','select'].includes(a)){setRenaming(false);setAction('idle');setCooldown(false);}
  }catch(e){setError(e instanceof Error?e.message:'저장하지 못했어요.');}finally{setBusy(false);locked.current=false;}
 }
 useEffect(()=>{void load();const autosave=setInterval(()=>void doAction('save'),60000);const tick=setInterval(()=>setClock(Date.now()),1000);return ()=>{clearInterval(autosave);clearInterval(tick);timers.current.forEach(clearTimeout);};},[]);
 const isEgg=pet?.phase==='egg',stage=stageOf(pet?.xp??0),morph=morphOf(pet?.morphId),eggProgress=pet?Math.min(100,pet.incubation+Math.max(0,clock-pet.updated)/1800):0;
 const growth=isEgg?eggProgress:stage===2?100:stage===1?((pet?.xp??0)-80)/160*100:(pet?.xp??0)/80*100;
 useEffect(()=>{if(!pet||pet.phase==='egg')return;const image=new Image();image.src=spriteAsset(pet).url;},[pet?.morphId,stage]);
 const blocked=!pet||busy||cooldown||hatching;
 const stats=[{label:'포만감',value:pet?.food??0,Icon:Utensils,color:'orange'},{label:'촉촉함',value:pet?.moisture??0,Icon:Droplets,color:'blue'},{label:'청결',value:pet?.clean??0,Icon:Sparkles,color:'green'},{label:'행복',value:pet?.happy??0,Icon:Heart,color:'pink'}];
 return <main className="shell">
  <header className="topbar"><a className="brand" href="/" aria-label="크레키우기 홈"><span className="brand-mark"><Leaf size={23}/></span>크레키우기<span className="edition">PIXEL PET</span></a><div className="account-actions"><span className="account-name">{accountName}님</span><button className="logout-button" disabled={busy||hatching} onClick={()=>void onLogout()}>로그아웃</button><button className="save" onClick={()=>void doAction('save')} disabled={!pet||busy||hatching}><Save size={16}/>저장</button></div></header>
  <div className="title-row"><div><p className="eyebrow">A TINY EGG, A NEW FRIEND</p><h1>{isEgg?'작은 알 속, 새로운 만남.':'작은 크레, 함께하는 하루.'}</h1></div><span className="day">{isEgg?'부화 준비 중':`함께한 지 ${pet?Math.floor((Date.now()-pet.born)/86400000)+1:1}일`}</span></div>
  <div className="game-layout"><section className="habitat-card" aria-label="크레 사육장">
   <div className="habitat-label"><span>{isEgg?<Egg size={15}/>:<Leaf size={15}/>} {isEgg?'알 돌보기':'나의 사육장'}</span><span>01</span></div>
   <div className={'habitat '+action+(hatching?' hatching':'')}>
    <img className="terrarium" src="/assets/terrarium.png" alt="식물과 나뭇가지, 은신처가 있는 도트 사육장"/>
    {pet&&<><div className="speech" aria-live="polite">{hatching?'톡, 톡… 새로운 친구가 나와요!':isEgg&&eggProgress>=100?'준비됐어요! 부화하기를 눌러 주세요.':message}</div>
    <div className={'pet-position '+(isEgg||hatching?'egg-position':'stage-'+stage)}>{isEgg||hatching?<img className="gecko" src={`/assets/morphs/egg/frame-${hatching?hatchFrame:eggProgress>=100?1:0}.png`} alt="부화 준비 중인 알"/>:<CreSprite creature={pet} action={visualAction} frame={frame} className="gecko" label={`${morph.name} ${pet.name}`}/>}<CareEffect action={visualAction} frame={frame}/></div><span className="pet-tag">{hatching?'두근두근':pet.name} <Heart size={11} fill="currentColor"/></span></>}
    {!pet&&<div className="load-overlay">{busy?'크레를 만나러 가는 중…':auth?<a href="/login" target="_top">로그인하고 알 만나기</a>:<button onClick={()=>void load()}>다시 불러오기</button>}</div>}
   </div>
   <div className="habitat-footer"><span><Heart size={14}/> {pet?pet.lastAction:'새로운 만남이 기다리고 있어요'}</span><span>CRESTED GECKO</span></div>
  </section>
  <aside className="pet-panel"><div className="pet-heading"><span className="stage-badge">{isEgg?'알':stageNames[stage]}</span><span className="species">{isEgg?'아직은 비밀이에요':morph.name}</span></div>
   {renaming?<form className="rename" onSubmit={e=>{e.preventDefault();void doAction('rename',name);}}><label htmlFor="pet-name">이름 (최대 12자)</label><div><input id="pet-name" value={name} maxLength={12} onChange={e=>setName(e.target.value)} autoFocus/><button disabled={!name.trim()||busy}>확인</button><button type="button" onClick={()=>setRenaming(false)}>취소</button></div></form>:<div className="name-row"><h2>{pet?.name??'새로운 알'}</h2><button aria-label="이름 바꾸기" disabled={!pet||hatching} onClick={()=>{setName(pet?.name??'');setRenaming(true);}}><Pencil size={16}/></button></div>}
   <p className="personality">{isEgg?'알을 돌보며 첫 만남을 기다려요.':stage===0?'세상이 궁금한 작은 베이비':stage===1?'매일 조금씩 자라는 중':'어느새 든든한 나의 친구'}</p>
   {isEgg?<div className="egg-info"><Egg size={28}/><strong>색과 무늬는 부화할 때 결정돼요</strong><p>그냥 기다리면 약 3분.<br/>돌볼 때마다 준비가 12%씩 빨라져요.</p><span>일반부터 전설까지, 36가지 만남</span></div>:<><div className={'morph-badge rarity-'+morph.rarity}><span style={{background:morph.swatch}}/>{morph.rarity} · {morph.pattern}</div><div className="stats">{stats.map(({label,value,Icon,color})=><div className={'stat '+color} key={label}><div><span><Icon size={16}/>{label}</span><b>{Math.round(value)}<small> / 100</small></b></div><Progress value={value} aria-label={label}/></div>)}</div></>}
   <div className="growth"><div className="growth-title"><span><Leaf size={17}/>{isEgg?'부화 준비':'성장 기록'}</span><b>{!isEgg&&stage===2?'성장 완료':Math.floor(growth)+'%'}</b></div><Progress value={growth} aria-label={isEgg?'부화 준비':'다음 단계까지 성장'}/>
   {isEgg?<p>{eggProgress>=100?'이제 새로운 친구를 만날 수 있어요.':`가만히 기다리면 약 ${Math.ceil((100-eggProgress)*1.8)}초 남았어요.`}</p>:<><div className="stages">{stageNames.map((s,i)=><span className={i<=stage?'reached':''} key={s}>{i<stage?<Check size={12}/>:<span className="stage-dot"/>}{s}</span>)}</div><p>{stage===2?'다 자라도 돌봄은 계속돼요.':`다음 단계까지 성장 ${Math.ceil((stage===0?80:240)-(pet?.xp??0))}점`}</p></>}</div>
   <MorphGalleryDialog owned={pet?[pet,...pet.nursery]:[]}/>
  </aside></div>
  <section className="care-section" aria-label="돌보기"><div className="section-head"><h2>{isEgg?'알 돌보기':'오늘의 돌봄'}</h2><span>{isEgg?'두근두근, 어떤 색일까요?':'작은 관심이 쌓여, 쑥쑥 자라요'}</span></div><div className="care-actions">{(isEgg?eggActions:petActions).map(({id,label,sub,Icon})=><button key={id} className={'care-button '+id} disabled={blocked||(isEgg&&eggProgress>=100)} onClick={()=>void doAction(id)}><span className="action-icon"><Icon size={27} strokeWidth={1.8}/></span><span><strong>{label}</strong><small>{sub}</small></span></button>)}{isEgg&&<button className="care-button hatch-button" disabled={blocked||eggProgress<100} onClick={()=>void doAction('hatch')}><span className="action-icon"><Egg size={27}/></span><span><strong>부화하기</strong><small>{eggProgress>=100?'새 친구 만나기':'준비가 끝나면 열려요'}</small></span></button>}</div></section>
  {error&&<div className="error" role="alert">{error}<button onClick={()=>void load()} disabled={busy}><RefreshCw size={14}/>다시 불러오기</button></div>}
  {pet&&<section className="nursery"><div className="section-head"><h2>나의 알과 크레 <small>{pet.nursery.length+1}</small></h2><button className="new-egg" disabled={blocked||isEgg} onClick={()=>void doAction('newEgg')}><Plus size={16}/>새 알 받기</button></div><p>새 알을 받으면 지금 크레는 이곳에 보관돼요. 보관 중에는 성장과 상태 변화가 쉬어가요.</p><div className="nursery-list">{[pet,...pet.nursery].map(c=><button key={c.id} className={'nursery-pet '+(c.id===pet.id?'active':'')} disabled={busy||hatching||c.id===pet.id} onClick={()=>void doAction('select',c.id)}><CreSprite creature={c}/><strong>{c.name}</strong><span>{c.phase==='egg'?'부화 준비 중':morphOf(c.morphId).name}</span><small>{c.id===pet.id?'지금 돌보는 중':'눌러서 돌보기'}</small></button>)}</div></section>}
  <footer className="bottom"><span><Check size={14}/>{busy?'기록하는 중…':saved||'돌봄 후 자동으로 저장돼요'}</span><span>{isEgg?'알 → 부화 → 베이비 → 아성체 → 성체':'돌봄 +10점 · 건강할 때 시간에 따라 성장'}</span></footer>
  <p className="gentle-note">오래 자리를 비워도 괜찮아요. 돌봄이 필요하면 성장을 잠시 쉬어요.</p>
  <Dialog open={!!reveal} onOpenChange={open=>{if(!open)setReveal(null);}}><DialogContent className="hatch-result"><DialogTitle>새로운 친구가 태어났어요!</DialogTitle><DialogDescription>색과 무늬가 정해졌어요. 이제 이름을 짓고 함께 자라 보세요.</DialogDescription>{reveal&&<><CreSprite creature={reveal} className="reveal-sprite" label={morphOf(reveal.morphId).name}/><span className="result-rarity">{morphOf(reveal.morphId).rarity} · {morphOf(reveal.morphId).weight/100}%</span><h3>{morphOf(reveal.morphId).name}</h3><p>{morphOf(reveal.morphId).pattern}</p><button onClick={()=>{setReveal(null);setName(reveal.name);setRenaming(true);}}>이름 지어주기</button></>}</DialogContent></Dialog>
 </main>;
}
