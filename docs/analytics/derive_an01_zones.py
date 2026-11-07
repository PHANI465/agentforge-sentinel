"""AN01 decision 1 (proposal): derive the pinned S1 local-midnight table from zoneinfo.

    uv run --locked python docs/analytics/derive_an01_zones.py            # print summary
    uv run --locked python docs/analytics/derive_an01_zones.py --check    # compare with the
                                                                          # committed table

This is a review/development tool, not a gate test. It reads whatever zone data the host
`zoneinfo` resolves (the locked `tzdata` wheel on Windows; the system database on Linux,
where `tzdata` is not locked). The proposal is that the server never reads host zone data at
runtime: it uses the committed table, and this script only (re)derives it under review.

For each allow-listed zone and each local date D in [2000-01-01, 2038-01-01] it computes the
first instant whose local date is D (local 00:00, which must exist and be unambiguous), then
stores the table as offset ranges: [first local date, UTC offset at local midnight, seconds].
Standard library only; no network, database or file writes.
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
FIRST, LAST = date(2000, 1, 1), date(2038, 1, 1)
TABLE = Path(__file__).with_name("AN01-zone-table.json")
DOMAIN = "sentinel.report-zones.an01-s1\n"


def midnight(zone: ZoneInfo, day: date) -> datetime:
    naive = datetime(day.year, day.month, day.day)
    early = naive.replace(tzinfo=zone, fold=0).astimezone(timezone.utc)
    late = naive.replace(tzinfo=zone, fold=1).astimezone(timezone.utc)
    if early != late or early.astimezone(zone).replace(tzinfo=None) != naive:
        raise SystemExit(f"{zone.key} {day}: local midnight is missing or ambiguous")
    return early


def derive() -> tuple[dict, dict]:
    ranges, summary = {}, {}
    for name in ZONES:
        zone, day, previous, offset, lengths, rows = ZoneInfo(name), FIRST, None, None, {}, []
        while day <= LAST:
            start = midnight(zone, day)
            here = int((datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
                        - start).total_seconds())
            if here != offset:
                rows.append([day.isoformat(), here])
                offset = here
            if previous is not None:
                length = int((start - previous).total_seconds())
                lengths[str(length)] = lengths.get(str(length), 0) + 1
            previous, day = start, day + timedelta(days=1)
        ranges[name] = rows
        summary[name] = {"offset_ranges": len(rows), "day_seconds": dict(sorted(lengths.items()))}
    return ranges, summary


def source() -> str:
    try:
        import tzdata  # noqa: PLC0415
        return f"tzdata package, IANA {tzdata.IANA_VERSION}"
    except ImportError:
        return "host zoneinfo database (no tzdata package)"


def digest(ranges: dict) -> str:
    canonical = json.dumps(ranges, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((DOMAIN + canonical).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    ranges, summary = derive()
    report = {"source": source(), "python": sys.version.split()[0],
              "range": [FIRST.isoformat(), LAST.isoformat()],
              "sha256": digest(ranges), "summary": summary}
    print(json.dumps(report, indent=1))
    if args.check:
        committed = json.loads(TABLE.read_text(encoding="utf-8"))
        if committed["ranges"] != ranges or committed["sha256"] != digest(ranges):
            print("DIFFERS from the committed table: review the zone-data change", file=sys.stderr)
            return 1
        print("matches the committed table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
