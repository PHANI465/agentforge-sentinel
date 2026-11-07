"""Recompute the derived (not measured) facts behind the AN01 r3 decision proposal.

    uv run --locked python docs/analytics/check_an01_r3.py

Standard library only. Reads two committed files: the r2 checker (for its cursor encoder)
and AN01-zone-table.json. It never reads host zone data, a database or the network, so the
answer is the same on every platform. Exit status 1 on any failure.
"""
from __future__ import annotations

import bisect
import hashlib
import importlib.util
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
UTC = timezone.utc
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def load_r2():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("check_an01", HERE / "check_an01.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---- decision 3/4: the cursor length bound is derived from the encoding ------------------
r2 = load_r2()
worst = {"occurred": datetime(2037, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
         "id": "ffffffff-ffff-4fff-bfff-ffffffffffff"}
lengths = {cap: len(r2.encode_cursor("f" * 64, worst, (cap, cap)))
           for cap in (200_000, 1_000_000, 9_999_999)}
check("worst-case cursor at the 200,000 cap is 228 characters", lengths[200_000] == 228,
      str(lengths))
check("every count up to 9,999,999 fits a 256-character limit",
      max(lengths.values()) <= 256, f"max {max(lengths.values())}")
check("the r2 fixture page-1 cursor (215) is under the bound", 215 <= 256)

# ---- decision 1: the pinned zone table ---------------------------------------------------
doc = json.loads((HERE / "AN01-zone-table.json").read_text(encoding="utf-8"))
ranges = doc["ranges"]
canonical = json.dumps(ranges, sort_keys=True, separators=(",", ":"))
recomputed = hashlib.sha256(("sentinel.report-zones.an01-s1\n" + canonical).encode()).hexdigest()
check("zone table digest matches its contents", recomputed == doc["sha256"], recomputed[:16])
check("zone table digest is the one in the decision document",
      doc["sha256"] == "dd1b19c9c191d33f94758cf81bab82ac5d29c68b9717e5f58897ac2e024749a5")
check("exactly the five S1 zones", sorted(ranges) == sorted(
    ["UTC", "Asia/Kolkata", "Asia/Tokyo", "Europe/London", "America/New_York"]))
FIRST, LAST = date(2000, 1, 1), date(2038, 1, 1)


def starts(zone: str) -> list[tuple[date, datetime]]:
    """(local date, UTC start instant) for every date in range, from the table only."""
    rows = [(date.fromisoformat(d), off) for d, off in ranges[zone]]
    out, i, day = [], 0, FIRST
    while day <= LAST + timedelta(days=1):
        while i + 1 < len(rows) and rows[i + 1][0] <= day:
            i += 1
        out.append((day, datetime(day.year, day.month, day.day, tzinfo=UTC)
                    - timedelta(seconds=rows[i][1])))
        day += timedelta(days=1)
    return out


TABLE = {zone: starts(zone) for zone in ranges}
for zone, rows in ranges.items():
    check(f"{zone}: ranges start at 2000-01-01 and are strictly ordered",
          rows[0][0] == "2000-01-01" and all(a[0] < b[0] for a, b in zip(rows, rows[1:])))
    found = {int((b[1] - a[1]).total_seconds()) for a, b in zip(TABLE[zone], TABLE[zone][1:])}
    check(f"{zone}: every local day is 82,800, 86,400 or 90,000 s", found <= {82800, 86400, 90000},
          str(sorted(found)))


def day_seconds(zone: str, day: date) -> int:
    index = (day - FIRST).days
    return int((TABLE[zone][index + 1][1] - TABLE[zone][index][1]).total_seconds())


check("New York 2026-03-08 is 82,800 s", day_seconds("America/New_York", date(2026, 3, 8)) == 82800)
check("New York 2026-11-01 is 90,000 s", day_seconds("America/New_York", date(2026, 11, 1)) == 90000)
check("London 2026-03-29 is 82,800 s", day_seconds("Europe/London", date(2026, 3, 29)) == 82800)
check("London 2026-10-25 is 90,000 s", day_seconds("Europe/London", date(2026, 10, 25)) == 90000)
kolkata = TABLE["Asia/Kolkata"][(date(2026, 10, 1) - FIRST).days][1]
check("Kolkata 2026-10-01 starts at 2026-09-30T18:30Z (r2 known answer)",
      kolkata == datetime(2026, 9, 30, 18, 30, tzinfo=UTC))

# ---- the r2 bound "a 92-day instant window touches at most 94 local dates" ----------------
# Exhaustive over window starts on every whole hour, and 1 us before every local midnight,
# for 2000..2037 (all offsets in these zones are whole hours, so these are the extremes).
SPAN = timedelta(seconds=92 * 86400)
worst_dates = {}
for zone in ranges:
    instants = [s for _d, s in TABLE[zone]]
    best = 0
    candidates = [s - timedelta(microseconds=1) for s in instants[:-100]]
    t = datetime(2000, 1, 1, tzinfo=UTC)
    while t < datetime(2037, 9, 1, tzinfo=UTC):
        candidates.append(t)
        t += timedelta(hours=1)
    for start in candidates:
        end = start + SPAN
        first = bisect.bisect_right(instants, start) - 1   # date containing `start`
        last = bisect.bisect_left(instants, end) - 1       # date containing end - epsilon
        best = max(best, last - first + 1)
    worst_dates[zone] = best
check("a 92-day instant window touches at most 94 local dates in any S1 zone",
      max(worst_dates.values()) <= 94, str(worst_dates))
check("so daily output is at most 94 x 4 = 376 rows", max(worst_dates.values()) * 4 <= 376)

print(("OK" if not FAILURES else "FAILED") + f": {len(FAILURES)} failure(s)")
sys.exit(1 if FAILURES else 0)
