# Play Store Watchdog — project brief

Streamlit dashboard + GitHub Actions monitors that trace Google Play developer
accounts and watch them for changes. Read this before changing anything.

## Stack

| Piece | Where it runs |
|---|---|
| `dashboard.py` | Streamlit Cloud — `gamebuzztracker.streamlit.app`, auto-deploys from `main` |
| `theme.py`, `.streamlit/config.toml` | The dashboard's dark "game studio" look: CSS plus the hero banner, login header and sidebar card |
| `monitor.py` | GitHub Actions (`monitor.yml`), **started by Supabase pg_cron** every 2 hours at :17 UTC — competitors / watchlist |
| `monitor_own_accounts.py` | GitHub Actions (`monitor_own_accounts.yml`), **started by Supabase pg_cron** every 30 min at :07 / :37 UTC — our own accounts |
| `auth.py` | Supabase Auth helpers (usernames map to `<username>@watchdog.local`) |
| `firebase_analytics.py` | Google Analytics 4 reader for the Firebase tab |
| `trace.py`, `backfill_titles.py`, `migrate_to_new_supabase.py` | One-off scripts |
| Database | Supabase (Postgres + Auth + RLS) — the **new** project (see Migrations) |

Repo: `shahrukhdev-gvs/GamesWatchdog` (public, created 10 Nov 2026). The old repo
`Shahrukh-GVS/playstore-watchdog` has both workflows **disabled** — keep them off:
its secrets point at the old database, so re-enabling them would send duplicate
alerts from stale data.

**The repo is public.** Never commit `.env`, `.streamlit/secrets.toml`, or a
Google service-account JSON. Keys live in Streamlit Secrets, GitHub Secrets
and Supabase Vault. Keeping the repo public is also what makes GitHub Actions
minutes unlimited; a private repo would run out on the free plan.

## Users and visibility

Logins: `shahrukh.gvs` (admin), `babar.gvs`, `nabeel.gvs`, `ayesha.gvs`, `adeel.gvs`.

- Every table is row-level-secured on `user_id = auth.uid()`. The dashboard uses
  the signed-in user's anon-key client, so users only see their own rows.
- The monitors use the **service_role** key: RLS is bypassed and `auth.uid()` is
  NULL, so **every insert in a monitor must set `user_id` explicitly.**
- `profiles.firebase_manager` is true for `babar.gvs` only. It lets him see and
  add Firebase games for every team (see `14-firebase-games.sql`).

Two separate grouping concepts, easy to confuse:
- **Studios** (`studios`, `developers.studio_id`) group **ad network IDs** and tag
  traced watchlist accounts.
- **Teams** (`teams`, `developers.team_id`) group **our own accounts** in the
  My Accounts tab. Only usernames in `TEAM_FEATURE_USERS` see the team UI.

Firebase tab team labels live in `FIREBASE_BRANDS` in `dashboard.py`:
shahrukh=GamBuzz, nabeel=NovaBolt, ayesha=Gravity Ayesha, adeel=Gravity Adeel.

## Dashboard tabs

Trace · AppStore Spy · Search by Name · My Accounts · Firebase · Watchlist ·
Shortlisted · Recent Activity · Manage Ad IDs · Settings

## Notifications (current behaviour)

Routing is **per login, not per team**. `user_settings` holds two webhooks per user:

- `slack_webhook_url` — watchlist monitor
- `slack_webhook_url_own` — own-accounts monitor, falls back to the one above

So every own account belonging to one login goes to that login's single channel,
whatever team it is filed under. Per-team routing is **not implemented** — see
Open work below.

Per-event toggles in `user_settings`: `slack_enabled`, `notify_removed`,
`notify_new_upload`, `notify_listing_changed`, `notify_nothing_new`.

Removals are deliberately deferred: `monitor_own_accounts.py` collects
`pending_removals`, sends the Slack digest first, and only writes the `removed`
status after a successful send. Don't "simplify" this — committing first would
silently lose an alert when Slack fails.

With `notify_nothing_new` off, a run that finds no changes sends that user
**nothing** — a quiet channel doesn't by itself mean the monitors stopped.

Duplicate app inserts are non-fatal in both monitors: `insert_app()` catches the
unique violation (23505) per app, logs it and carries on, so one bad row can't
abort a user's run and lose their digest. Keep it that way.

## Scheduling (Supabase pg_cron)

GitHub's own `schedule:` trigger never fired in this repo and dropped most runs
in the old one, so **the workflows have no `schedule:` — don't add it back.**
Supabase starts them on time through the GitHub API:

- Extensions `pg_cron` + `pg_net` (new project).
- Vault secret `github_actions_token`: a fine-grained GitHub token for
  `GamesWatchdog` only, **Actions: Read and write**, set to never expire. If
  it ever leaks, revoke it on GitHub and store a new one with
  `vault.update_secret`. Never put it in a file in this repo; set it in the SQL
  editor (`vault.create_secret` / `vault.update_secret`).
- `private.dispatch_monitor(workflow_file)` — `security definer`, in the
  `private` schema (not exposed by the API), execute revoked from
  `public`/`anon`/`authenticated`. POSTs to `.../actions/workflows/<file>/dispatches`
  with `{"ref": "main"}`.
- Cron jobs: `monitor-own-accounts` (`7,37 * * * *`), `monitor-watchlist`
  (`17 */2 * * *`), `cleanup-cron-history` (`0 3 * * *`, keeps 7 days of
  `cron.job_run_details`). All times UTC.
- Each workflow has a `concurrency` group, so two runs of the same monitor
  never overlap.

Checking it: `cron.job_run_details` says whether each job ran;
`net._http_response` holds GitHub's answer — **204** is success, 401 = token
wrong or expired, 403 = missing Actions permission, 404 = wrong repo/file.
A failed HTTP call still shows as a *succeeded* cron job, so look at
`net._http_response`. On GitHub the runs appear as `workflow_dispatch`.

This setup was run by hand in the SQL editor and isn't in a numbered migration
yet (see Open work).

## Migrations

Numbered `.sql` files, run by hand in the Supabase SQL editor, in order.
New changes get the next number and must be safe to run twice
(`if not exists`, `drop policy if exists` before `create`).

The live database is the **new** Supabase project, built from
`00-new-project-schema.sql` (02, 04, 06, 07, 09, 11, 13, 14 combined), with data
copied from the old project by `migrate_to_new_supabase.py` on 10–11 Nov 2026.
03 (ad-ID seed), 05, 10, 15, 16 were one-off backfills and aren't needed for a
fresh database; 15/16 aren't in the repo. The next new file is **17**.

## External APIs

- **AppstoreSpy** — `POST https://api.appstorespy.com/v1/play/apps/query`, header
  `API-KEY`. `filter.category_type` accepts **only `GAME` or `APP`**. Both
  searches also send `published: true`, plus `pre_register` when ticked.
- **Google Analytics 4** — one service account, key in Streamlit secrets under
  `[gcp_service_account]`. `firebase_analytics.py` resolves package name →
  GA4 property via the Admin API, then reads the Data API. Per-team keys are
  supported: `FIREBASE_KEYS` maps a username to its own secrets section and
  falls back to the shared key when that section is absent.
  Day 1 / 3 / 7 retention comes from a GA4 **cohort report**
  (`fetch_retention`: `firstSessionDate` cohorts, `cohortActiveUsers` ÷
  `cohortTotalUsers`), filtered to the Android stream, falling back to the whole
  property if GA4 rejects that filter. Session and screen-view cards are hidden
  behind `SHOW_SESSION_METRICS = False` in `dashboard.py`.
- **Play Store pages** are scraped with `requests` + BeautifulSoup. Always run
  URLs through `ensure_gl_us()`.

## Conventions

- Times shown to users are Pakistan time (`PKT`, UTC+5); the DB stores UTC.
- `requirements.txt` pins minimum versions — Streamlit Cloud runs Python 3.14,
  and an unpinned `streamlit` resolved to a version that crashed on import.
- Use `width="stretch"`, not the deprecated `use_container_width=True`.
- Tables/selectboxes are plain Streamlit; no custom components. The look comes
  from CSS in `theme.py`, which targets Streamlit's `data-testid` / `role`
  hooks. Streamlit changes its markup between versions (1.6x moved tabs to
  react-aria: `[role="tab"]`, `aria-selected`), so check the page after a
  Streamlit upgrade.

## Testing without credentials

Offline tests, no keys or network needed:

```bash
python -m pytest tests
```

- `tests/test_monitors.py` — both monitors against a fake Supabase that
  enforces the unique index and the 1000-row limit; forces duplicate inserts.
- `tests/test_firebase_retention.py` — the GA4 cohort request, parsing, maths
  and the stream-filter fallback, with `firebase_analytics._call` replaced.

For the dashboard, the quickest check is Streamlit's `AppTest` with a fake
Supabase client and `requests.post` / `firebase_analytics._call` monkeypatched,
which runs the real app end to end offline. Verify changes by running the app,
not only by parsing the file.

## Open work

1. **Per-team Slack webhooks.** Wanted: each team's alerts go to that team's
   channel. Needs a webhook column on `teams`, a UI field in Manage teams, and
   grouping in `monitor_own_accounts.py` so one run sends one digest per team
   (falling back to the user's webhook for accounts with no team).
2. Only GamBuzz's Google Analytics access is set up; other teams still need the
   service account added as Viewer on their GA4 account.
3. **Put the pg_cron setup in `17-schedule-monitors-with-pg-cron.sql`**
   (extensions, `private.dispatch_monitor`, the three `cron.schedule` calls —
   never the token), so a fresh project can be rebuilt from the repo.
4. **Alert when the monitors stop.** Nothing notices today if no run happens
   for hours (the 10–11 Nov outage went unnoticed for a day). Free projects can
   also be paused by Supabase after about a week with no activity.
