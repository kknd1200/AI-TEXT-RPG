import {supabase} from '../lib/supabase'

async function postAccount(payload){
  const r=await fetch('/api/cre-account',{
    method:'POST',
    headers:{'content-type':'application/json'},
    body:JSON.stringify(payload)
  })
  const body=await r.json().catch(()=>({error:'응답을 읽지 못했어요.'}))
  if(!r.ok) throw new Error(body.error||'계정 요청에 실패했어요.')
  return body
}

export async function account(action,username,password){
  const body=await postAccount({action,username,password})
  const {error}=await supabase.auth.setSession({access_token:body.access_token,refresh_token:body.refresh_token})
  if(error) throw error
  return body
}

export async function resetPassword(username,recoveryCode,newPassword){
  return postAccount({action:'reset',username,recoveryCode,newPassword})
}

export async function logout(){await supabase.auth.signOut()}
