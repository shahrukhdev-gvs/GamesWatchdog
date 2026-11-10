# Play Store Watchdog — project brief

Streamlit dashboard + GitHub Actions monitors that trace Google Play developer
accounts and watch them for changes. Read this before changing anything.

## Stack

| Piece | Where it runs |
|---|---|
| `dashboard.py` | Streamlit Cloud — `gamebuzztracker.streamlit.app`, auto-deploys from `main` |
| `monitor.py` | GitHub Actions, every 2 hours (`monitor.yml`) — competitors / watchlist |
| `monitor_own_accounts.py` | GitHub Actions, every 30 min (`monitor_own_accounts.yml`) — our own accounts |
| `auth.py` | Supabase Auth helpers (usernames map to `<username>@watchdog.local`) |
| `firebase_analytics.py` | Google Analytics 4 reader for the Firebase tab |
| `trace.py`, `backfill_titles.py` | One-off scripts |
| Database | Supabase (Postgres + Auth + RLS) |

**The repo is public.** Never commit `.env`, `.streamlit/secrets.toml`, or a
Google service-account JSON. Keys live in Streamlit Secrets and GitHub Secrets.

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

## Migrations

Numbered `.sql` files, run by hand in the Supabase SQL editor, in order.
02–07, 09, 10, 11, 13, 14 are applied. 15/16 (babar team backfill) were written
but turned out to be unnecessary. New changes get the next number and must be
safe to run twice (`if not exists`, `drop policy if exists` before `create`).

## External APIs

- **AppstoreSpy** — `POST https://api.appstorespy.com/v1/play/apps/query`, header
  `API-KEY`. `filter.category_type` accepts **only `GAME` or `APP`**. Both
  searches also send `published: true`, plus `pre_register` when ticked.
- **Google Analytics 4** — one service account, key in Streamlit secrets under
  `[gcp_service_account]`. `firebase_analytics.py` resolves package name →
  GA4 property via the Admin API, then reads the Data API. Per-team keys are
  supported: `FIREBASE_KEYS` maps a username to its own secrets section and
  falls back to the shared key when that section is absent.
- **Play Store pages** are scraped with `requests` + BeautifulSoup. Always run
  URLs through `ensure_gl_us()`.

## Conventions

- Times shown to users are Pakistan time (`PKT`, UTC+5); the DB stores UTC.
- `requirements.txt` pins minimum versions — Streamlit Cloud runs Python 3.14,
  and an unpinned `streamlit` resolved to a version that crashed on import.
- Use `width="stretch"`, not the deprecated `use_container_width=True`.
- Tables/selectboxes are plain Streamlit; no custom components.

## Testing without credentials

There is no test suite. The quickest check is Streamlit's `AppTest` with a fake
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
