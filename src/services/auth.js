import {supabase} from '../lib/supabase'
export async function account(action,username,password){
  const r=await fetch('/api/cre-account',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action,username,password})})
  const body=await r.json().catch(()=>({error:'응답을 읽지 못했어요.'}))
  if(!r.ok) throw new Error(body.error||'계정 요청에 실패했어요.')
  const {error}=await supabase.auth.setSession({access_token:body.access_token,refresh_token:body.refresh_token})
  if(error) throw error
}
export async function logout(){await supabase.auth.signOut()}
