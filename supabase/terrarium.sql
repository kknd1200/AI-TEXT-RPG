-- Dedicated save format for the pixel terrarium. Existing accounts and RPG tables remain valid.
create table if not exists public.cre_terrarium_saves (
  user_id uuid primary key references public.cre_accounts(id) on delete cascade,
  state jsonb not null check (jsonb_typeof(state) = 'object' and state->>'version' = '2'),
  revision bigint not null default 0 check (revision >= 0),
  updated_at timestamptz not null default now()
);
alter table public.cre_terrarium_saves enable row level security;
revoke all on public.cre_terrarium_saves from public, anon, authenticated;
grant select on public.cre_terrarium_saves to authenticated;
grant all on public.cre_terrarium_saves to service_role;
create policy cre_terrarium_read_own on public.cre_terrarium_saves
  for select to authenticated using ((select auth.uid()) = user_id);
-- Writes pass through cre-terrarium, which verifies membership, calculates growth
-- and rarity on the server, and compares revisions atomically.
