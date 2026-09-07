import fs from 'node:fs/promises'
import {createClient} from '@supabase/supabase-js'
const url=process.env.SUPABASE_URL,key=process.env.SUPABASE_SECRET_KEY
if(!url||!key)throw new Error('SUPABASE_URL / SUPABASE_SECRET_KEY required')
const src=JSON.parse(await fs.readFile(new URL('../src/data/morphs.json',import.meta.url),'utf8'))
const rows=src.morphs.map(m=>({id:m.id,display_order:m.displayOrder,name_ko:m.nameKo,name_en:m.nameEn,description_ko:m.descriptionKo,rarity:m.rarity,hatch_rate:m.hatchRate,color:m.color,pattern:m.pattern,trait:m.trait,active:true,updated_at:new Date().toISOString()}))
const total=rows.reduce((s,r)=>s+Number(r.hatch_rate),0);if(Math.abs(total-100)>1e-9)throw new Error(`hatch total must be 100, got ${total}`)
const supabase=createClient(url,key,{auth:{persistSession:false}})
const {error}=await supabase.from('cre_morphs').upsert(rows,{onConflict:'id'});if(error)throw error
console.log(`Synced ${rows.length} morphs, total=${total}%`)
