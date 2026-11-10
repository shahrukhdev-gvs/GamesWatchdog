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
