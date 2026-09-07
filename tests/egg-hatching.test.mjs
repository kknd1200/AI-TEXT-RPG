import assert from 'node:assert/strict';
import test from 'node:test';
import {MORPHS,newPet,normalizePet,advance,care,drawMorph} from '../supabase/functions/_shared/pet.ts';
const start=200000;
test('weighted intervals total 100%, exactly match advertised odds, and reject invalid rolls',()=>{
 assert.equal(MORPHS.reduce((s,m)=>s+m.weight,0),10000);
 const count=Object.fromEntries(MORPHS.map(m=>[m.id,0]));
 for(let i=0;i<10000;i++)count[drawMorph((i+.5)/10000)]++;
 for(const m of MORPHS)assert.equal(count[m.id],m.weight);
 assert.throws(()=>drawMorph(-1));assert.throws(()=>drawMorph(1));assert.throws(()=>drawMorph(NaN));
});
test('new saves start as eggs; no phenotype before ready; timed incubation and care accelerate hatch',()=>{
 const egg=newPet(start);assert.equal(egg.phase,'egg');assert.equal(egg.morphId,undefined);
 const early=care(egg,'hatch',start+1000,undefined,.999).pet;assert.equal(early.phase,'egg');assert.equal(early.morphId,undefined);
 const cared=care(egg,'warm',start+4000).pet;assert(cared.incubation>12);
 const fast=care(cared,'mist',start+5000).pet;assert.equal(fast.careCount,cared.careCount);
 assert.equal(advance(egg,start+180000).incubation,100);
 assert.equal(care(egg,'feed',start+4000).pet.careCount,0);
});
test('hatch persists one result through JSON reload and subsequent hatch requests',()=>{
 const born=care(newPet(start),'hatch',start+180000,undefined,.999).pet;
 assert.equal(born.phase,'hatched');assert.equal(born.morphId,'axanthic');
 const loaded=JSON.parse(JSON.stringify(born));
 const repeated=care(loaded,'hatch',start+200000,undefined,0).pet;
 assert.equal(repeated.morphId,'axanthic');assert.equal(repeated.id,born.id);
 assert.equal(repeated.hatchedAt,born.hatchedAt);
});
test('new egg preserves old pet, switching preserves egg progress, archived pets pause',()=>{
 let grown=care(newPet(start),'hatch',start+180000,undefined,.31).pet;
 grown={...grown,name:'보물',xp:105};
 const next=care(grown,'newEgg',start+190000).pet;
 assert.equal(next.phase,'egg');assert.equal(next.nursery[0].xp,advance(grown,start+190000).xp);assert.equal(next.nursery[0].name,'보물');
 const selected=care(next,'select',start+200000,grown.id).pet;
 assert.equal(selected.id,grown.id);assert.equal(selected.nursery[0].id,next.id);assert(selected.nursery[0].incubation>0);
 const back=care(selected,'select',start+900000,next.id).pet;
 assert.equal(back.incubation,selected.nursery[0].incubation);
 assert.equal(new Set([back.id,...back.nursery.map(p=>p.id)]).size,2);
});
test('legacy save converts to an egg without losing the original gecko',()=>{
 const legacy={name:'모찌',food:70,moisture:60,clean:60,happy:50,xp:180,born:start,updated:start,lastCare:0,lastAction:'기록',careCount:8};
 const result=normalizePet(legacy,start+900000);
 assert.equal(result.phase,'egg');assert.equal(result.nursery[0].name,'모찌');assert.equal(result.nursery[0].xp,180);assert.equal(result.nursery[0].careCount,8);
 assert.deepEqual(normalizePet(result,start+999999),result);
});
