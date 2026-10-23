"""Deterministic synthetic transaction generator with fraud scenarios and legitimate
lookalikes. Independently implemented (no third-party simulator code).

Output is split into what a decision-time system may see (`transactions`: TransactionInput
fields plus `ingested_at`) and hidden truth (`labels`: fraud flag, scenario, label
availability time). The two are joined only by `external_id`.
"""
from __future__ import annotations

import math
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

GENERATOR_VERSION = "g1"
EPOCH = datetime(2026, 9, 1, tzinfo=timezone.utc)
CURRENCIES = {  # code: (exponent, units of currency per USD, share of accounts)
    "USD": (2, 1.0, 0.60), "GBP": (2, 0.8, 0.15), "INR": (2, 83.0, 0.20), "JPY": (0, 150.0, 0.05),
}
MAX_MINOR_UNITS = 9_000_000_000_000
FRAUD_SCENARIOS = ("account_takeover", "card_testing", "mule_cashout")
LOOKALIKE_SCENARIOS = ("payday_burst", "large_legit_purchase", "micro_payments")
LEGIT_MATURITY = timedelta(days=30)  # a legitimate label is "known" once no dispute arrived


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 7
    accounts: int = 1000
    days: int = 30
    max_rows: int = 100_000
    fraud_account_rate: float = 0.05       # accounts that suffer one fraud scenario
    lookalike_account_rate: float = 0.10   # accounts with one legitimate lookalike episode
    daily_rate_range: tuple[float, float] = (0.3, 3.0)
    late_ingestion_rate: float = 0.01      # rows that arrive hours after they occurred
    unlabeled_fraud_rate: float = 0.10     # fraud never disputed within the horizon

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Dataset:
    config: GeneratorConfig
    accounts: list[dict] = field(default_factory=list)
    transactions: list[dict] = field(default_factory=list)  # decision-time projection
    labels: list[dict] = field(default_factory=list)        # hidden truth
    truncated: bool = False


def _iso(value: datetime) -> str:
    # Fixed width (always microseconds) so string order equals time order.
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z")


def _minor(currency: str, usd_major: float) -> int:
    exponent, per_usd, _ = CURRENCIES[currency]
    value = round(usd_major * per_usd * 10 ** exponent)
    return max(1, min(MAX_MINOR_UNITS, value))


class _Builder:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.rng = random.Random(config.seed)
        self.end = EPOCH + timedelta(days=config.days)
        self.rows: list[tuple[dict, dict]] = []

    def uuid(self) -> str:
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def account(self, index: int) -> dict:
        rng = self.rng
        currencies = list(CURRENCIES)
        currency = rng.choices(currencies, weights=[CURRENCIES[c][2] for c in currencies])[0]
        opened = EPOCH - timedelta(days=rng.randint(1, 3 * 365))
        return {"account_id": self.uuid(), "home_currency": currency,
                "opened_at": _iso(opened), "segment": rng.choice(["retail", "student", "smb"]),
                "daily_rate": round(rng.uniform(*self.config.daily_rate_range), 3),
                "typical_usd": round(rng.lognormvariate(math.log(35), 0.5), 2),
                "index": index}

    def emit(self, account: dict, occurred: datetime, usd_major: float, direction: str,
             scenario: str, fraud: bool, currency: str | None = None) -> None:
        if not EPOCH <= occurred < self.end:
            return
        rng = self.rng
        currency = currency or account["home_currency"]
        delay = (timedelta(hours=rng.uniform(1, 12)) if rng.random() < self.config.late_ingestion_rate
                 else timedelta(seconds=rng.randint(0, 120)))
        external_id = f"syn-{self.config.seed}-{len(self.rows):07d}"
        txn = {"external_id": external_id, "account_id": account["account_id"],
               "amount": {"currency": currency, "minor_units": _minor(currency, usd_major),
                          "currency_exponent": CURRENCIES[currency][0]},
               "direction": direction, "occurred_at": _iso(occurred),
               "ingested_at": _iso(occurred + delay)}
        if fraud:
            disputed = rng.random() >= self.config.unlabeled_fraud_rate
            label_at = occurred + timedelta(days=rng.uniform(1, 45)) if disputed else None
        else:
            label_at = occurred + LEGIT_MATURITY
        label = {"external_id": external_id, "is_fraud": fraud, "scenario": scenario,
                 "label_available_at": _iso(label_at) if label_at else None}
        self.rows.append((txn, label))

    def baseline(self, account: dict) -> None:
        rng, day = self.rng, timedelta(days=1)
        t = EPOCH + timedelta(seconds=rng.uniform(0, 86_400) / max(account["daily_rate"], 0.1))
        while t < self.end:
            direction = "credit" if rng.random() < 0.08 else "debit"
            usd = account["typical_usd"] * rng.lognormvariate(0, 0.6)
            if direction == "credit":
                usd *= 8
            foreign = rng.random() < 0.02
            currency = rng.choice([c for c in CURRENCIES if c != account["home_currency"]]) \
                if foreign else None
            self.emit(account, t, usd, direction, "normal", False, currency)
            t += timedelta(seconds=rng.expovariate(account["daily_rate"] / day.total_seconds()))

    def episode_start(self) -> datetime:
        return EPOCH + timedelta(seconds=self.rng.uniform(2 * 86_400, (self.config.days - 1)
                                                         * 86_400))

    def fraud(self, account: dict) -> None:
        rng, start = self.rng, self.episode_start()
        scenario = rng.choice(FRAUD_SCENARIOS)
        foreign = rng.choice([c for c in CURRENCIES if c != account["home_currency"]])
        if scenario == "account_takeover":   # burst of large debits, often foreign
            for i in range(rng.randint(3, 8)):
                self.emit(account, start + timedelta(minutes=rng.uniform(0, 90)),
                          account["typical_usd"] * rng.uniform(8, 40), "debit", scenario, True,
                          foreign if rng.random() < 0.5 else None)
        elif scenario == "card_testing":     # tiny probes, then one large hit
            for i in range(rng.randint(4, 10)):
                self.emit(account, start + timedelta(minutes=i * rng.uniform(1, 4)),
                          rng.uniform(0.5, 2.0), "debit", scenario, True)
            self.emit(account, start + timedelta(minutes=45), account["typical_usd"] * 25,
                      "debit", scenario, True)
        else:                                 # inbound credits then rapid outbound debits
            for i in range(rng.randint(2, 4)):
                self.emit(account, start + timedelta(minutes=i * 20), rng.uniform(800, 3000),
                          "credit", scenario, True)
            for i in range(rng.randint(2, 5)):
                self.emit(account, start + timedelta(hours=2, minutes=i * 7),
                          rng.uniform(500, 2500), "debit", scenario, True)

    def lookalike(self, account: dict) -> None:
        rng, start = self.rng, self.episode_start()
        scenario = rng.choice(LOOKALIKE_SCENARIOS)
        if scenario == "payday_burst":       # legit high velocity after a salary credit
            self.emit(account, start, account["typical_usd"] * 60, "credit", scenario, False)
            for i in range(rng.randint(4, 9)):
                self.emit(account, start + timedelta(minutes=30 + rng.uniform(0, 120)),
                          account["typical_usd"] * rng.uniform(1, 4), "debit", scenario, False)
        elif scenario == "large_legit_purchase":
            self.emit(account, start, account["typical_usd"] * rng.uniform(20, 60), "debit",
                      scenario, False)
        else:                                 # many tiny legit taps (transit/vending)
            for i in range(rng.randint(5, 12)):
                self.emit(account, start + timedelta(minutes=i * rng.uniform(2, 15)),
                          rng.uniform(0.5, 3.0), "debit", scenario, False)


def generate(config: GeneratorConfig) -> Dataset:
    """Same config -> identical dataset (row content and order)."""
    builder = _Builder(config)
    accounts = [builder.account(i) for i in range(config.accounts)]
    for account in accounts:
        builder.baseline(account)
        roll = builder.rng.random()
        if roll < config.fraud_account_rate:
            builder.fraud(account)
        elif roll < config.fraud_account_rate + config.lookalike_account_rate:
            builder.lookalike(account)
    rows = sorted(builder.rows, key=lambda r: (r[0]["occurred_at"], r[0]["external_id"]))
    truncated = len(rows) > config.max_rows
    rows = rows[:config.max_rows]
    public_accounts = [{k: a[k] for k in ("account_id", "home_currency", "opened_at", "segment")}
                       for a in accounts]
    return Dataset(config=config, accounts=public_accounts,
                   transactions=[r[0] for r in rows], labels=[r[1] for r in rows],
                   truncated=truncated)
