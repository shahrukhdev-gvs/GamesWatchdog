-- Adds the separate "My Accounts" Slack channel.
-- Run this if you already ran 09-multi-user-schema.sql before this column existed.
-- Safe to run either way.

alter table user_settings
    add column if not exists slack_webhook_url_own text;

comment on column user_settings.slack_webhook_url     is 'Watchlist / competitor tracking channel (2-hour monitor)';
comment on column user_settings.slack_webhook_url_own is 'Own accounts channel (30-min monitor). Falls back to slack_webhook_url if null.';
