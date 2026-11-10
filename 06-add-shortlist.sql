-- Adds a shortlist flag so games can be checked/starred without leaving the Watchlist
alter table apps add column shortlisted boolean default false;
