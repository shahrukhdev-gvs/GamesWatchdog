-- =========================================================
-- Play Store Watchdog — Database Schema
-- Run this once in Supabase SQL Editor
-- =========================================================

-- Developers (Play Store publisher accounts we're tracking)
create table developers (
    id bigint generated always as identity primary key,
    dev_id text unique,              -- Play Store developer id from URL (?id=...)
    name text,                       -- Developer display name
    developer_url text,              -- Full developer page URL
    source text default 'trace',     -- 'trace' (found via app-ads.txt) or 'transfer' (auto-added via transfer detection)
    first_seen timestamptz default now(),
    last_checked timestamptz
);

-- Apps under watched developers
create table apps (
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
create table ad_network_ids (
    id bigint generated always as identity primary key,
    network text not null,           -- e.g. 'google.com' (AdMob), 'applovin.com'
    account_id text not null,        -- e.g. 'pub-XXXXXXXXXXXXXXXX'
    label text,                      -- optional note, e.g. "Main AdMob account"
    unique(network, account_id)
);

-- Log of every detected change, feeds the Discord digest
create table change_log (
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
create index idx_apps_developer on apps(developer_id);
create index idx_apps_status on apps(status);
create index idx_changelog_notified on change_log(notified);
