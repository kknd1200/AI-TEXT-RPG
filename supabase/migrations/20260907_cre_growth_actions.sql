create or replace function public.cre_care_action(p_action text)
returns table (gecko_id uuid,action text,care jsonb,growth_xp integer,stage text)
language plpgsql security definer set search_path='' as $$
declare v_user uuid:=auth.uid();v_gecko uuid;v_care jsonb;v_xp integer;v_stage text;v_gain integer;v_key text;v_add integer;
begin
 if v_user is null then raise exception 'authentication required';end if;
 select active_gecko_id,care into v_gecko,v_care from public.cre_player_state where user_id=v_user for update;
 if v_gecko is null then raise exception 'no active gecko';end if;
 case p_action when 'feed' then v_key:='satiety';v_add:=12;v_gain:=8;when 'spray' then v_key:='humidity';v_add:=12;v_gain:=5;when 'clean' then v_key:='clean';v_add:=14;v_gain:=7;when 'play' then v_key:='happy';v_add:=10;v_gain:=10;else raise exception 'invalid care action';end case;
 v_care:=jsonb_set(coalesce(v_care,'{}'::jsonb),array[v_key],to_jsonb(least(100,coalesce((v_care->>v_key)::integer,0)+v_add)),true);
 update public.cre_player_state set care=v_care,last_seen_at=now(),updated_at=now() where user_id=v_user;
 update public.cre_owned_geckos set growth_xp=least(100,growth_xp+v_gain),stage=case when growth_xp+v_gain>=100 then 'adult' else stage end,updated_at=now() where id=v_gecko and user_id=v_user returning growth_xp,stage into v_xp,v_stage;
 return query select v_gecko,p_action,v_care,v_xp,v_stage;
end;$$;
revoke all on function public.cre_care_action(text) from public,anon;
grant execute on function public.cre_care_action(text) to authenticated;
