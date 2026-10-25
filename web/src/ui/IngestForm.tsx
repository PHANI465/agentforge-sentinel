import { useState } from "react";
import type { FormEvent } from "react";
import { formatScore, scoreLabel } from "../api/format";
import { moneyFromParts } from "../api/format";
import type { SentinelClient } from "../api/client";
import type { Currency, TransactionInput } from "../api/types";
import { CURRENCY_EXPONENT } from "../api/types";

const CURRENCIES = Object.keys(CURRENCY_EXPONENT) as Currency[];

export function IngestForm({
  client,
  token,
  onRecorded,
}: {
  client: SentinelClient;
  token: string;
  onRecorded: (caseId: string | null) => void;
}) {
  const [externalId, setExternalId] = useState("");
  const [accountId, setAccountId] = useState("");
  const [minorUnits, setMinorUnits] = useState("");
  const [currency, setCurrency] = useState<Currency>("USD");
  const [direction, setDirection] = useState<"debit" | "credit">("debit");
  const [occurredAt, setOccurredAt] = useState("");
  const [frozen, setFrozen] = useState<TransactionInput | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function payload(): TransactionInput | null {
    const units = Number(minorUnits);
    if (!externalId.trim() || !accountId.trim() || !occurredAt.trim()) return null;
    if (!Number.isSafeInteger(units) || units <= 0) return null;
    return {
      external_id: externalId.trim(),
      account_id: accountId.trim(),
      amount: moneyFromParts(currency, units),
      direction,
      occurred_at: occurredAt.trim(),
    };
  }

  async function submit(body: TransactionInput) {
    setBusy(true);
    const result = await client.ingest(token, body);
    setBusy(false);
    if (!result.ok) {
      if (result.ambiguous) setFrozen(body);
      setMessage(result.message);
      return;
    }
    setFrozen(null);
    const score = result.data.scoring
      ? `${scoreLabel(result.data.scoring.scoring_kind, result.data.scoring.score_semantics)} ${formatScore(result.data.scoring.score)}`
      : `Rule score ${formatScore(result.data.rule_score)}`;
    const opened = result.data.case
      ? "A case was opened."
      : "No case was opened.";
    const replay = result.data.replayed ? " This repeated an earlier ingest." : "";
    setMessage(`${opened} ${score}.${replay}`);
    onRecorded(result.data.case?.id ?? null);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const body = payload();
    if (!body) {
      setMessage("Enter an external id, account id, positive minor-unit amount, and an RFC3339 time.");
      return;
    }
    await submit(body);
  }

  return (
    <form className="ingest block" onSubmit={onSubmit}>
      <h2>Record a synthetic transaction</h2>
      <label>
        External id
        <input value={externalId} onChange={(event) => setExternalId(event.target.value)} />
      </label>
      <label>
        Account id
        <input value={accountId} onChange={(event) => setAccountId(event.target.value)} />
      </label>
      <label>
        Amount in minor units
        <input
          inputMode="numeric"
          value={minorUnits}
          onChange={(event) => setMinorUnits(event.target.value)}
        />
      </label>
      <label>
        Currency
        <select value={currency} onChange={(event) => setCurrency(event.target.value as Currency)}>
          {CURRENCIES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>
      <label>
        Direction
        <select
          value={direction}
          onChange={(event) => setDirection(event.target.value as "debit" | "credit")}
        >
          <option value="debit">Debit</option>
          <option value="credit">Credit</option>
        </select>
      </label>
      <label>
        Occurred at
        <input
          value={occurredAt}
          onChange={(event) => setOccurredAt(event.target.value)}
          placeholder="2026-10-23T17:00:00Z"
        />
      </label>
      <button type="submit" disabled={busy}>
        Record transaction
      </button>
      {frozen ? (
        <button type="button" disabled={busy} onClick={() => void submit(frozen)}>
          Retry the same transaction
        </button>
      ) : null}
      <p className="status">{message}</p>
    </form>
  );
}
