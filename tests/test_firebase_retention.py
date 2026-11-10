"""Offline tests for Day 1 / 3 / 7 retention in firebase_analytics.py.

The Google API call (_call) is replaced, so these check the request we send,
how GA4's cohort rows are read, the maths, and the fallback when GA4 refuses
the Android-stream filter. No Google account or network is used.

    python -m pytest tests/test_firebase_retention.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import firebase_analytics as fa  # noqa: E402


def cohort_rows(cohorts):
    """GA4 runReport shape for a cohort report.
    cohorts: {install_iso: (total_users, {nth_day: active_users})}"""
    rows = []
    for name, (total, days) in cohorts.items():
        for nth, active in days.items():
            rows.append({"dimensionValues": [{"value": name}, {"value": f"{nth:04d}"}],
                         "metricValues": [{"value": str(active)}, {"value": str(total)}]})
    return {"rows": rows}


SEL = date(2026, 11, 10)
DATA = cohort_rows({
    "2026-11-09": (200, {0: 200, 1: 70}),            # Day 1 as of 10 Nov: 35.0%
    "2026-11-08": (100, {0: 100, 1: 40, 2: 30}),     # Day 1 as of  9 Nov: 40.0%
    "2026-11-07": (400, {0: 400, 3: 60}),            # Day 3 as of 10 Nov: 15.0%
    "2026-11-03": (50, {0: 50, 7: 4}),               # Day 7 as of 10 Nov:  8.0%
})


def test_request_asks_for_install_day_cohorts_on_the_android_stream():
    calls = []
    fa_call = fa._call
    fa._call = lambda method, url, key, **kw: calls.append((url, kw["json"])) or DATA
    try:
        out = fa.fetch_retention("123", "456", SEL.isoformat())
    finally:
        fa._call = fa_call
    url, body = calls[0]
    assert url.endswith("/properties/123:runReport")
    assert "dateRanges" not in body  # GA4 rejects dateRanges on cohort reports
    spec = body["cohortSpec"]
    assert [c["name"] for c in spec["cohorts"]] == [f"2026-11-{d:02d}" for d in range(9, 1, -1)]
    assert all(c["dimension"] == "firstSessionDate" for c in spec["cohorts"])
    assert spec["cohortsRange"] == {"granularity": "DAILY", "startOffset": 0, "endOffset": 7}
    assert body["dimensionFilter"]["filter"]["fieldName"] == "streamId"
    assert out["all_streams"] is False and len(calls) == 1


def test_day_n_retention_maths():
    cohorts = fa._parse_cohorts(DATA)
    assert fa.retention(cohorts, 1, SEL) == (35.0, date(2026, 11, 9), 200, 70)
    assert fa.retention(cohorts, 1, date(2026, 11, 9)) == (40.0, date(2026, 11, 8), 100, 40)
    assert fa.retention(cohorts, 3, SEL) == (15.0, date(2026, 11, 7), 400, 60)
    assert fa.retention(cohorts, 7, SEL) == (8.0, date(2026, 11, 3), 50, 4)


def test_nobody_came_back_is_zero_not_missing():
    cohorts = fa._parse_cohorts(cohort_rows({"2026-11-09": (10, {0: 10})}))
    assert fa.retention(cohorts, 1, SEL) == (0.0, date(2026, 11, 9), 10, 0)


def test_no_installs_that_day_is_missing():
    assert fa.retention({}, 1, SEL) == (None, date(2026, 11, 9), 0, 0)


def test_falls_back_to_whole_property_if_stream_filter_is_refused():
    calls = []

    def fake(method, url, key, **kw):
        calls.append(kw["json"])
        if "dimensionFilter" in kw["json"]:
            raise fa.GAError("Google API 400: Field streamId is not compatible with cohort reports")
        return DATA

    fa_call, fa._call = fa._call, fake
    try:
        out = fa.fetch_retention("123", "456", SEL.isoformat())
    finally:
        fa._call = fa_call
    assert len(calls) == 2 and "dimensionFilter" not in calls[1]
    assert out["all_streams"] is True
    assert fa.retention(out["cohorts"], 1, SEL)[0] == 35.0


def test_other_google_errors_are_not_hidden():
    def fake(method, url, key, **kw):
        raise fa.GAError("Google API 403: User does not have sufficient permissions")

    fa_call, fa._call = fa._call, fake
    try:
        try:
            fa.fetch_retention("123", "456", SEL.isoformat())
            raised = False
        except fa.GAError:
            raised = True
    finally:
        fa._call = fa_call
    assert raised
