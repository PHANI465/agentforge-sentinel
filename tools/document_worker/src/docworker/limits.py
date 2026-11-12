"""Concrete, enforced Part A bounds and caller-declared interpretation options.

Every number here is an enforced cap, not a measured capacity claim. The smoke report records
what was actually measured on the fixtures; nothing near the caps is advertised as supported
throughput.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

MiB = 1024 * 1024


@dataclass(frozen=True)
class Limits:
    # Input
    max_input_bytes: int = 10 * MiB
    # PDF
    max_pdf_pages: int = 50
    # Tables (CSV and each XLSX sheet)
    max_table_rows: int = 20_000
    max_columns: int = 64
    max_field_chars: int = 4_096
    # XLSX container
    max_xlsx_sheets: int = 16
    max_xlsx_cells: int = 500_000
    max_zip_members: int = 256
    max_zip_member_bytes: int = 32 * MiB
    max_zip_total_bytes: int = 64 * MiB
    max_zip_ratio: int = 200          # applied to members larger than 1 MiB uncompressed
    # Output
    max_records: int = 20_000
    max_unparsed_items: int = 500
    max_page_text_chars: int = 100_000
    max_narrative_chars: int = 1_000_000
    max_stdout_bytes: int = 16 * MiB
    max_stderr_bytes: int = 64 * 1024
    # Child process
    deadline_seconds: float = 30.0
    memory_bytes: int = 1024 * MiB            # Windows job per-process committed memory
    posix_address_space_bytes: int = 4096 * MiB  # RLIMIT_AS (virtual; numpy/onnx reserve)
    stop_confirm_seconds: float = 5.0
    # Handles
    handle_ttl_seconds: int = 3_600

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Limits":
        known = {f.name: f.type for f in fields(cls)}
        unknown = set(data) - set(known)
        if unknown:
            raise ValueError(f"unknown limit(s): {sorted(unknown)}")
        clean = {}
        for key, value in data.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"limit {key} must be a positive number")
            clean[key] = value
        return cls(**clean)


DECIMAL_STYLES = ("unspecified", "dot", "comma")
DATE_ORDERS = ("iso_only", "dmy", "mdy")


@dataclass(frozen=True)
class Options:
    """Interpretation assumptions. Defaults never guess: undeclared conventions stay unknown."""

    decimal_style: str = "unspecified"  # dot = 1,234.56 ; comma = 1.234,56
    date_order: str = "iso_only"
    default_currency: str | None = None  # applied only where neither row nor document states one

    def __post_init__(self):
        if self.decimal_style not in DECIMAL_STYLES:
            raise ValueError(f"decimal_style must be one of {DECIMAL_STYLES}")
        if self.date_order not in DATE_ORDERS:
            raise ValueError(f"date_order must be one of {DATE_ORDERS}")
        if self.default_currency is not None and not (
            len(self.default_currency) == 3 and self.default_currency.isalpha()
            and self.default_currency.isupper()
        ):
            raise ValueError("default_currency must be a 3-letter upper-case ISO code")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Options":
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"unknown option(s): {sorted(unknown)}")
        return cls(**data)
