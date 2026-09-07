import { useEffect, useState } from 'react';
import { spriteAsset, spriteStage, spriteCell, SPRITE_COLUMNS, SPRITE_ROWS, type SpriteAction } from '@/lib/sprites';
import type { Creature } from '@/lib/pet';

export function useSpriteFrame(action:SpriteAction,playing=true) {
 const [frame,setFrame]=useState(0);
 useEffect(()=>{
  setFrame(0);
  const preference=window.matchMedia('(prefers-reduced-motion: reduce)');
  let timer:ReturnType<typeof setInterval>|undefined;
  const sync=()=>{
   if(timer)clearInterval(timer);
   setFrame(0);
   if(playing&&action!=='idle'&&!preference.matches)timer=setInterval(()=>setFrame(f=>(f+1)%4),240);
  };
  sync();preference.addEventListener('change',sync);
  return()=>{if(timer)clearInterval(timer);preference.removeEventListener('change',sync);};
 },[action,playing]);
 return frame;
}

type Props={creature:Pick<Creature,'phase'|'morphId'|'xp'>;action?:SpriteAction;frame?:number;className?:string;label?:string};
export function CreSprite({creature,action='idle',frame=0,className='',label}:Props) {
 const {url,atlas}=spriteAsset(creature,action);
 const index=atlas&&action!=='idle'?Math.max(0,Math.min(3,frame)):0;
 const cell=spriteCell(spriteStage(creature.xp),action,index);
 return <span className={`cre-sprite ${className}`} role={label?'img':undefined} aria-label={label} aria-hidden={label?undefined:true}
  data-morph={creature.morphId} data-stage={creature.xp>=240?'adult':'baby'} data-action={action} data-frame={index}
  style={{backgroundImage:`url("${url}")`,backgroundSize:atlas?`${SPRITE_COLUMNS*100}% ${SPRITE_ROWS*100}%`:'100% 100%',backgroundPosition:atlas?`${cell.col/(SPRITE_COLUMNS-1)*100}% ${cell.row/(SPRITE_ROWS-1)*100}%`:'center'}}/>;
}

export function CareEffect({action,frame=0}:{action:SpriteAction;frame?:number}) {
 if(action==='idle')return null;
 return <span className={`care-effect effect-${action}`} aria-hidden="true" style={{backgroundImage:`url("/assets/cre36/fx/${action}.png")`,backgroundPosition:`${(frame%2)*100}% ${Math.floor(frame/2)*100}%`}}/>;
}
