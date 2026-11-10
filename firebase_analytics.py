"""Google Analytics 4 (Firebase Analytics) reader for the Firebase tab.

Each team has its OWN Google Cloud service account (created with that team's
own Gmail), stored in Streamlit secrets under its own section, e.g.
[gcp_service_account] for GamBuzz and [gcp_service_account_nabeel] for NovaBolt.
No single Google identity can read more than one team's Analytics.
Each service account only needs "Viewer" in that team's Google Analytics.

Flow:
  package name --(Analytics Admin API)--> GA4 property + Android data stream
  property + stream --(Analytics Data API)--> daily users / sessions / sources
  property + stream --(cohort report)--> Day 1 / 3 / 7 retention
"""

from datetime import date, timedelta

import streamlit as st

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
ADMIN = "https://analyticsadmin.googleapis.com/v1beta"
DATA = "https://analyticsdata.googleapis.com/v1beta"

# GA4 default channel groups that mean "someone paid for this user".
PAID_CHANNELS = {
    "Paid Search", "Paid Social", "Paid Video", "Paid Shopping", "Paid Other",
    "Display", "Cross-network", "Audio", "Affiliates",
}


class GAError(Exception):
    pass


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

DEFAULT_KEY = "gcp_service_account"


def is_configured(key=DEFAULT_KEY):
    try:
        return key in st.secrets
    except Exception:
        return False


def service_account_email(key=DEFAULT_KEY):
    try:
        return st.secrets[key].get("client_email")
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def _session(key=DEFAULT_KEY):
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession

    if not is_configured(key):
        raise GAError(
            f"Missing **[{key}]** in Streamlit secrets. "
            "Paste that team's service account JSON key there (see setup guide)."
        )
    info = dict(st.secrets[key])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return AuthorizedSession(creds)


def _call(method, url, key=DEFAULT_KEY, **kwargs):
    resp = _session(key).request(method, url, timeout=30, **kwargs)
    if resp.status_code >= 400:
        try:
            msg = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            msg = resp.text
        if resp.status_code == 403 and "has not been used" in msg:
            msg += " → Enable this API in Google Cloud Console, wait 2 minutes, retry."
        raise GAError(f"Google API {resp.status_code}: {msg}")
    return resp.json()


# ---------------------------------------------------------------------------
# Package name -> GA4 property + stream
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def android_stream_index(key=DEFAULT_KEY):
    """{package_name: {property_id, property_name, stream_id, app_id}} for every
    Android stream the service account can see. Cached for an hour."""
    index = {}
    page_token = None
    properties = []
    while True:
        params = {"pageSize": 200}
        if page_token:
            params["pageToken"] = page_token
        data = _call("GET", f"{ADMIN}/accountSummaries", key, params=params)
        for acc in data.get("accountSummaries", []):
            for prop in acc.get("propertySummaries", []):
                properties.append((prop["property"], prop.get("displayName", "")))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    for prop_path, prop_name in properties:
        token = None
        while True:
            params = {"pageSize": 200}
            if token:
                params["pageToken"] = token
            try:
                data = _call("GET", f"{ADMIN}/{prop_path}/dataStreams", key, params=params)
            except GAError:
                break  # one inaccessible property shouldn't break the rest
            for s in data.get("dataStreams", []):
                android = s.get("androidAppStreamData")
                if not android or not android.get("packageName"):
                    continue
                index[android["packageName"].lower()] = {
                    "property_id": prop_path.split("/")[-1],
                    "property_name": prop_name,
                    "stream_id": s["name"].split("/")[-1],
                    "app_id": android.get("firebaseAppId"),
                }
            token = data.get("nextPageToken")
            if not token:
                break
    return index


def find_stream(package_name, refresh=False, key=DEFAULT_KEY):
    """-> (link_dict or None, error_message or None)"""
    if not is_configured(key):
        return None, f"This team's Google key isn't set up yet — add [{key}] to Streamlit secrets."
    try:
        if refresh:
            android_stream_index.clear()
        link = android_stream_index(key).get(package_name.lower())
        if not link and not refresh:
            # The index is cached for an hour; a game set up in Firebase since
            # then won't be in it yet, so look again with a fresh copy.
            android_stream_index.clear()
            link = android_stream_index(key).get(package_name.lower())
    except GAError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Could not reach Google Analytics: {e}"
    if not link:
        who = service_account_email(key) or "the service account"
        return None, (f"No GA4 Android stream for `{package_name}` is visible to {who}. "
                      "Add that email as Viewer on the game's GA4 property (or account).")
    return link, None


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def _run_report(property_id, stream_id, start, end, dimensions, metrics, limit=10000,
                key=DEFAULT_KEY):
    body = {
        "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
        "dimensions": [{"name": d} for d in dimensions],
        "metrics": [{"name": m} for m in metrics],
        "limit": limit,
        "keepEmptyRows": False,
    }
    if stream_id:
        body["dimensionFilter"] = {"filter": {
            "fieldName": "streamId", "stringFilter": {"value": str(stream_id)}}}
    data = _call("POST", f"{DATA}/properties/{property_id}:runReport", key, json=body)

    rows = []
    for r in data.get("rows", []):
        row = {}
        dim_values = r.get("dimensionValues", [])
        for i, d in enumerate(dimensions):
            # Missing values shouldn't happen, but a short row must not crash the tab.
            val = dim_values[i].get("value") if i < len(dim_values) else None
            if d == "date" and val and len(val) == 8:
                val = f"{val[:4]}-{val[4:6]}-{val[6:]}"
            row[d] = val
        for m, v in zip(metrics, r.get("metricValues", [])):
            try:
                row[m] = float(v.get("value") or 0)
            except ValueError:
                row[m] = 0.0
        rows.append(row)
    return rows


DAILY_METRICS = [
    "activeUsers", "newUsers", "totalUsers", "sessions", "engagedSessions",
    "averageSessionDuration", "userEngagementDuration", "engagementRate",
    "screenPageViews", "eventCount",
]


@st.cache_data(ttl=600, show_spinner=False)
def game_report(property_id, stream_id, end_iso, days, key=DEFAULT_KEY):
    """Everything the detail view needs, for `days` days ending on end_iso.
    Cached 10 minutes per game/date so clicking around is cheap."""
    end = date.fromisoformat(end_iso)
    start = end - timedelta(days=max(days, 2) - 1)

    daily = _run_report(property_id, stream_id, start, end, ["date"], DAILY_METRICS, key=key)
    channels = _run_report(property_id, stream_id, start, end,
                           ["date", "firstUserDefaultChannelGroup"],
                           ["newUsers", "activeUsers"], key=key)
    campaigns = _run_report(property_id, stream_id, start, end,
                            ["date", "firstUserCampaignName", "firstUserSource"],
                            ["newUsers", "activeUsers"], key=key)
    countries = _run_report(property_id, stream_id, start, end,
                            ["date", "country"], ["activeUsers", "newUsers"], key=key)
    return {"daily": daily, "channels": channels,
            "campaigns": campaigns, "countries": countries}


def is_paid(channel):
    return (channel or "") in PAID_CHANNELS


# ---------------------------------------------------------------------------
# Retention (GA4 cohort report)
# ---------------------------------------------------------------------------

RETENTION_DAYS = (1, 3, 7)
# Cohorts fetched: one per install day, far enough back for Day 7 of the selected
# day AND of the day before it (for the "vs previous day" arrow).
_COHORT_LOOKBACK = max(RETENTION_DAYS) + 1


def _cohort_body(cohort_days, stream_id):
    body = {
        "dimensions": [{"name": "cohort"}, {"name": "cohortNthDay"}],
        "metrics": [{"name": "cohortActiveUsers"}, {"name": "cohortTotalUsers"}],
        "cohortSpec": {
            "cohorts": [{
                "name": d.isoformat(),
                "dimension": "firstSessionDate",
                "dateRange": {"startDate": d.isoformat(), "endDate": d.isoformat()},
            } for d in cohort_days],
            "cohortsRange": {"granularity": "DAILY", "startOffset": 0,
                             "endOffset": max(RETENTION_DAYS)},
        },
        "limit": 1000,
    }
    if stream_id:
        body["dimensionFilter"] = {"filter": {
            "fieldName": "streamId", "stringFilter": {"value": str(stream_id)}}}
    return body


def _parse_cohorts(data):
    """GA4 cohort rows -> {install_day_iso: {"users": n, "days": {N: active_on_day_N}}}"""
    out = {}
    for r in data.get("rows", []):
        dims = [d.get("value") for d in r.get("dimensionValues", [])]
        mets = [m.get("value") for m in r.get("metricValues", [])]
        if len(dims) < 2 or len(mets) < 2:
            continue
        try:
            nth, active, total = int(dims[1]), float(mets[0] or 0), float(mets[1] or 0)
        except (TypeError, ValueError):
            continue
        c = out.setdefault(dims[0], {"users": 0.0, "days": {}})
        c["users"] = max(c["users"], total)
        c["days"][nth] = c["days"].get(nth, 0.0) + active
    return out


def fetch_retention(property_id, stream_id, end_iso, key=DEFAULT_KEY):
    """Install-day cohorts for the days before end_iso, each with the number of
    its users active on day 0..7 after install.

    -> {"cohorts": {...see _parse_cohorts...}, "all_streams": bool}
    all_streams is True if GA4 refused the Android-stream filter on a cohort
    report and the numbers therefore cover every stream in the property."""
    end = date.fromisoformat(end_iso)
    days = [end - timedelta(days=n) for n in range(1, _COHORT_LOOKBACK + 1)]
    url = f"{DATA}/properties/{property_id}:runReport"
    try:
        data = _call("POST", url, key, json=_cohort_body(days, stream_id))
        return {"cohorts": _parse_cohorts(data), "all_streams": False}
    except GAError as e:
        if not stream_id or "Google API 400" not in str(e):
            raise
    data = _call("POST", url, key, json=_cohort_body(days, None))
    return {"cohorts": _parse_cohorts(data), "all_streams": True}


retention_report = st.cache_data(ttl=600, show_spinner=False)(fetch_retention)


def retention(cohorts, n, as_of):
    """Day-n retention as of a calendar day: of the users who first opened the
    game n days before as_of, the share who were active on as_of.

    -> (percent or None, install_day, cohort_users, users_back)"""
    install_day = as_of - timedelta(days=n)
    c = cohorts.get(install_day.isoformat())
    if not c or not c["users"]:
        return None, install_day, 0, 0
    back = c["days"].get(n, 0.0)
    return back / c["users"] * 100, install_day, int(c["users"]), int(back)