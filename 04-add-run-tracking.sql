-- Adds a run_id so Recent Activity can group changes by which 2-hour check cycle found them
alter table change_log add column run_id text;
alter table change_log add column developer_name text;
alter table change_log add column app_title text;
alter table change_log add column package_name text;

create index idx_changelog_run on change_log(run_id);
