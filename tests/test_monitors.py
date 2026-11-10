"""Offline tests for monitor.py and monitor_own_accounts.py: a duplicate app
insert must never abort a user's run.

apps is unique on (user_id, package_name). These tests check that both
monitors:
  * skip a package the user already tracks under a developer the monitor
    doesn't check, instead of inserting it again;
  * catch a duplicate-key error on any apps insert (e.g. both monitors adding
    the same package at once), log it, and carry on so the digest still goes out;
  * page through a user's apps past Supabase's 1000-row limit;
  * (monitor.py) only count the current user's rows when adding a new
    developer's catalog after a transfer.

A fake Supabase enforces the unique index and the row limit; Play Store and
Slack calls are stubbed. Nothing touches the network or a real database.

    python tests/test_monitors.py          # report per check, exit 1 on failure
    python -m pytest tests/test_monitors.py
    python tests/test_monitors.py <dir>    # test monitor files in another folder
"""
import contextlib
import copy
import importlib.util
import io
import sys
from pathlib import Path

import supabase as supabase_pkg
from postgrest.exceptions import APIError

REPO = Path(__file__).resolve().parent.parent
ROW_LIMIT = 1000


class Result:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


class Query:
    def __init__(self, db, table):
        self.db, self.table, self.mode, self.payload = db, table, "select", None
        self.filters, self.window, self.order_col, self.eqs = [], None, None, {}

    def select(self, *_a, **_k): self.mode = "select"; return self
    def insert(self, payload): self.mode, self.payload = "insert", payload; return self
    def update(self, payload): self.mode, self.payload = "update", payload; return self
    def eq(self, c, v): self.eqs[c] = v; self.filters.append(lambda r: r.get(c) == v); return self
    def neq(self, c, v): self.filters.append(lambda r: r.get(c) != v); return self
    def in_(self, c, vs): self.filters.append(lambda r: r.get(c) in vs); return self
    def order(self, c, **_k): self.order_col = c; return self
    def range(self, a, b): self.window = (a, b); return self
    def limit(self, n): self.window = (0, n - 1); return self

    def _rows(self):
        return [r for r in self.db.tables.setdefault(self.table, []) if all(f(r) for f in self.filters)]

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.mode == "insert":
            new = []
            for p in (self.payload if isinstance(self.payload, list) else [self.payload]):
                if self.table == "apps" and any(r["user_id"] == p.get("user_id") and
                                                r["package_name"] == p["package_name"] for r in rows):
                    raise APIError({"code": "23505", "message": 'duplicate key value violates '
                                    'unique constraint "uq_apps_user_package"'})
                row = dict(p, id=self.db.next_id())
                rows.append(row)
                new.append(copy.deepcopy(row))
            return Result(new)
        if self.mode == "update":
            hit = self._rows()
            for r in hit:
                r.update(self.payload)
            return Result(copy.deepcopy(hit))
        hit = self._rows()
        if self.order_col:
            hit.sort(key=lambda r: r.get(self.order_col))
        a, b = self.window if self.window else (0, ROW_LIMIT - 1)
        b = min(b, a + ROW_LIMIT - 1)  # server-side cap, like Supabase's max-rows
        result = Result(copy.deepcopy(hit[a:b + 1]))
        # Race: a per-package existence check comes back empty, then another
        # process inserts that package for this user before our insert runs.
        pkg, user = self.eqs.get("package_name"), self.eqs.get("user_id")
        if self.table == "apps" and pkg in self.db.race_after_check and user and not result.data:
            self.db.race_after_check.discard(pkg)
            self.db.inject(user, pkg)
        return result


class FakeSupabase:
    def __init__(self):
        self.tables, self._id = {}, 10_000
        self.race_after_check = set()

    def inject(self, user, pkg):
        """Another process (e.g. the other monitor) inserts this package for this user."""
        self.tables["apps"].append({"id": self.next_id(), "user_id": user, "developer_id": 999,
                                    "package_name": pkg, "title": "inserted by someone else",
                                    "status": "active"})

    def next_id(self):
        self._id += 1
        return self._id

    def table(self, name):
        return Query(self, name)

    def apps(self, user):
        return {r["package_name"]: r for r in self.tables["apps"] if r["user_id"] == user}


def load(path, fake):
    """Import a monitor file with create_client returning the fake (it connects at import)."""
    real_create_client, real_dont_write = supabase_pkg.create_client, sys.dont_write_bytecode
    supabase_pkg.create_client = lambda *a, **k: fake
    sys.dont_write_bytecode = True  # no __pycache__ next to the monitors
    try:
        spec = importlib.util.spec_from_file_location(f"m_{path.stem}_{id(fake)}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        supabase_pkg.create_client, sys.dont_write_bytecode = real_create_client, real_dont_write
    return mod


def run_main(mod):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        mod.main()
    return out.getvalue()


FILLER = [f"com.filler.app{i:04d}" for i in range(1100)]  # > 1000, to exercise paging


def check_own_accounts(folder):
    db = FakeSupabase()
    db.tables = {
        "developers": [
            {"id": 1, "user_id": "U", "name": "My Own Dev", "source": "own_account", "developer_url": "own1"},
            {"id": 2, "user_id": "U", "name": "Traced Dev", "source": "trace", "developer_url": "t1"},
            {"id": 3, "user_id": "V", "name": "V Own Dev", "source": "own_account", "developer_url": "ownV"},
        ],
        "apps": [{"id": 100, "user_id": "U", "developer_id": 2, "package_name": "com.p.shared",
                  "title": "P", "status": "active"}]
                + [{"id": 200 + i, "user_id": "U", "developer_id": 1, "package_name": p, "title": p,
                    "status": "active", "icon_hash": None} for i, p in enumerate(FILLER)],
        "user_settings": [{"user_id": "U"}, {"user_id": "V"}],
        "change_log": [],
    }
    mod = load(folder / "monitor_own_accounts.py", db)
    # com.race.new comes BEFORE com.q.new, so Q only gets in if the run carries on.
    catalogs = {"own1": FILLER + ["com.p.shared", "com.race.new", "com.q.new"], "ownV": ["com.z.v"]}
    mod.fetch_developer_catalog = lambda link, developer_name=None: [
        {"package_name": p, "title": p if p.startswith("com.filler") else p.upper(), "icon_url": None}
        for p in catalogs[link]]

    def fetch_app_page(pkg, *a, **k):
        # Called right before the insert of a new package: someone else inserts it now.
        if pkg == "com.race.new":
            db.inject("U", pkg)
        return None
    mod.fetch_app_page = fetch_app_page
    mod.get_icon_hash = lambda url: None
    mod.check_app_directly = lambda *a, **k: ("still_removed", None)
    digests = []
    mod.send_digest = lambda events, webhook, settings: digests.append(copy.deepcopy(events)) or True

    out = run_main(mod)
    u = db.apps("U")
    return {
        "no [error] for any user": "[error]" not in out,
        "Q inserted for U": "com.q.new" in u,
        "shared P not duplicated, still under traced dev": u["com.p.shared"]["developer_id"] == 2
                                                         and sum(r["package_name"] == "com.p.shared"
                                                                 for r in db.tables["apps"]) == 1,
        "no filler app re-inserted": len(u) == 1 + len(FILLER) + 2,
        "duplicate insert (race) caught and logged": "[warn] com.race.new already exists" in out
            and sum(r["package_name"] == "com.race.new" for r in db.tables["apps"]) == 1,
        "U digest sent with only Q as new upload": len(digests) >= 1 and
            [e["package_name"] for e in digests[0]["new_upload"]] == ["com.q.new"],
        "V still processed (Z inserted)": "com.z.v" in db.apps("V"),
    }, out


def check_main_monitor(folder):
    db = FakeSupabase()
    db.tables = {
        "developers": [
            {"id": 1, "user_id": "U", "name": "My Own Dev", "source": "own_account",
             "developer_url": "own1", "dev_id": "Own1"},
            {"id": 2, "user_id": "U", "name": "Traced Dev", "source": "trace",
             "developer_url": "t1", "dev_id": "Traced", "studio_id": None},
        ],
        "apps": [
            {"id": 100, "user_id": "U", "developer_id": 1, "package_name": "com.p2.own",
             "title": "P2", "status": "active"},
            {"id": 101, "user_id": "U", "developer_id": 2, "package_name": "com.x.moving",
             "title": "X", "status": "active", "last_seen": None},
            # Another user already tracks S; U must still get it from the transfer catalog.
            {"id": 102, "user_id": "W", "developer_id": 99, "package_name": "com.s.other",
             "title": "S", "status": "active"},
        ],
        "studios": [], "user_settings": [{"user_id": "U"}], "change_log": [],
    }
    mod = load(folder / "monitor.py", db)
    new_dev_link = "https://play.google.com/store/apps/dev?id=NewDev"
    # Race packages come BEFORE the ones checked afterwards, so those only get in
    # if the run carries on past the failed insert.
    catalogs = {"t1": ["com.p2.own", "com.race.r", "com.r.new"],
                new_dev_link: ["com.x.moving", "com.race.s", "com.s.other"]}
    mod.fetch_developer_catalog = lambda link, developer_name=None: [
        {"package_name": p, "title": p.upper(), "icon_url": None} for p in catalogs[link]]
    db.race_after_check.add("com.race.s")  # transfer-catalog path: race after the "already" check

    def fetch_app_page(pkg, *a, **k):
        if pkg == "com.race.r":            # new-app path: race right before the insert
            db.inject("U", pkg)
        return None
    mod.fetch_app_page = fetch_app_page
    mod.get_icon_hash = lambda url: None
    mod.check_app_directly = lambda pkg, *a, **k: (("found", ("New Dev", new_dev_link))
                                                    if pkg == "com.x.moving" else ("still_removed", None))
    digests = []
    mod.send_digest = lambda events, webhook, settings, run_id=None: digests.append(copy.deepcopy(events)) or True

    out = run_main(mod)
    u = db.apps("U")
    return {
        "no [error] for any user": "[error]" not in out,
        "R inserted for U": "com.r.new" in u,
        "own-account P2 not duplicated, still under own dev": u["com.p2.own"]["developer_id"] == 1
            and sum(r["package_name"] == "com.p2.own" for r in db.tables["apps"]) == 1,
        "X moved to the new developer": u["com.x.moving"]["developer_id"] not in (1, 2),
        "S added for U although W tracks it": "com.s.other" in u,
        "new-app duplicate insert (race) caught and logged": "[warn] com.race.r already exists" in out
            and sum(r["package_name"] == "com.race.r" for r in db.tables["apps"]) == 1,
        "transfer-catalog duplicate insert (race) caught and logged":
            "[warn] com.race.s already exists" in out
            and sum(r["package_name"] == "com.race.s" for r in db.tables["apps"]) == 1,
        "U digest sent, transfer of X included": len(digests) == 1
            and [e["package_name"] for e in digests[0]["transferred"]] == ["com.x.moving"],
    }, out


def _assert_all(checks, out):
    failed = [label for label, ok in checks.items() if not ok]
    assert not failed, f"failed checks: {failed}\n--- monitor output ---\n{out}"


def test_own_accounts_monitor_survives_duplicates():
    _assert_all(*check_own_accounts(REPO))


def test_main_monitor_survives_duplicates():
    _assert_all(*check_main_monitor(REPO))


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO
    failed = False
    for name, test in (("monitor_own_accounts.py", check_own_accounts), ("monitor.py", check_main_monitor)):
        try:
            checks, out = test(folder)
        except Exception as e:
            checks, out = {f"crashed: {type(e).__name__}: {e}": False}, ""
        print(f"{name}  ({folder})")
        for label, ok in checks.items():
            print(f"  {'PASS' if ok else 'FAIL'}  {label}")
            failed |= not ok
        for line in out.splitlines():
            if line.startswith(("[warn]", "[error]")):
                print(f"        {line[:150]}")
        print()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
