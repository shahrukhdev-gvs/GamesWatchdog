-- 14-firebase-games.sql
-- Games tracked in the "Firebase" tab, with their Google Analytics (GA4) link.
--
-- Visibility rules (enforced by the database, not just the app):
--   * shahrukh.gvs / nabeel.gvs / ayesha.gvs see ONLY their own games.
--   * A "firebase manager" (babar.gvs) sees every row and can add/remove
--     games on anyone's behalf.
--   * A package name can exist only ONCE in the whole table, so the same game
--     can't be added twice (not even under two different teams).
--
-- Safe to run more than once.

-- 1. Manager flag on profiles ------------------------------------------------
alter table profiles add column if not exists firebase_manager boolean not null default false;

update profiles set firebase_manager = true where username = 'babar.gvs';

-- Runs with the owner's rights so it can read profiles without tripping RLS
-- (and without recursion when used inside the profiles policy below).
create or replace function is_firebase_manager()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (select firebase_manager from profiles where user_id = auth.uid()),
    false
  );
$$;

grant execute on function is_firebase_manager() to authenticated;

-- Managers need to look up the other users' ids (to label games and to add
-- games for them). Normal users still only see their own profile.
drop policy if exists firebase_manager_reads_profiles on profiles;
create policy firebase_manager_reads_profiles on profiles
  for select using (is_firebase_manager());

-- 2. Games table -------------------------------------------------------------
create table if not exists firebase_games (
  id               bigserial primary key,
  user_id          uuid not null default auth.uid() references auth.users(id) on delete cascade,
  package_name     text not null,
  title            text,
  icon_url         text,
  ga4_property_id  text,          -- e.g. '412345678'
  ga4_property_name text,
  stream_id        text,          -- the Android data stream inside that property
  link_error       text,          -- why linking to GA4 failed, if it did
  added_by         uuid default auth.uid() references auth.users(id) on delete set null,
  created_at       timestamptz not null default now(),
  constraint firebase_games_package_unique unique (package_name)
);

create index if not exists firebase_games_user_idx on firebase_games(user_id);

alter table firebase_games enable row level security;

drop policy if exists firebase_games_select on firebase_games;
create policy firebase_games_select on firebase_games
  for select using (user_id = auth.uid() or is_firebase_manager());

drop policy if exists firebase_games_insert on firebase_games;
create policy firebase_games_insert on firebase_games
  for insert with check (user_id = auth.uid() or is_firebase_manager());

drop policy if exists firebase_games_update on firebase_games;
create policy firebase_games_update on firebase_games
  for update using (user_id = auth.uid() or is_firebase_manager())
  with check (user_id = auth.uid() or is_firebase_manager());

drop policy if exists firebase_games_delete on firebase_games;
create policy firebase_games_delete on firebase_games
  for delete using (user_id = auth.uid() or is_firebase_manager());

-- Lets a normal user find out that a package is already taken by ANOTHER team
-- (so they get a clear message) without being able to see that team's games.
create or replace function firebase_package_taken(pkg text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (select 1 from firebase_games where package_name = pkg);
$$;

grant execute on function firebase_package_taken(text) to authenticated;
