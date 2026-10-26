import {
  aboveThreshold,
  formatMoney,
  formatScore,
  scoreLabel,
  stateLabel,
} from "../api/format";
import type { CasePage, CaseState } from "../api/types";
import { CASE_STATES } from "../api/types";

export function Queue({
  page,
  loading,
  state,
  selectedId,
  hasPrevious,
  busy,
  onState,
  onSelect,
  onPrevious,
  onNext,
}: {
  page: CasePage | null;
  loading: boolean;
  state: CaseState | "";
  selectedId: string | null;
  hasPrevious: boolean;
  busy: boolean;
  onState: (state: CaseState | "") => void;
  onSelect: (caseId: string) => void;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <section className="queue" aria-labelledby="queue-heading">
      <h2 id="queue-heading">Case queue</h2>
      <label className="filters">
        Case state
        <select
          value={state}
          onChange={(event) => onState(event.target.value as CaseState | "")}
        >
          <option value="">All states</option>
          {CASE_STATES.map((item) => (
            <option key={item} value={item}>
              {stateLabel(item)}
            </option>
          ))}
        </select>
      </label>
      {loading ? <p>Loading cases.</p> : null}
      {!loading && page && page.items.length === 0 ? (
        <p>{state ? "No cases in this state." : "No cases in this session."}</p>
      ) : null}
      {!loading && !page ? <p>Cases could not be loaded.</p> : null}
      <div>
        {page?.items.map((item) => {
          const flagged = aboveThreshold(item.score, item.threshold);
          return (
            <button
              key={item.id}
              type="button"
              className={item.id === selectedId ? "row selected" : "row"}
              aria-current={item.id === selectedId ? "true" : undefined}
              onClick={() => onSelect(item.id)}
            >
              <strong>{formatMoney(item.amount)}</strong>
              <p className="meta">{item.direction === "debit" ? "Debit" : "Credit"}</p>
              <p className="meta">{item.external_id}</p>
              <p className={flagged ? "meta alert-score" : "meta"}>
                {scoreLabel(item.scoring_kind, item.score_semantics)} {formatScore(item.score)}
                {flagged ? ", at or above threshold" : ""}
              </p>
              <p className="meta">
                {stateLabel(item.state)}, revision {item.revision}
              </p>
            </button>
          );
        })}
      </div>
      <div className="pager">
        <button type="button" className="secondary" onClick={onPrevious} disabled={!hasPrevious || busy}>
          Previous page
        </button>
        <button
          type="button"
          className="secondary"
          onClick={onNext}
          disabled={!page?.next_cursor || busy}
        >
          Next page
        </button>
      </div>
    </section>
  );
}
