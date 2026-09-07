-- Fix PL/pgSQL output-column name ambiguities found during end-to-end DB testing.

create or replace function public.cre_hatch()
returns table (
  gecko_id uuid, morph_id text, name_ko text, name_en text, rarity text,
  hatch_rate numeric, baby_asset text, adult_asset text, remaining_eggs integer
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_roll numeric;
  v_total numeric;
  v_morph public.cre_morphs%rowtype;
  v_gecko uuid;
  v_eggs integer;
begin
  if v_user is null then raise exception 'authentication required'; end if;
  insert into public.cre_player_state(user_id) values(v_user) on conflict (user_id) do nothing;
  select cps.eggs into v_eggs from public.cre_player_state cps where cps.user_id=v_user for update;
  if coalesce(v_eggs,0) <= 0 then raise exception 'no eggs'; end if;
  select sum(cm.hatch_rate) into v_total from public.cre_morphs cm where cm.active=true;
  if coalesce(v_total, 0) <= 0 then raise exception 'no active morphs'; end if;
  v_roll := pg_catalog.random() * v_total;
  select cm.* into v_morph
  from public.cre_morphs cm
  where cm.id = (
    select ranked.id
    from (
      select cm2.id, sum(cm2.hatch_rate) over(order by cm2.display_order) as cumulative
      from public.cre_morphs cm2
      where cm2.active=true
    ) ranked
    where v_roll < ranked.cumulative
    order by ranked.cumulative
    limit 1
  );
  if v_morph.id is null then
    select cm3.* into v_morph from public.cre_morphs cm3 where cm3.active=true order by cm3.display_order desc limit 1;
  end if;
  insert into public.cre_owned_geckos(user_id,morph_id) values(v_user,v_morph.id) returning id into v_gecko;
  update public.cre_player_state cps
     set eggs=cps.eggs-1, active_gecko_id=coalesce(cps.active_gecko_id,v_gecko), updated_at=now()
   where cps.user_id=v_user
   returning cps.eggs into v_eggs;
  insert into public.cre_hatch_log(user_id,gecko_id,morph_id,roll) values(v_user,v_gecko,v_morph.id,v_roll);
  return query select v_gecko,v_morph.id,v_morph.name_ko,v_morph.name_en,v_morph.rarity,
    v_morph.hatch_rate,v_morph.baby_asset,v_morph.adult_asset,v_eggs;
end;
$$;
revoke all on function public.cre_hatch() from public, anon;
grant execute on function public.cre_hatch() to authenticated;

create or replace function public.cre_care_action(p_action text)
returns table (
  gecko_id uuid,
  action text,
  care jsonb,
  growth_xp integer,
  stage text
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_gecko uuid;
  v_care jsonb;
  v_xp integer;
  v_stage text;
  v_gain integer;
  v_key text;
  v_add integer;
begin
  if v_user is null then raise exception 'authentication required'; end if;
  select cps.active_gecko_id, cps.care into v_gecko, v_care
    from public.cre_player_state cps
   where cps.user_id = v_user
   for update;
  if v_gecko is null then raise exception 'no active gecko'; end if;
  if not exists(select 1 from public.cre_owned_geckos cog where cog.id=v_gecko and cog.user_id=v_user) then
    raise exception 'active gecko ownership mismatch';
  end if;
  case p_action
    when 'feed' then v_key := 'satiety'; v_add := 12; v_gain := 8;
    when 'spray' then v_key := 'humidity'; v_add := 12; v_gain := 5;
    when 'clean' then v_key := 'clean'; v_add := 14; v_gain := 7;
    when 'play' then v_key := 'happy'; v_add := 10; v_gain := 10;
    else raise exception 'invalid care action';
  end case;
  v_care := jsonb_set(coalesce(v_care,'{}'::jsonb),array[v_key],to_jsonb(least(100,coalesce((v_care->>v_key)::integer,0)+v_add)),true);
  update public.cre_player_state cps set care=v_care,last_seen_at=now(),updated_at=now() where cps.user_id=v_user;
  update public.cre_owned_geckos cog
     set growth_xp=least(100,cog.growth_xp+v_gain),
         stage=case when cog.growth_xp+v_gain>=100 then 'adult' else cog.stage end,
         updated_at=now()
   where cog.id=v_gecko and cog.user_id=v_user
   returning cog.growth_xp,cog.stage into v_xp,v_stage;
  return query select v_gecko,p_action,v_care,v_xp,v_stage;
end;
$$;
revoke all on function public.cre_care_action(text) from public,anon;
grant execute on function public.cre_care_action(text) to authenticated;
