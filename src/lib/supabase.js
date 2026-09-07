import { createClient } from '@supabase/supabase-js'
const url=import.meta.env.VITE_SUPABASE_URL||'https://buapfwbukpremwaksahr.supabase.co'
const key=import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY||'sb_publishable_BJOfOKFAjZBiuD2oywCglQ_iO4aAyuI'
export const supabase=createClient(url,key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:false}})
