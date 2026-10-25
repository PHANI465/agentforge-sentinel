import { useState } from "react";
import { formatCount, formatRate, formatScore } from "../api/format";
import type { ModelResults, PolicyStats, SliceRow } from "../api/types";

const SPLIT_ORDER = ["burn_in", "train", "validation", "test"] as const;
const SLICE_ORDER = ["currency", "scenario", "activity_count_24h", "test_week"];

function splitTitle(key: string): string {
  if (key === "burn_in") return "Burn-in";
  if (key === "train") return "Train";
  if (key === "validation") return "Validation";
  if (key === "test") return "Test";
  return key;
}

function sliceCaption(dimension: string): string {
  if (dimension === "currency") return "Currency slices, kept separate";
  if (dimension === "scenario") {
    return "Scenario slices. Offline hidden synthetic truth, not a live feature and not a model input.";
  }
  if (dimension === "activity_count_24h") return "Activity count in 24 hours";
  if (dimension === "test_week") return "Test week";
  return dimension;
}

function CountTable({ caption, stats }: { caption: string; stats: PolicyStats }) {
  const rows: [string, string][] = [
    ["Flagged", formatCount(stats.flagged)],
    ["True positives", formatCount(stats.tp)],
    ["False positives", formatCount(stats.fp)],
    ["False negatives", formatCount(stats.fn)],
    ["True negatives", formatCount(stats.tn)],
    ["Precision", formatRate(stats.precision)],
    ["Recall", formatRate(stats.recall)],
    ["False positive rate", formatRate(stats.false_positive_rate)],
  ];
  return (
    <div className="table-wrap">
      <table className="data">
        <caption>{caption}</caption>
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SliceTable({ dimension, rows }: { dimension: string; rows: SliceRow[] }) {
  return (
    <div className="table-wrap">
      <table className="data">
        <caption>{sliceCaption(dimension)}</caption>
        <thead>
          <tr>
            <th scope="col">Value</th>
            <th scope="col">Rows</th>
            <th scope="col">Fraud</th>
            <th scope="col">Flagged</th>
            <th scope="col">True positives</th>
            <th scope="col">False positives</th>
            <th scope="col">False negatives</th>
            <th scope="col">True negatives</th>
            <th scope="col">Precision</th>
            <th scope="col">Recall</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${dimension}-${row.value}`}>
              <th scope="row">{row.value}</th>
              <td>{formatCount(row.rows)}</td>
              <td>{formatCount(row.fraud)}</td>
              <td>{formatCount(row.flagged)}</td>
              <td>{formatCount(row.tp)}</td>
              <td>{formatCount(row.fp)}</td>
              <td>{formatCount(row.fn)}</td>
              <td>{formatCount(row.tn)}</td>
              <td>{formatRate(row.precision)}</td>
              <td>{formatRate(row.recall)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PrecisionRecall({ results }: { results: ModelResults }) {
  const [open, setOpen] = useState(false);
  const points = results.pr_curve;
  const path = points
    .map((point) => `${(point.recall * 100).toFixed(4)},${((1 - point.precision) * 100).toFixed(4)}`)
    .join(" ");
  return (
    <div className="block">
      <h3>Test precision-recall curve</h3>
      <p>
        Selected model {results.selected}. {formatCount(points.length)} points from this report. Recall and precision
        come from these points.
      </p>
      {points.length === 0 ? <p>This report has no precision-recall points.</p> : null}
      {points.length > 0 ? (
        <svg
          className="pr-chart"
          viewBox="-8 -4 116 112"
          role="img"
          aria-label={`Test precision-recall curve for ${results.selected}, ${points.length} points`}
        >
          <polyline points={path} fill="none" stroke="#143e63" strokeWidth="1.4" />
          <text x="50" y="108" textAnchor="middle" fontSize="4">
            Recall
          </text>
          <text x="-2" y="50" fontSize="4" transform="rotate(-90 2 50)">
            Precision
          </text>
        </svg>
      ) : null}
      <button
        type="button"
        aria-expanded={open}
        aria-controls="pr-points"
        onClick={() => setOpen((current) => !current)}
      >
        {open ? "Hide precision-recall points" : "Show precision-recall points"}
      </button>
      {open ? (
        <div className="table-wrap" id="pr-points">
          <table className="data">
            <caption>Test precision-recall points</caption>
            <thead>
              <tr>
                <th scope="col">Recall</th>
                <th scope="col">Precision</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point, index) => (
                <tr key={`${point.recall}-${point.precision}-${index}`}>
                  <td>{formatScore(point.recall)}</td>
                  <td>{formatScore(point.precision)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

export function ModelReport({ results }: { results: ModelResults }) {
  const grouped = new Map<string, SliceRow[]>();
  for (const row of results.slices) {
    const current = grouped.get(row.dimension) ?? [];
    current.push(row);
    grouped.set(row.dimension, current);
  }
  const dimensions = [
    ...SLICE_ORDER.filter((dimension) => grouped.has(dimension)),
    ...[...grouped.keys()].filter((dimension) => !SLICE_ORDER.includes(dimension)),
  ];
  const windowKeys = [
    ...SPLIT_ORDER.filter((key) => results.windows[key]),
    ...Object.keys(results.windows).filter((key) => !SPLIT_ORDER.includes(key as (typeof SPLIT_ORDER)[number])),
  ];
  return (
    <section className="report" aria-labelledby="model-results">
      <h2 id="model-results" tabIndex={-1}>
        {results.label}
      </h2>
      <p>Synthetic data. This is an offline benchmark, not a live tenant statistic and not a production result.</p>
      <p className="threshold-figure">{formatScore(results.frozen_threshold)}</p>
      <p>
        Frozen online threshold for {results.selected}. Online alerts use this threshold. The daily top-
        {formatCount(results.review_k_per_day)} review is a separate offline policy.
      </p>
      <p className="meta">
        Results {results.results_id}. Protocol {results.protocol_version}. Ranking {results.review_ranking}.
      </p>
      {results.limitations.length === 0 ? <p>This report lists no limitations.</p> : null}
      <ul>
        {results.limitations.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <div className="block">
        <h3>Splits and delayed labels</h3>
        <div className="table-wrap">
          <table className="data">
            <caption>Decision-time windows, days from the generator epoch, start inclusive and end exclusive</caption>
            <thead>
              <tr>
                <th scope="col">Window</th>
                <th scope="col">Start</th>
                <th scope="col">End</th>
              </tr>
            </thead>
            <tbody>
              {windowKeys.map((key) => (
                <tr key={key}>
                  <th scope="row">{splitTitle(key)}</th>
                  <td>{String(results.windows[key][0])}</td>
                  <td>{String(results.windows[key][1])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="table-wrap">
          <table className="data">
            <caption>Train, validation, and test counts</caption>
            <thead>
              <tr>
                <th scope="col">Split</th>
                <th scope="col">Rows</th>
                <th scope="col">Legitimate</th>
                <th scope="col">Fraud</th>
                <th scope="col">Unknown excluded</th>
                <th scope="col">Labels observable by the horizon</th>
                <th scope="col">Decision days</th>
              </tr>
            </thead>
            <tbody>
              {["train", "validation", "test"].map((key) => {
                const split = results.splits[key];
                return (
                  <tr key={key}>
                    <th scope="row">{splitTitle(key)}</th>
                    <td>{formatCount(split.rows)}</td>
                    <td>{formatCount(split.legitimate)}</td>
                    <td>{formatCount(split.fraud)}</td>
                    <td>{formatCount(split.unknown_excluded)}</td>
                    <td>
                      {split.labels_observable_by_horizon === null
                        ? "not reported"
                        : formatCount(split.labels_observable_by_horizon)}
                    </td>
                    <td>{formatCount(split.decision_days)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <dl>
          {Object.entries(results.label_views).map(([key, value]) => (
            <div key={key}>
              <dt>{splitTitle(key)} label view</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="block">
        <h3>Baseline comparison</h3>
        <p>Average precision is listed separately from the trapezoidal precision-recall area.</p>
        {results.candidates.length === 0 ? <p>This report has no baseline comparison.</p> : null}
        {results.candidates.length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <caption>Validation and test average precision</caption>
              <thead>
                <tr>
                  <th scope="col">Candidate</th>
                  <th scope="col">Kind</th>
                  <th scope="col">Validation average precision</th>
                  <th scope="col">Test average precision</th>
                  <th scope="col">Trapezoidal precision-recall area</th>
                  <th scope="col">Test Brier</th>
                  <th scope="col">Role</th>
                </tr>
              </thead>
              <tbody>
                {results.candidates.map((candidate) => (
                  <tr key={candidate.name} className={candidate.name === results.selected ? "selected-record" : undefined}>
                    <th scope="row">{candidate.name}</th>
                    <td>{candidate.kind}</td>
                    <td>{formatScore(candidate.validation_average_precision)}</td>
                    <td>{formatScore(candidate.test_average_precision)}</td>
                    <td>{formatScore(candidate.test_pr_auc_trapezoid)}</td>
                    <td>{candidate.test_brier === null ? "not reported" : formatScore(candidate.test_brier)}</td>
                    <td>{candidate.name === results.selected ? "selected" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
      <div className="block report-grid">
        <CountTable
          caption={`Frozen online threshold ${formatScore(results.frozen_threshold)}`}
          stats={results.selected_policy.frozen_threshold}
        />
        <CountTable
          caption={`Offline daily top-${formatCount(results.review_k_per_day)} review`}
          stats={results.selected_policy.daily_top_k}
        />
      </div>
      <div className="block">
        <h3>Uncertainty</h3>
        <p>{results.uncertainty.method}</p>
        <p>
          Replicates {formatCount(results.uncertainty.replicates)}. Accounts {formatCount(results.uncertainty.accounts)}.
          One-class replicates skipped {formatCount(results.uncertainty.skipped_one_class)}.
        </p>
        <p>
          Average precision interval{" "}
          {results.uncertainty.average_precision
            ? `${formatScore(results.uncertainty.average_precision[0])} to ${formatScore(results.uncertainty.average_precision[1])}`
            : "not reported"}
          .
        </p>
        <p>
          Precision at capacity interval{" "}
          {results.uncertainty.precision_at_capacity
            ? `${formatScore(results.uncertainty.precision_at_capacity[0])} to ${formatScore(results.uncertainty.precision_at_capacity[1])}`
            : "not reported"}
          .
        </p>
        <p>
          Recall at capacity interval{" "}
          {results.uncertainty.recall_at_capacity
            ? `${formatScore(results.uncertainty.recall_at_capacity[0])} to ${formatScore(results.uncertainty.recall_at_capacity[1])}`
            : "not reported"}
          .
        </p>
      </div>
      <div className="block">
        <h3>Calibration</h3>
        <p>Brier {formatScore(results.calibration.brier)}.</p>
        <p>{results.calibration.note}</p>
        {results.calibration.reliability.length === 0 ? <p>This report has no reliability bins.</p> : null}
        {results.calibration.reliability.length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <caption>Reliability bins</caption>
              <thead>
                <tr>
                  <th scope="col">From</th>
                  <th scope="col">To</th>
                  <th scope="col">Count</th>
                  <th scope="col">Mean score</th>
                  <th scope="col">Fraud rate</th>
                </tr>
              </thead>
              <tbody>
                {results.calibration.reliability.map((bin) => (
                  <tr key={`${bin.lo}-${bin.hi}`}>
                    <td>{formatScore(bin.lo)}</td>
                    <td>{formatScore(bin.hi)}</td>
                    <td>{formatCount(bin.n)}</td>
                    <td>{formatScore(bin.mean_score)}</td>
                    <td>{formatScore(bin.fraud_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
      <div className="block">
        <h3>Error slices</h3>
        {dimensions.length === 0 ? <p>This report has no error slices.</p> : null}
        {dimensions.map((dimension) => (
          <SliceTable key={dimension} dimension={dimension} rows={grouped.get(dimension) ?? []} />
        ))}
      </div>
      <PrecisionRecall results={results} />
    </section>
  );
}
