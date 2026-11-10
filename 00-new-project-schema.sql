-- =========================================================
-- Play Store Watchdog — full schema for a BRAND NEW Supabase project
--
-- Combines migrations 02, 04, 06, 07, 09, 11, 13 and 14 in dependency order.
-- Leaves out 03 (ad-ID seed), 05, 10, 15, 16 (one-off backfills) — real data
-- is imported from the old project instead.
--
-- Run once, whole file, in the Supabase SQL editor of the NEW project.
-- Safe to run again: everything is "if not exists" / "or replace".
-- =========================================================



-- =========================================================
-- From 02-schema.sql
-- =========================================================
-- =========================================================
-- Play Store Watchdog — Database Schema
-- Run this once in Supabase SQL Editor
-- =========================================================

-- Developers (Play Store publisher accounts we're tracking)
create table if not exists developers (
    id bigint generated always as identity primary key,
    dev_id text unique,              -- Play Store developer id from URL (?id=...)
    name text,                       -- Developer display name
    developer_url text,              -- Full developer page URL
    source text default 'trace',     -- 'trace' (found via app-ads.txt) or 'transfer' (auto-added via transfer detection)
    first_seen timestamptz default now(),
    last_checked timestamptz
);

-- Apps under watched developers
create table if not exists apps (
    id bigint generated always as identity primary key,
    package_name text unique not null,
    developer_id bigint references developers(id),
    title text,
    icon_url text,
    icon_hash text,                  -- hash of icon image, used to detect icon changes
    installs_bracket text,           -- raw string e.g. "10K+"
    is_pre_registration boolean default false,
    status text default 'active',    -- 'active' | 'removed'
    first_seen timestamptz default now(),
    last_seen timestamptz default now(),
    last_country_checked text        -- which gl= country last confirmed it live
);

-- Master list of YOUR known ad network IDs used for matching app-ads.txt
create table if not exists ad_network_ids (
    id bigint generated always as identity primary key,
    network text not null,           -- e.g. 'google.com' (AdMob), 'applovin.com'
    account_id text not null,        -- e.g. 'pub-XXXXXXXXXXXXXXXX'
    label text,                      -- optional note, e.g. "Main AdMob account"
    unique(network, account_id)
);

-- Log of every detected change, feeds the Discord digest
create table if not exists change_log (
    id bigint generated always as identity primary key,
    app_id bigint references apps(id),
    developer_id bigint references developers(id),
    event_type text not null,        -- 'new_upload' | 'removed' | 'transferred_in' | 'transferred_out' | 'listing_changed'
    old_value jsonb,                 -- e.g. {"title": "Old Name", "icon_url": "..."}
    new_value jsonb,                 -- e.g. {"title": "New Name", "icon_url": "..."}
    notified boolean default false,  -- whether this was already included in a Discord digest
    detected_at timestamptz default now()
);

-- Helpful indexes for the monitor script's lookups
create index if not exists idx_apps_developer on apps(developer_id);
create index if not exists idx_apps_status on apps(status);
create index if not exists idx_changelog_notified on change_log(notified);


-- =========================================================
-- From 04-add-run-tracking.sql
-- =========================================================
-- Adds a run_id so Recent Activity can group changes by which 2-hour check cycle found them
alter table change_log add column if not exists run_id text;
alter table change_log add column if not exists developer_name text;
alter table change_log add column if not exists app_title text;
alter table change_log add column if not exists package_name text;

create index if not exists idx_changelog_run on change_log(run_id);


-- =========================================================
-- From 06-add-shortlist.sql
-- =========================================================
-- Adds a shortlist flag so games can be checked/starred without leaving the Watchlist
alter table apps add column if not exists shortlisted boolean default false;


-- =========================================================
-- From 07-add-studios.sql
-- =========================================================
-- =========================================================
-- Migration: Multi-studio support
-- IMPORTANT: change 'My Studio' below to your actual studio name
-- before running this.
-- =========================================================

-- 1. Create the studios table
create table if not exists studios (
    id bigint generated always as identity primary key,
    name text unique not null,
    notes text,
    created_at timestamptz default now()
);

-- 2. No starter studio is created here: this is a fresh project and the real
--    studios are imported from the old database by the migration script.

-- 3. Add studio_id to ad_network_ids and developers
alter table ad_network_ids add column if not exists studio_id bigint references studios(id);
alter table developers add column if not exists studio_id bigint references studios(id);

-- 4. (Backfill skipped — nothing to assign in an empty database.)

-- 5. Drop the old per-network unique constraint.
--    07 also added a global unique (account_id) constraint here, but 09 below
--    drops it again in favour of per-user uniqueness (uq_adids_user_account).
--    Left out so a re-run can't fail once two users share an account_id.
alter table ad_network_ids drop constraint if exists ad_network_ids_network_account_id_key;

-- 6. Helpful indexes
create index if not exists idx_ad_network_ids_studio on ad_network_ids(studio_id);
create index if not exists idx_developers_studio on developers(studio_id);


-- =========================================================
-- From 09-multi-user-schema.sql
-- =========================================================
-- =========================================================
-- Multi-user migration, part A: schema + RLS
-- Run this FIRST. Your existing data stays put but becomes
-- invisible to logged-in users until part B assigns it to you.
-- =========================================================

-- 1. Profiles: username + admin flag, keyed to auth.users
create table if not exists profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    username text unique not null,
    is_admin boolean default false,
    created_at timestamptz default now()
);

-- 2. Per-user settings (Slack webhook lives here now, not in env vars)
create table if not exists user_settings (
    user_id uuid primary key references auth.users(id) on delete cascade,
    slack_webhook_url text,          -- competitor / watchlist tracking channel
    slack_webhook_url_own text,      -- your own accounts channel (falls back to the above)
    slack_enabled boolean default true,
    notify_new_upload boolean default true,
    notify_removed boolean default true,
    notify_transferred boolean default true,
    notify_listing_changed boolean default true,
    notify_nothing_new boolean default true,
    updated_at timestamptz default now()
);

-- 3. Add user_id to every data table.
--    `default auth.uid()` means inserts stamp themselves automatically —
--    no application code needs to set it.
alter table studios         add column if not exists user_id uuid references auth.users(id) on delete cascade default auth.uid();
alter table ad_network_ids  add column if not exists user_id uuid references auth.users(id) on delete cascade default auth.uid();
alter table developers      add column if not exists user_id uuid references auth.users(id) on delete cascade default auth.uid();
alter table apps            add column if not exists user_id uuid references auth.users(id) on delete cascade default auth.uid();
alter table change_log      add column if not exists user_id uuid references auth.users(id) on delete cascade default auth.uid();

-- 4. Uniqueness becomes per-user.
--    Two users must be able to track the same developer or app independently.
alter table developers      drop constraint if exists developers_dev_id_key;
alter table apps            drop constraint if exists apps_package_name_key;
alter table ad_network_ids  drop constraint if exists ad_network_ids_account_id_unique;
alter table ad_network_ids  drop constraint if exists ad_network_ids_network_account_id_key;
alter table studios         drop constraint if exists studios_name_key;

create unique index if not exists uq_developers_user_dev      on developers(user_id, dev_id);
create unique index if not exists uq_apps_user_package        on apps(user_id, package_name);
create unique index if not exists uq_adids_user_account       on ad_network_ids(user_id, account_id);
create unique index if not exists uq_studios_user_name        on studios(user_id, name);

create index if not exists idx_studios_user     on studios(user_id);
create index if not exists idx_adids_user       on ad_network_ids(user_id);
create index if not exists idx_developers_user  on developers(user_id);
create index if not exists idx_apps_user        on apps(user_id);
create index if not exists idx_changelog_user   on change_log(user_id);

-- 5. Turn RLS on. From here the database itself refuses cross-user reads —
--    isolation no longer depends on the app remembering to filter.
alter table profiles       enable row level security;
alter table user_settings  enable row level security;
alter table studios        enable row level security;
alter table ad_network_ids enable row level security;
alter table developers     enable row level security;
alter table apps           enable row level security;
alter table change_log     enable row level security;

-- 6. Policies: you may only touch your own rows.
drop policy if exists own_profile on profiles;
create policy own_profile on profiles
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists own_settings on user_settings;
create policy own_settings on user_settings
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists own_studios on studios;
create policy own_studios on studios
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists own_adids on ad_network_ids;
create policy own_adids on ad_network_ids
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists own_developers on developers;
create policy own_developers on developers
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists own_apps on apps;
create policy own_apps on apps
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists own_changelog on change_log;
create policy own_changelog on change_log
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Note: the GitHub Actions monitors connect with the service_role key, which
-- bypasses RLS by design. That is correct — they are trusted backend jobs that
-- legitimately need to see every user's data in order to check it.


-- =========================================================
-- From 11-add-second-slack-channel.sql
-- =========================================================
-- Adds the separate "My Accounts" Slack channel.
-- Run this if you already ran 09-multi-user-schema.sql before this column existed.
-- Safe to run either way.

alter table user_settings
    add column if not exists slack_webhook_url_own text;

comment on column user_settings.slack_webhook_url     is 'Watchlist / competitor tracking channel (2-hour monitor)';
comment on column user_settings.slack_webhook_url_own is 'Own accounts channel (30-min monitor). Falls back to slack_webhook_url if null.';


-- =========================================================
-- From 13-add-teams-for-my-accounts.sql
-- =========================================================
-- =========================================================
-- Teams for My Accounts
--
-- Purely additive. Studios are NOT touched — they keep grouping ad IDs and
-- tagging traced watchlist accounts exactly as before. Teams are a separate
-- thing that only files your own Play Console accounts.
--
-- A developer row can therefore carry both: studio_id (how it was traced)
-- and team_id (which of your teams owns it). They never interact.
-- =========================================================

create table if not exists teams (
    id bigint generated always as identity primary key,
    user_id uuid references auth.users(id) on delete cascade default auth.uid(),
    name text not null,
    created_at timestamptz default now()
);

-- Team names unique per user, so two people can both have a "Gambuzz"
create unique index if not exists uq_teams_user_name on teams(user_id, name);
create index if not exists idx_teams_user on teams(user_id);

alter table teams enable row level security;

drop policy if exists own_teams on teams;
create policy own_teams on teams
    for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Deleting a team leaves its accounts in place, just unassigned
alter table developers
    add column if not exists team_id bigint references teams(id) on delete set null;

create index if not exists idx_developers_team on developers(team_id);

-- Confirm studios survived untouched
select
  (select count(*) from studios)  as studios_still_here,
  (select count(*) from teams)    as teams_created,
  (select count(*) from developers where studio_id is not null) as devs_with_studio;


-- =========================================================
-- From 14-firebase-games.sql
-- =========================================================
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
