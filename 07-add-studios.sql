-- =========================================================
-- Migration: Multi-studio support
-- IMPORTANT: change 'My Studio' below to your actual studio name
-- before running this.
-- =========================================================

-- 1. Create the studios table
create table studios (
    id bigint generated always as identity primary key,
    name text unique not null,
    notes text,
    created_at timestamptz default now()
);

-- 2. Create your first studio (wraps all existing data)
--    >>> CHANGE 'My Studio' TO YOUR STUDIO NAME <<<
insert into studios (name) values ('My Studio');

-- 3. Add studio_id to ad_network_ids and developers
alter table ad_network_ids add column studio_id bigint references studios(id);
alter table developers add column studio_id bigint references studios(id);

-- 4. Assign all existing ad IDs and developers to that first studio
update ad_network_ids
set studio_id = (select id from studios where name = 'My Studio')
where studio_id is null;

update developers
set studio_id = (select id from studios where name = 'My Studio')
where studio_id is null and source != 'own_account';

-- 5. Enforce global uniqueness of account_id across all studios
--    (drops the old per-network unique constraint, adds a global one)
alter table ad_network_ids drop constraint if exists ad_network_ids_network_account_id_key;
alter table ad_network_ids add constraint ad_network_ids_account_id_unique unique (account_id);

-- 6. Helpful indexes
create index idx_ad_network_ids_studio on ad_network_ids(studio_id);
create index idx_developers_studio on developers(studio_id);
