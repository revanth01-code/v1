-- backend/app/db/migrations/002_profile.sql

create table financial_profile (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) not null unique,
  monthly_income numeric not null default 0,
  monthly_expenses numeric not null default 0,
  existing_savings numeric not null default 0,
  existing_investments numeric not null default 0,
  dependents int not null default 0,
  employment_type text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Enable Row Level Security — without this, RLS is off by default and
-- ANY authenticated user could read/write ANY row. This line is the
-- single most important line in this file.
alter table financial_profile enable row level security;

-- A user can only see their own profile row
create policy "Users can view own profile"
  on financial_profile for select
  using (auth.uid() = user_id);

-- A user can only insert a profile row for themselves
create policy "Users can insert own profile"
  on financial_profile for insert
  with check (auth.uid() = user_id);

-- A user can only update their own profile row
create policy "Users can update own profile"
  on financial_profile for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Keep updated_at fresh automatically on every update
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger financial_profile_set_updated_at
  before update on financial_profile
  for each row
  execute function set_updated_at();