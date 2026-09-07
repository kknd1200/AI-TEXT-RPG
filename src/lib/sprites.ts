import { canonicalMorphId, type Creature } from './pet';

export const SPRITE_ACTIONS=['idle','feed','mist','clean','play'] as const;
export type SpriteAction=typeof SPRITE_ACTIONS[number];
export type SpriteStage='baby'|'adult';
export const spriteStage=(xp:number):SpriteStage=>xp>=240?'adult':'baby';
export const isSpriteAction=(value:string):value is SpriteAction=>SPRITE_ACTIONS.includes(value as SpriteAction);
export const SPRITE_COLUMNS=8;
export const SPRITE_ROWS=5;
export const spriteCell=(stage:SpriteStage,action:SpriteAction,frame=0)=>({col:(stage==='adult'?4:0)+(action==='idle'?0:Math.max(0,Math.min(3,frame))),row:SPRITE_ACTIONS.indexOf(action)});

export function spriteAsset(creature:Pick<Creature,'phase'|'morphId'|'xp'>,action:SpriteAction='idle') {
 if(creature.phase==='egg')return {url:'/assets/morphs/egg/frame-0.png',atlas:false};
 const id=canonicalMorphId(creature.morphId);
 if(id)return {url:`/assets/cre36/atlases/${id}.png`,atlas:true};
 // The previous season's yellow tiger has no exact counterpart among the 36.
 // Retain that saved appearance instead of silently changing its color.
 return {url:'/assets/morphs/tiger/frame-0.png',atlas:false};
}
