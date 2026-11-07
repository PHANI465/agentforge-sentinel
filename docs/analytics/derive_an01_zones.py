"""AN01 decision 1 (proposal): derive the pinned S1 local-midnight table from zoneinfo.

    uv run --locked python docs/analytics/derive_an01_zones.py            # print summary
    uv run --locked python docs/analytics/derive_an01_zones.py --check    # compare with the
                                                                          # committed table
    uv run --locked python docs/analytics/derive_an01_zones.py --write    # regenerate it

This is a review/development tool, not a gate test. It reads whatever zone data the host
`zoneinfo` resolves: the locked `tzdata` wheel on Windows, and the system database on Linux,
where `tzdata` is not locked. The proposal is that the server never reads host zone data at
runtime. It uses the committed table, and this script only (re)derives it under review.

Two ranges are kept apart (R50):

- **The public request domain** is the UTC instants `[2000-01-01T00:00Z, 2038-01-01T00:00Z)`.
  A request is valid only if its UTC window, after any date-mode conversion, lies inside it.
- **The lookup range** is the local dates the server may need for a valid request: the local
  date containing the lower edge, the local date containing the last valid instant, and the
  next date after that, whose midnight ends the last bucket.

  It is computed per zone from zoneinfo, then padded to one shared range,
  `[1999-12-31, 2038-01-02]`. The table covers exactly that range, and a lookup outside it is
  an error, never an extrapolation.

For each zone and each local date D in the lookup range it computes the first instant whose
local date is D (local 00:00, which must exist and be unambiguous). It stores the result as
offset ranges: [first local date, UTC offset at local midnight, in seconds]. Standard library
only; no network or database. It writes a file only with --write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ZONES = ("UTC", "Asia/Kolkata", "Asia/Tokyo", "Europe/London", "America/New_York")
UTC = timezone.utc
DOMAIN_LOWER = datetime(2000, 1, 1, tzinfo=UTC)          # inclusive
DOMAIN_UPPER = datetime(2038, 1, 1, tzinfo=UTC)          # exclusive
LAST_INSTANT = DOMAIN_UPPER - timedelta(microseconds=1)  # last valid instant (microseconds)
FIRST, LAST = date(1999, 12, 31), date(2038, 1, 2)       # padded lookup dates, inclusive
TABLE = Path(__file__).with_name("AN01-zone-table.json")
DIGEST_DOMAIN = "sentinel.report-zones.an01-s1.v2\n"
NOTE = ("AN01 decision 1 proposal: pinned S1 local-midnight offsets. Each range is "
        "[first local date, UTC offset in seconds at local 00:00] and applies until the next "
        "range. Lookups are valid only for local dates inside lookup_dates; there is no "
        "extrapolation. The public request domain is separate. Derived by "
        "derive_an01_zones.py; not used by any code yet.")


def midnight(zone: ZoneInfo, day: date) -> datetime:
    naive = datetime(day.year, day.month, day.day)
    early = naive.replace(tzinfo=zone, fold=0).astimezone(UTC)
    late = naive.replace(tzinfo=zone, fold=1).astimezone(UTC)
    if early != late or early.astimezone(zone).replace(tzinfo=None) != naive:
        raise SystemExit(f"{zone.key} {day}: local midnight is missing or ambiguous")
    return early


def required_dates(name: str) -> dict:
    """The local dates a valid request can need in this zone, straight from zoneinfo."""
    zone = ZoneInfo(name)
    lower = DOMAIN_LOWER.astimezone(zone).date()
    upper = LAST_INSTANT.astimezone(zone).date()
    return {"lower_containing": lower.isoformat(), "upper_containing": upper.isoformat(),
            "upper_sentinel": (upper + timedelta(days=1)).isoformat()}


def derive() -> tuple[dict, dict]:
    ranges, summary = {}, {}
    for name in ZONES:
        need = required_dates(name)
        if date.fromisoformat(need["lower_containing"]) < FIRST or \
                date.fromisoformat(need["upper_sentinel"]) > LAST:
            raise SystemExit(f"{name}: the padded lookup range does not cover {need}")
        zone, day, previous, offset, lengths, rows = ZoneInfo(name), FIRST, None, None, {}, []
        while day <= LAST:
            start = midnight(zone, day)
            here = int((datetime(day.year, day.month, day.day, tzinfo=UTC)
                        - start).total_seconds())
            if here != offset:
                rows.append([day.isoformat(), here])
                offset = here
            if previous is not None:
                length = int((start - previous).total_seconds())
                lengths[str(length)] = lengths.get(str(length), 0) + 1
            previous, day = start, day + timedelta(days=1)
        ranges[name] = rows
        summary[name] = {"required": need, "offset_ranges": len(rows),
                         "day_seconds": dict(sorted(lengths.items()))}
    return ranges, summary


def source() -> str:
    try:
        import tzdata  # noqa: PLC0415
        return f"tzdata package, IANA {tzdata.IANA_VERSION}"
    except ImportError:
        return "host zoneinfo database (no tzdata package)"


def digest(lookup_dates: list[str], ranges: dict) -> str:
    canonical = json.dumps({"lookup_dates": lookup_dates, "ranges": ranges},
                           sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((DIGEST_DOMAIN + canonical).encode()).hexdigest()


def document(ranges: dict) -> dict:
    lookup = [FIRST.isoformat(), LAST.isoformat()]
    return {"note": NOTE, "zone_data": "IANA 2026e (derived on Windows tzdata wheel and "
            "native Ubuntu system zoneinfo; identical)",
            "request_domain_utc": ["2000-01-01T00:00:00Z", "2038-01-01T00:00:00Z"],
            "request_domain_rule": "from >= lower and to <= upper, after date-mode conversion",
            "lookup_dates": lookup, "zones": list(ZONES),
            "sha256": digest(lookup, ranges), "ranges": ranges}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    ranges, summary = derive()
    lookup = [FIRST.isoformat(), LAST.isoformat()]
    report = {"source": source(), "python": sys.version.split()[0], "lookup_dates": lookup,
              "sha256": digest(lookup, ranges), "summary": summary}
    print(json.dumps(report, indent=1))
    if args.write:
        TABLE.write_text(json.dumps(document(ranges), indent=1) + "\n", encoding="utf-8",
                         newline="\n")
        print(f"wrote {TABLE.name}")
    if args.check:
        committed = json.loads(TABLE.read_text(encoding="utf-8"))
        if (committed.get("ranges") != ranges or committed.get("lookup_dates") != lookup
                or committed.get("sha256") != digest(lookup, ranges)):
            print("DIFFERS from the committed table: review the zone-data change",
                  file=sys.stderr)
            return 1
        print("matches the committed table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
