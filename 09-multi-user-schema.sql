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
