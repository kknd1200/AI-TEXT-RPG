create table if not exists public.cre_account_recovery (
  user_id uuid primary key references public.cre_accounts(id) on delete cascade,
  username text not null unique,
  recovery_hash text not null,
  failed_attempts integer not null default 0 check (failed_attempts >= 0),
  locked_until timestamptz,
  updated_at timestamptz not null default now()
);

alter table public.cre_account_recovery enable row level security;
revoke all on public.cre_account_recovery from anon, authenticated;
