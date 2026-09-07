export default async function handler(req,res){
  if(req.method!=='POST') return res.status(405).json({error:'허용되지 않은 요청이에요.'})
  const {action,username,password,recoveryCode,newPassword}=req.body||{}
  const url=(process.env.SUPABASE_URL||'https://buapfwbukpremwaksahr.supabase.co').replace(/\/$/,'')
  const key=process.env.CRE_SERVER_KEY
  if(!key) return res.status(503).json({error:'Vercel의 CRE_SERVER_KEY 설정이 필요해요.'})
  const ip=(req.headers['x-forwarded-for']||req.socket?.remoteAddress||'unknown').toString().split(',')[0].trim().slice(0,80)
  try{
    const r=await fetch(`${url}/functions/v1/cre-account`,{
      method:'POST',
      headers:{'content-type':'application/json','x-cre-server-key':key},
      body:JSON.stringify({action,username,password,recoveryCode,newPassword,clientIp:ip})
    })
    const body=await r.json().catch(()=>({error:'계정 서버 응답 오류'}))
    res.setHeader('Cache-Control','no-store')
    return res.status(r.status).json(body)
  }catch{return res.status(503).json({error:'계정 연결이 원활하지 않아요.'})}
}
