import { MORPH_CATALOG } from './morph-catalog.ts';

const rarityNames={common:'일반',uncommon:'고급',rare:'희귀',epic:'영웅',legendary:'전설'} as const;
const colors={orange:['오렌지','#e59036'],yellow:['옐로우','#eddb63'],cream:['크림','#e9d2a5'],brown:['브라운','#93633d'],red:['레드','#b84436'],olive:['올리브','#89904d'],gray:['그레이','#969ba3'],white:['화이트','#eceae1'],black:['블랙','#35343c'],lavender:['라벤더','#a49abb']} as const;
const patterns={patternless:'무늬 없음',flame:'밝은 등 무늬',tiger:'등과 옆구리를 가로지르는 줄무늬',harlequin:'옆구리·다리의 큰 무늬',bicolor:'두 가지 톤',pinstripe:'등을 따라 이어지는 가는 선',brindle:'불규칙하게 끊긴 줄무늬',dalmatian:'점박이 무늬'} as const;
const traits={none:'',tricolor:'세 가지 색',white_spot:'흰 점무늬',lilly_white:'넓게 이어진 흰색 무늬',halloween:'주황·붉은색·검정 대비',super_dalmatian:'촘촘한 점무늬',extreme_harlequin:'몸과 다리를 덮는 넓은 무늬',axanthic:'무채색 몸'} as const;
export const MORPHS=MORPH_CATALOG.map(m=>({id:m.id,name:m.nameKo,color:colors[m.color][0],pattern:traits[m.trait]||patterns[m.pattern],rarity:rarityNames[m.rarity],weight:Math.round(m.hatchRate*100),swatch:colors[m.color][1],description:m.descriptionKo,patternId:m.pattern,traitId:m.trait}));

const LEGACY_MORPHS = [
 {id:'patternless',name:'브라운 패턴리스',color:'브라운',pattern:'무늬 없음',rarity:'일반',weight:3000,swatch:'#94633c'},
 {id:'flame',name:'오렌지 플레임',color:'오렌지',pattern:'밝은 등 무늬',rarity:'일반',weight:2400,swatch:'#e58d3c'},
 {id:'tiger',name:'옐로 타이거',color:'옐로',pattern:'짙은 세로 줄무늬',rarity:'고급',weight:1800,swatch:'#ddc257'},
 {id:'dalmatian',name:'크림 달마시안',color:'크림',pattern:'검은 점박이',rarity:'고급',weight:1200,swatch:'#efe1b7'},
 {id:'harlequin',name:'레드 할리퀸',color:'레드',pattern:'옆구리·다리의 크림 무늬',rarity:'희귀',weight:800,swatch:'#b34e3d'},
 {id:'tricolor',name:'트라이컬러',color:'브라운·오렌지·크림',pattern:'세 가지 색의 큰 무늬',rarity:'희귀',weight:500,swatch:'#795237'},
 {id:'lilywhite',name:'릴리 화이트',color:'아이보리',pattern:'넓은 흰색 무늬',rarity:'영웅',weight:250,swatch:'#f4efe3'},
 {id:'axanthic',name:'실버 아잔틱',color:'실버·차콜',pattern:'무채색 몸과 밝은 등',rarity:'전설',weight:50,swatch:'#8a949b'},
] as const;
export type CatalogMorphId=typeof MORPH_CATALOG[number]['id'];
export type MorphId=CatalogMorphId|typeof LEGACY_MORPHS[number]['id'];
// Resolve the original names without rewriting or rerolling saved creatures.
export const LEGACY_MORPH_IDS:Partial<Record<MorphId,CatalogMorphId>>={patternless:'cre_009',flame:'cre_002',dalmatian:'cre_020',harlequin:'cre_014',tricolor:'cre_021',lilywhite:'cre_023',axanthic:'cre_034'};
export function canonicalMorphId(id?:string):CatalogMorphId|undefined {
 if(MORPHS.some(m=>m.id===id))return id as CatalogMorphId;
 return LEGACY_MORPH_IDS[id as MorphId];
}
export const morphOf=(id?:string)=>MORPHS.find(m=>m.id===canonicalMorphId(id))??LEGACY_MORPHS.find(m=>m.id===id)??MORPHS[1];
export function drawMorph(roll:number):CatalogMorphId {if(!Number.isFinite(roll)||roll<0||roll>=1)throw Error('Invalid random draw');let mark=roll*10000;for(const morph of MORPHS){if(mark<morph.weight)return morph.id;mark-=morph.weight;}return MORPHS[MORPHS.length-1].id;}
export type Creature={id:string;name:string;phase:'egg'|'hatched';morphId?:MorphId;incubation:number;hatchedAt?:number;food:number;moisture:number;clean:number;happy:number;xp:number;born:number;updated:number;lastCare:number;lastAction:string;careCount:number};
export type Pet=Creature & {version:2;nursery:Creature[]};
export type Action='feed'|'mist'|'clean'|'play'|'save'|'rename'|'warm'|'hatch'|'newEgg'|'select';
export const stageOf=(xp:number)=>xp>=240?2:xp>=80?1:0;
export const stageNames=['베이비','아성체','성체'];
export function newPet(now:number):Pet{return {version:2,nursery:[],id:'cre-'+now.toString(36),name:'새로운 알',phase:'egg',incubation:0,food:68,moisture:62,clean:75,happy:70,xp:0,born:now,updated:now,lastCare:0,lastAction:'새로운 알이 도착했어요.',careCount:0};}
export function normalizePet(raw:Pet,now:number):Pet {if(raw.version===2)return raw;const old={...raw,id:'first-cre',phase:'hatched' as const,morphId:'flame' as const,incubation:100,hatchedAt:raw.born};const fresh=newPet(now);fresh.nursery=[old];return fresh;}
export function advance(p:Pet,now:number):Pet {
 const mins=Math.max(0,(now-p.updated)/60000);
 if(p.phase==='egg')return {...p,incubation:Math.min(100,p.incubation+mins*(100/3)),updated:Math.max(now,p.updated)};
 const active=Math.min(mins,120,Math.max(0,(Math.min(p.food,p.moisture,p.clean)-25)/0.35));
 const clamp=(n:number)=>Math.max(10,Math.min(100,n));
 return {...p,food:clamp(p.food-mins*0.35),moisture:clamp(p.moisture-mins*0.3),clean:clamp(p.clean-mins*0.18),happy:clamp(p.happy-mins*0.15),xp:Math.min(240,p.xp+active*0.8),updated:Math.max(now,p.updated)};
}
function snapshot(p:Pet):Creature {const {nursery,version,...creature}=p;void nursery;void version;return creature;}
export function care(p:Pet,action:Action,now:number,value?:string,roll?:number):{pet:Pet;message:string} {
 let n=advance(p,now);const result=(message:string)=>({pet:n,message});
 if(action==='select'){const found=n.nursery.find(c=>c.id===value);if(!found)return result('해당 크레를 찾지 못했어요.');n={...found,updated:now,version:2,nursery:[snapshot(n),...n.nursery.filter(c=>c.id!==value)]};return result(found.phase==='egg'?'알을 다시 돌봐요.':`${found.name}와 다시 함께해요.`);}
 if(action==='newEgg'){if(n.phase==='egg')return result('지금 돌보고 있는 알부터 부화시켜 주세요.');n={...newPet(now),nursery:[snapshot(n),...n.nursery]};return result('어떤 크레를 만나게 될까요?');}
 if(action==='rename'){n.name=(value??'').trim().slice(0,12)||p.name;return result('새 이름을 기억했어요.');}
 if(action==='save')return result('성장 기록을 저장했어요.');
 if(action==='hatch'){
  if(n.phase!=='egg')return result('이미 부화한 크레예요.');
  if(n.incubation<100)return result('아직 부화 준비 중이에요. 알을 조금 더 돌봐 주세요.');
  if(roll===undefined)throw Error('Hatching requires server randomness');
  const morphId=drawMorph(roll);n={...n,phase:'hatched',morphId,hatchedAt:now,name:'아기 크레',xp:0,lastCare:now,lastAction:`${morphOf(morphId).name}가 태어났어요!`};return result(n.lastAction);
 }
 if(now-p.lastCare<3000)return result('잠깐! 돌봄을 즐기고 있어요.');
 if(n.phase==='egg'){
  if(!['warm','mist','clean'].includes(action))return result('알은 온기·분무·청소로 돌봐 주세요.');
  if(n.incubation>=100)return result('준비가 끝났어요! 부화하기를 눌러 주세요.');
  n={...n,incubation:Math.min(100,n.incubation+12),lastCare:now,careCount:n.careCount+1,lastAction:action==='warm'?'알에 따뜻한 온기를 전했어요.':action==='mist'?'알 주변이 촉촉해졌어요.':'알 주변을 깨끗하게 했어요.'};return result(n.lastAction);
 }
 if(action==='warm')return result('부화한 크레에게 먹이를 줘 보세요.');
 const key=({feed:'food',mist:'moisture',clean:'clean',play:'happy'} as const)[action];
 if(n[key]>=95)return result(({feed:'아직 배가 불러요.',mist:'아직 충분히 촉촉해요.',clean:'사육장이 이미 깨끗해요.',play:'지금은 잠깐 쉬고 싶어요.'})[action]);
 n={...n,[key]:Math.min(100,n[key]+28),xp:Math.min(240,n.xp+10),lastCare:now,careCount:n.careCount+1};
 n.lastAction=({feed:'냠냠, 맛있게 먹었어요!',mist:'촉촉해져서 기분이 좋아요.',clean:'사육장이 반짝반짝해요!',play:'함께 놀아서 행복해요!'})[action];return result(n.lastAction);
}
