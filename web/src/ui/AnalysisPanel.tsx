import { useEffect, useState } from "react";
import type { SentinelClient } from "../api/client";
import { allows } from "../api/case";
import { artifactLabel, analysisUnavailableMessage, formatScore, modelReportMissingMessage } from "../api/format";
import type { ApiResult, ModelResults, ScorerInfo, SessionView } from "../api/types";
import { ModelReport } from "./ModelReport";

export type AnalysisState =
  | { phase: "loading" }
  | { phase: "denied" }
  | { phase: "unavailable" }
  | { phase: "failed"; message: string }
  | { phase: "rule"; scorer: ScorerInfo }
  | { phase: "report-loading"; scorer: ScorerInfo }
  | { phase: "report"; scorer: ScorerInfo; results: ModelResults }
  | { phase: "report-missing"; scorer: ScorerInfo; message: string }
  | { phase: "report-failed"; scorer: ScorerInfo; message: string };

function scorerOf(state: AnalysisState): ScorerInfo | null {
  if (state.phase === "loading" || state.phase === "denied" || state.phase === "unavailable" || state.phase === "failed") {
    return null;
  }
  return state.scorer;
}

function reportFailure(result: ApiResult<ModelResults>): AnalysisState["phase"] {
  if (!result.ok && (result.status === 404 || result.code === "not_found")) return "report-missing";
  return "report-failed";
}

export function useAnalysis({
  client,
  token,
  session,
  onConfigured,
}: {
  client: SentinelClient;
  token: string;
  session: SessionView;
  onConfigured?: (scorer: ScorerInfo | null) => void;
}): AnalysisState {
  const [state, setState] = useState<AnalysisState>({ phase: "loading" });
  const capabilities = session.capabilities.join("\0");

  useEffect(() => {
    onConfigured?.(scorerOf(state));
  }, [onConfigured, state]);

  useEffect(() => {
    let cancelled = false;
    const canRead = allows(session, "read_case");
    if (!canRead) {
      setState({ phase: "denied" });
      return;
    }
    if (typeof client.scoring !== "function" || typeof client.modelResults !== "function") {
      setState({ phase: "unavailable" });
      return;
    }
    setState({ phase: "loading" });
    void (async () => {
      const scoring = await client.scoring(token);
      if (cancelled) return;
      if (!scoring.ok) {
        if (scoring.status === 404 || scoring.status === 405) {
          setState({ phase: "unavailable" });
          return;
        }
        setState({ phase: "failed", message: scoring.message });
        return;
      }
      const scorer = scoring.data;
      if (!scorer.results_id) {
        setState({ phase: "rule", scorer });
        return;
      }
      setState({ phase: "report-loading", scorer });
      const report = await client.modelResults(token, scorer.results_id);
      if (cancelled) return;
      if (!report.ok) {
        const phase = reportFailure(report);
        setState(
          phase === "report-missing"
            ? { phase, scorer, message: modelReportMissingMessage() }
            : { phase: "report-failed", scorer, message: report.message },
        );
        return;
      }
      setState({ phase: "report", scorer, results: report.data });
    })();
    return () => {
      cancelled = true;
    };
  }, [capabilities, client, session, token]);

  return state;
}

export function ScorerStrip({ state }: { state: AnalysisState }) {
  const scorer = scorerOf(state);
  return (
    <section className="analysis" id="scoring" aria-labelledby="scoring-heading">
      <h2 id="scoring-heading">Configured scorer</h2>
      {state.phase === "loading" ? <p>Loading the configured scorer.</p> : null}
      {state.phase === "denied" ? <p>This session cannot read the configured scorer.</p> : null}
      {state.phase === "unavailable" ? <p>{analysisUnavailableMessage()}</p> : null}
      {state.phase === "failed" ? <p>{state.message}</p> : null}
      {scorer ? (
        <>
          <p>
            {artifactLabel(scorer.scorer)} ({scorer.scoring_kind}, {scorer.score_semantics}). Features{" "}
            {artifactLabel(scorer.features)}. Threshold policy {artifactLabel(scorer.threshold_policy)}.
          </p>
          <p className="threshold-figure">{formatScore(scorer.threshold)}</p>
          <p>Alert rule: {scorer.alert_rule}.</p>
          {scorer.notes.length > 0 ? (
            <ul>
              {scorer.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}
          {state.phase === "report" ? <a href="#model-results">Read the offline benchmark</a> : null}
          {state.phase === "report-loading" ? <p>Loading the offline benchmark.</p> : null}
          {state.phase === "rule" ? <p>This server has no offline model report for the configured scorer.</p> : null}
          {state.phase === "report-missing" || state.phase === "report-failed" ? <p>{state.message}</p> : null}
        </>
      ) : null}
    </section>
  );
}

export function ModelSection({ state }: { state: AnalysisState }) {
  if (state.phase !== "report") return null;
  return <ModelReport results={state.results} />;
}
