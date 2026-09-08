import { useMemo, useState } from 'react';
import { ArrowLeft, BookOpen, Pause, Play } from 'lucide-react';
import { MORPHS, canonicalMorphId, type Creature } from '@/lib/pet';
import { hasSpriteAction, SPRITE_COVERAGE, type SpriteAction } from '@/lib/sprites';
import { CreSprite, CareEffect, useSpriteFrame } from './cre-sprite';
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogTrigger } from './ui/dialog';

const actions:{id:SpriteAction;label:string}[]=[{id:'idle',label:'가만히'},{id:'feed',label:'먹기'},{id:'mist',label:'분무'},{id:'clean',label:'청소'},{id:'play',label:'놀기'}];
function Gallery({owned=[]}:{owned?:Creature[]}) {
 const [query,setQuery]=useState(''),[rarity,setRarity]=useState('전체'),[action,setAction]=useState<SpriteAction>('idle'),[playing,setPlaying]=useState(true);
 const frame=useSpriteFrame(action,playing);
 const found=new Set(owned.map(c=>canonicalMorphId(c.morphId)));
 const visible=useMemo(()=>MORPHS.filter(m=>(rarity==='전체'||m.rarity===rarity)&&`${m.name} ${m.pattern}`.includes(query.trim())),[query,rarity]);
 return <div className="morph-gallery">
  <div className="gallery-controls">
   <div className="gallery-search"><label htmlFor="morph-search">크레 찾기</label><input id="morph-search" placeholder="색이나 무늬로 검색" value={query} onChange={e=>setQuery(e.target.value)}/><label className="sr-only" htmlFor="morph-rarity">등급</label><select id="morph-rarity" value={rarity} onChange={e=>setRarity(e.target.value)}>{['전체','일반','고급','희귀','영웅','전설'].map(r=><option key={r}>{r}</option>)}</select></div>
   <div className="gallery-animation" aria-label="돌봄 동작 선택">{actions.map(a=><button type="button" aria-pressed={action===a.id} key={a.id} onClick={()=>setAction(a.id)}>{a.label}</button>)}<button type="button" className="animation-toggle" disabled={action==='idle'} aria-label={playing?'애니메이션 일시 정지':'애니메이션 재생'} onClick={()=>setPlaying(v=>!v)}>{playing?<Pause size={15}/>:<Play size={15}/>}</button></div>
  </div>
  <p className="gallery-count">{visible.length}종 · 아기와 성체를 나란히 만나보세요{owned.length>0?` · 만난 모프 ${found.size}/36`:''}</p>
  {!SPRITE_COVERAGE.complete&&<p className="gallery-note">72가지 모습과 돌봄 동작 {SPRITE_COVERAGE.animations}/288개가 공개됐어요. 준비 중인 동작은 기본 자세로 표시되며, 배고픔·습도·청결·기분 변화는 그대로 적용돼요.</p>}
  <div className="morph-grid">{visible.map(m=><article className="morph-card" key={m.id} data-morph-id={m.id}>
   <div className="morph-card-top"><span className={'rarity-label rarity-'+m.rarity}>{m.rarity}</span><span>{m.weight/100}%</span></div>
   <div className="morph-pair">{(['baby','adult'] as const).map(stage=><figure key={stage}><div className="gallery-sprite-stage"><CreSprite creature={{phase:'hatched',morphId:m.id,xp:stage==='adult'?240:0}} action={action} frame={frame} label={`${m.name} ${stage==='adult'?'성체':'아기'}`}/><CareEffect action={action} frame={frame}/></div><figcaption>{stage==='baby'?'아기':'성체'}{!hasSpriteAction(m.id,stage,action)&&' · 동작 준비 중'}</figcaption></figure>)}</div>
   <h3>{m.name}</h3><p>{m.pattern}</p>{found.has(m.id)&&<span className="owned-mark">우리 집에서 만났어요</span>}
  </article>)}</div>
  {visible.length===0&&<p className="gallery-empty">해당하는 크레가 없어요. 다른 색이나 무늬를 찾아보세요.</p>}
  <p className="gallery-note">36종의 부화 확률 합계는 100%예요. 매번 독립 추첨하므로 같은 모프가 다시 태어날 수 있어요. 성장해도 모프는 바뀌지 않으며, 아성체는 아기의 모습을 사용하고 성장 240점에서 성체 모습이 됩니다.</p>
 </div>;
}

export function MorphGalleryDialog({owned}:{owned:Creature[]}) {
 const [open,setOpen]=useState(false);
 return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><button className="odds-link"><BookOpen size={16}/>36종 도감 · 돌봄 동작 보기</button></DialogTrigger><DialogContent className="gallery-dialog"><DialogTitle>크레 도감</DialogTitle><DialogDescription>36종 × 아기·성체, 72가지 모습을 만나보세요.</DialogDescription>{open&&<Gallery owned={owned}/>}</DialogContent></Dialog>;
}

export function MorphGalleryPage() {
 return <main className="gallery-page"><a className="gallery-back" href="/"><ArrowLeft size={17}/>크레키우기로</a><p className="eyebrow">CRESTED GECKO COLLECTION</p><h1>작은 도트, 36가지 만남.</h1><p className="gallery-intro">같은 색과 무늬를 간직한 채, 아기에서 성체로 자라요.</p><Gallery/></main>;
}
