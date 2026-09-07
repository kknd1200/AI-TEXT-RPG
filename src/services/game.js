import {supabase} from '../lib/supabase'
export async function loadGame(){
  const {data:{user}}=await supabase.auth.getUser();if(!user)return null
  const [{data:state,error:sErr},{data:geckos,error:gErr},{data:morphs,error:mErr}]=await Promise.all([
    supabase.from('cre_player_state').select('*').eq('user_id',user.id).maybeSingle(),
    supabase.from('cre_owned_geckos').select('*, cre_morphs(*)').eq('user_id',user.id).order('hatched_at',{ascending:false}),
    supabase.from('cre_morphs').select('*').eq('active',true).order('display_order')
  ])
  if(sErr)throw sErr;if(gErr)throw gErr;if(mErr)throw mErr
  return {user,state,geckos:geckos||[],morphs:morphs||[]}
}
export async function hatch(){const {data,error}=await supabase.rpc('cre_hatch');if(error)throw new Error(error.message.includes('no eggs')?'부화할 알이 없어요.':error.message);return data?.[0]}
export async function setActiveGecko(id){const {data,error}=await supabase.rpc('cre_set_active_gecko',{p_gecko_id:id});if(error)throw error;return data}
export async function careAction(action){const {data,error}=await supabase.rpc('cre_care_action',{p_action:action});if(error)throw new Error(error.message.includes('no active gecko')?'먼저 알을 부화해 크레를 만나보세요.':error.message);return data?.[0]}
