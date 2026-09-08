import { canonicalMorphId, type Creature } from './pet.ts';
import manifest from '../../public/assets/cre36/manifest.json' with { type: 'json' };

export const SPRITE_ACTIONS=['idle','feed','mist','clean','play'] as const;
export type SpriteAction=typeof SPRITE_ACTIONS[number];
export type SpriteStage='baby'|'adult';
export const spriteStage=(xp:number):SpriteStage=>xp>=240?'adult':'baby';
export const isSpriteAction=(value:string):value is SpriteAction=>SPRITE_ACTIONS.includes(value as SpriteAction);
export const SPRITE_COLUMNS=8;
export const SPRITE_ROWS=5;
export const spriteCell=(stage:SpriteStage,action:SpriteAction,frame=0)=>({col:(stage==='adult'?4:0)+(action==='idle'?0:Math.max(0,Math.min(3,frame))),row:SPRITE_ACTIONS.indexOf(action)});
const forms = new Map(manifest.forms.map(form => [`${form.morphId}-${form.stage}`, form]));
export const SPRITE_COVERAGE = {
 forms: manifest.forms.length,
 animations: manifest.forms.reduce((count, form) => count + Object.keys(form.animations).filter(action => action !== 'idle').length, 0),
 complete: manifest.complete,
};

export function hasSpriteAction(morphId:string|undefined,stage:SpriteStage,action:SpriteAction) {
 const form=forms.get(`${canonicalMorphId(morphId)}-${stage}`);
 return Boolean(form && Object.hasOwn(form.animations,action));
}

export function spriteEffect(action:SpriteAction) {
 return action==='idle'||manifest.missingEffects.includes(action)?null:`/assets/cre36/fx/${action}.png`;
}

export function spriteAsset(creature:Pick<Creature,'phase'|'morphId'|'xp'>,action:SpriteAction='idle') {
 if(creature.phase==='egg')return {url:'/assets/morphs/egg/frame-0.png',atlas:false,action:'idle' as const};
 const id=canonicalMorphId(creature.morphId);
 const form=forms.get(`${id}-${spriteStage(creature.xp)}`);
 if(form)return {url:form.sheet,atlas:true,action:hasSpriteAction(id,spriteStage(creature.xp),action)?action:'idle' as const};
 // The previous season's yellow tiger has no exact counterpart among the 36.
 // Retain that saved appearance instead of silently changing its color.
 return {url:'/assets/morphs/tiger/frame-0.png',atlas:false,action:'idle' as const};
}
