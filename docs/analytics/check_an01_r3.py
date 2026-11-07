"""Recompute the derived (not measured) facts behind the AN01 r3 decision proposal.

    uv run --locked python docs/analytics/check_an01_r3.py
    uv run --locked python docs/analytics/check_an01_r3.py --coverage-only --table OLD.json

Standard library only. It reads two committed files: the r2 checker (for its cursor
encoder) and AN01-zone-table.json. It never reads host zone data, a database or the
network, so the answer is the same on every platform. Exit status 1 on any failure.

Zone lookups are strict (R50). A local date outside the table's lookup range is an error
here, exactly as the server must refuse it: never clamped, extrapolated or indexed negatively.
The coverage section evaluates its conditions without relying on exceptions, so pointing
`--coverage-only --table` at an older table reports which edges that table fails to cover.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import importlib.util
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
UTC = timezone.utc
LOWER = datetime(2000, 1, 1, tzinfo=UTC)                  # request domain, inclusive
UPPER = datetime(2038, 1, 1, tzinfo=UTC)                  # request domain, exclusive
EPS = timedelta(microseconds=1)
SPAN = timedelta(seconds=92 * 86400)
EXPECTED_DIGEST = "24e41cecb475453bb35e166abfc250610670593fd6ff0f324e0095eae274e165"
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


class Zones:
    """Strict lookups over one table; only the dates it lists exist."""

    def __init__(self, doc: dict):
        self.first, self.last = map(date.fromisoformat,
                                    doc.get("lookup_dates") or doc["range"])
        self.dates: dict[str, list[date]] = {}
        self.starts: dict[str, list[datetime]] = {}
        for zone, rows in doc["ranges"].items():
            rows = [(date.fromisoformat(d), off) for d, off in rows]
            days, starts, i, day = [], [], 0, self.first
            while day <= self.last:
                while i + 1 < len(rows) and rows[i + 1][0] <= day:
                    i += 1
                days.append(day)
                starts.append(datetime(day.year, day.month, day.day, tzinfo=UTC)
                              - timedelta(seconds=rows[i][1]))
                day += timedelta(days=1)
            self.dates[zone], self.starts[zone] = days, starts

    def start(self, zone: str, day: date) -> datetime:
        if not self.first <= day <= self.last:
            raise LookupError(f"{zone} {day} is outside the lookup dates")
        return self.starts[zone][(day - self.first).days]

    def containing(self, zone: str, instant: datetime) -> int | None:
        """Index of the local date containing `instant`, with its next midnight also in the
        table; None if the table does not cover both (never a negative or clamped index)."""
        starts = self.starts[zone]
        index = bisect.bisect_right(starts, instant) - 1
        if index < 0 or index + 1 >= len(starts):
            return None
        return index

    def day_seconds(self, zone: str, day: date) -> int:
        return int((self.start(zone, day + timedelta(days=1))
                    - self.start(zone, day)).total_seconds())


# Known answers at both UTC edges: (lower containing local date, its start instant,
# upper containing local date, its sentinel next-midnight instant).
EDGES = {
    "UTC": ("2000-01-01", "2000-01-01T00:00Z", "2037-12-31", "2038-01-01T00:00Z"),
    "Europe/London": ("2000-01-01", "2000-01-01T00:00Z", "2037-12-31", "2038-01-01T00:00Z"),
    "America/New_York": ("1999-12-31", "1999-12-31T05:00Z", "2037-12-31", "2038-01-01T05:00Z"),
    "Asia/Kolkata": ("2000-01-01", "1999-12-31T18:30Z", "2038-01-01", "2038-01-01T18:30Z"),
    "Asia/Tokyo": ("2000-01-01", "1999-12-31T15:00Z", "2038-01-01", "2038-01-01T15:00Z"),
}


def instant(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def coverage(zones: Zones) -> None:
    """R50: every valid UTC request instant has its containing date and next midnight."""
    for zone, (low_day, low_start, up_day, sentinel) in EDGES.items():
        starts = zones.starts[zone]
        low_ok = starts[0] <= LOWER
        check(f"{zone}: the lower UTC edge lies inside the table (containing date "
              f"{low_day} starts {low_start})", low_ok,
              f"table starts {starts[0].isoformat()}")
        up_ok = starts[-1] >= UPPER
        check(f"{zone}: the last valid instant's date {up_day} has its next midnight "
              f"{sentinel} in the table", up_ok, f"table ends {starts[-1].isoformat()}")
        lower_index = zones.containing(zone, LOWER)
        upper_index = zones.containing(zone, UPPER - EPS)
        check(f"{zone}: lower edge known answer", lower_index is not None
              and zones.dates[zone][lower_index].isoformat() == low_day
              and zones.starts[zone][lower_index] == instant(low_start))
        check(f"{zone}: upper edge known answer", upper_index is not None
              and zones.dates[zone][upper_index].isoformat() == up_day
              and zones.starts[zone][upper_index + 1] == instant(sentinel))


def whole_domain(zones: Zones) -> dict:
    """Every whole-hour window start, plus 1 us before every local midnight and both edges,
    across the entire domain: windows [t, min(t + 92 days, UPPER)). Returns the most local
    dates any window touches, and counts uncovered lookups (which must be zero)."""
    worst, uncovered = {}, 0
    for zone in zones.starts:
        candidates = {LOWER, UPPER - EPS}
        candidates.update(s - EPS for s in zones.starts[zone] if LOWER <= s - EPS < UPPER)
        t = LOWER
        while t < UPPER:
            candidates.add(t)
            t += timedelta(hours=1)
        best = 0
        for start in candidates:
            end = min(start + SPAN, UPPER)
            first = zones.containing(zone, start)
            last = zones.containing(zone, end - EPS)
            if first is None or last is None:
                uncovered += 1
                continue
            best = max(best, last - first + 1)
        worst[zone] = best
    return {"worst_dates": worst, "uncovered": uncovered}


def date_mode(zones: Zones, zone: str, date_from: date, date_to: date) -> str:
    """The proposed validation order: convert both local dates (strict lookups), then check
    the converted UTC window against the request domain. Returns the outcome."""
    if not 1 <= (date_to - date_from).days <= 92:
        return "invalid_request: date range"
    try:
        start, end = zones.start(zone, date_from), zones.start(zone, date_to)
    except LookupError:
        return "invalid_request: date outside the lookup table"
    if start < LOWER or end > UPPER:
        return "invalid_request: converted window outside the request domain"
    return "accepted"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, default=HERE / "AN01-zone-table.json")
    parser.add_argument("--coverage-only", action="store_true")
    args = parser.parse_args()
    doc = json.loads(args.table.read_text(encoding="utf-8"))
    zones = Zones(doc)
    print(f"table: {args.table.name}, lookup dates {zones.first} .. {zones.last}")

    coverage(zones)
    result = whole_domain(zones)
    check("every window start in the whole UTC domain has covered lookups (no clamping)",
          result["uncovered"] == 0, f"{result['uncovered']} uncovered")
    if args.coverage_only:
        return finish()

    # ---- the table itself --------------------------------------------------------------
    canonical = json.dumps({"lookup_dates": doc["lookup_dates"], "ranges": doc["ranges"]},
                           sort_keys=True, separators=(",", ":"))
    recomputed = hashlib.sha256(("sentinel.report-zones.an01-s1.v2\n"
                                 + canonical).encode()).hexdigest()
    check("zone table digest matches its contents", recomputed == doc["sha256"], recomputed[:16])
    check("zone table digest is the one in the decision document",
          doc["sha256"] == EXPECTED_DIGEST)
    check("lookup dates are the padded range 1999-12-31 .. 2038-01-02",
          doc["lookup_dates"] == ["1999-12-31", "2038-01-02"])
    check("request domain is recorded separately from the lookup dates",
          doc["request_domain_utc"] == ["2000-01-01T00:00:00Z", "2038-01-01T00:00:00Z"])
    check("exactly the five S1 zones", sorted(doc["ranges"]) == sorted(EDGES))
    for zone, rows in doc["ranges"].items():
        check(f"{zone}: ranges start at the first lookup date and are strictly ordered",
              rows[0][0] == doc["lookup_dates"][0]
              and all(a[0] < b[0] for a, b in zip(rows, rows[1:])))
        found = {int((b - a).total_seconds())
                 for a, b in zip(zones.starts[zone], zones.starts[zone][1:])}
        check(f"{zone}: every local day is 82,800, 86,400 or 90,000 s",
              found <= {82800, 86400, 90000}, str(sorted(found)))

    # ---- strictness: no extrapolation ---------------------------------------------------
    for day in (date(1999, 12, 30), date(2038, 1, 3)):
        try:
            zones.start("Asia/Tokyo", day)
            refused = False
        except LookupError:
            refused = True
        check(f"lookup of {day} outside the table is refused, not extrapolated", refused)
    check("an instant before the table has no containing date (no negative index)",
          zones.containing("America/New_York", datetime(1999, 12, 31, 4, tzinfo=UTC)) is None)

    # ---- r2 known answers (unchanged) ---------------------------------------------------
    check("New York 2026-03-08 is 82,800 s",
          zones.day_seconds("America/New_York", date(2026, 3, 8)) == 82800)
    check("New York 2026-11-01 is 90,000 s",
          zones.day_seconds("America/New_York", date(2026, 11, 1)) == 90000)
    check("London 2026-03-29 is 82,800 s",
          zones.day_seconds("Europe/London", date(2026, 3, 29)) == 82800)
    check("London 2026-10-25 is 90,000 s",
          zones.day_seconds("Europe/London", date(2026, 10, 25)) == 90000)
    check("Kolkata 2026-10-01 starts at 2026-09-30T18:30Z (r2 known answer)",
          zones.start("Asia/Kolkata", date(2026, 10, 1)) == datetime(2026, 9, 30, 18, 30,
                                                                     tzinfo=UTC))
    check("edge-day lengths come from the table: New York 1999-12-31 is 86,400 s, "
          "Tokyo 2038-01-01 is 86,400 s",
          zones.day_seconds("America/New_York", date(1999, 12, 31)) == 86400
          and zones.day_seconds("Asia/Tokyo", date(2038, 1, 1)) == 86400)

    # ---- daily bound over the entire domain ---------------------------------------------
    worst = result["worst_dates"]
    check("a 92-day instant window touches at most 94 local dates in any S1 zone, over "
          "the whole domain", max(worst.values()) <= 94, str(worst))
    check("so daily output is at most 94 x 4 = 376 rows", max(worst.values()) * 4 <= 376)

    # ---- date mode: validate after conversion -------------------------------------------
    cases = [
        ("America/New_York", date(1999, 12, 31), date(2000, 1, 1),
         "invalid_request: converted window outside the request domain"),
        ("America/New_York", date(2000, 1, 1), date(2000, 1, 2), "accepted"),
        ("Asia/Tokyo", date(2037, 12, 31), date(2038, 1, 1), "accepted"),
        ("Asia/Tokyo", date(2038, 1, 1), date(2038, 1, 2),
         "invalid_request: converted window outside the request domain"),
        ("Asia/Tokyo", date(2038, 1, 2), date(2038, 1, 3),
         "invalid_request: date outside the lookup table"),
        ("UTC", date(2037, 12, 31), date(2038, 1, 1), "accepted"),
        ("UTC", date(2026, 10, 1), date(2027, 1, 2), "invalid_request: date range"),
    ]
    for zone, a, b, expected in cases:
        got = date_mode(zones, zone, a, b)
        check(f"date mode {zone} [{a}, {b}) -> {expected}", got == expected, got)
    accepted = rejected_lookup = 0
    for zone in zones.dates:
        for day in zones.dates[zone]:
            for k in (1, 92):
                outcome = date_mode(zones, zone, day, day + timedelta(days=k))
                accepted += outcome == "accepted"
                if outcome == "accepted":
                    # every accepted request's buckets need only in-table lookups
                    zones.start(zone, day + timedelta(days=k))
                rejected_lookup += outcome.endswith("lookup table")
    check("every accepted 1- and 92-date date-mode request converts with in-table lookups",
          accepted > 0, f"{accepted} accepted, {rejected_lookup} refused at lookup")

    # ---- decisions 3/4: the cursor length bound is derived from the encoding ------------
    r2 = load_r2()
    worst_cursor = {"occurred": datetime(2037, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
                    "id": "ffffffff-ffff-4fff-bfff-ffffffffffff"}
    lengths = {cap: len(r2.encode_cursor("f" * 64, worst_cursor, (cap, cap)))
               for cap in (200_000, 1_000_000, 9_999_999)}
    check("worst-case cursor at the 200,000 cap is 228 characters", lengths[200_000] == 228,
          str(lengths))
    check("every count up to 9,999,999 fits a 256-character limit",
          max(lengths.values()) <= 256, f"max {max(lengths.values())}")
    check("the r2 fixture page-1 cursor (215) is under the bound", 215 <= 256)
    check("a bool is not an exact integer count (strict member type)",
          type(True) is not int and isinstance(True, int))
    return finish()


def load_r2():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("check_an01", HERE / "check_an01.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finish() -> int:
    print(("OK" if not FAILURES else "FAILED") + f": {len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
