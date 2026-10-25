import type {
  ArtifactRef,
  ModelProvenance,
  ModelResults,
  PolicyStats,
  ReliabilityBin,
  ScorerInfo,
  ScoringInputs,
  SliceRow,
  SplitCounts,
} from "./types";

const CURRENCIES = new Set(["USD", "INR", "GBP", "JPY"]);
const SEMANTICS = new Set(["heuristic", "estimated_probability", "uncalibrated_score"]);
const HASH = /^[0-9a-f]{64}$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function count(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : null;
}

function rate(value: unknown): number | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  const parsed = finite(value);
  return parsed === null ? undefined : parsed;
}

/** Present number or null. Missing and non-numeric values are invalid. */
function requiredNullableFinite(record: Record<string, unknown>, key: string): number | null | undefined {
  if (!Object.hasOwn(record, key)) return undefined;
  const item = record[key];
  if (item === null) return null;
  const parsed = finite(item);
  return parsed === null ? undefined : parsed;
}

/** Omitted or null becomes null. A non-count is invalid. */
function optionalCount(record: Record<string, unknown>, key: string): number | null | undefined {
  if (!Object.hasOwn(record, key) || record[key] === null) return null;
  const parsed = count(record[key]);
  return parsed === null ? undefined : parsed;
}

export function acceptArtifact(value: unknown): ArtifactRef | null {
  if (!isRecord(value)) return null;
  const name = text(value.name);
  const version = text(value.version);
  const sha256 = text(value.sha256);
  if (!name || !version || !sha256 || !HASH.test(sha256)) return null;
  return { name, version, sha256 };
}

export function acceptModelProvenance(value: unknown): ModelProvenance | null {
  if (!isRecord(value)) return null;
  const protocolVersion = text(value.protocol_version);
  const protocolSha = text(value.protocol_sha256);
  const selectionSha = text(value.selection_sha256);
  const candidate = text(value.candidate);
  const artifactSha = text(value.artifact_sha256);
  const featureVersion = text(value.feature_version);
  const resultsId = text(value.results_id);
  if (
    !protocolVersion ||
    !protocolSha ||
    !HASH.test(protocolSha) ||
    !selectionSha ||
    !HASH.test(selectionSha) ||
    !candidate ||
    !artifactSha ||
    !HASH.test(artifactSha) ||
    !featureVersion ||
    !resultsId ||
    value.threshold_source !== "validation_frozen_threshold"
  ) {
    return null;
  }
  return {
    protocol_version: protocolVersion,
    protocol_sha256: protocolSha,
    selection_sha256: selectionSha,
    candidate,
    artifact_sha256: artifactSha,
    feature_version: featureVersion,
    threshold_source: "validation_frozen_threshold",
    results_id: resultsId,
  };
}

export function acceptScoringInputs(value: unknown): ScoringInputs | null {
  if (!isRecord(value) || value.feature_version !== "f1" || !isRecord(value.values)) return null;
  const currency = text(value.currency);
  const home = text(value.profile_home_currency);
  const opened = text(value.profile_opened_at);
  const history = count(value.history_rows);
  const disclosures = count(value.disclosures_used);
  if (!currency || !CURRENCIES.has(currency) || !home || !CURRENCIES.has(home) || !opened) return null;
  if (history === null || disclosures === null) return null;
  const values: Record<string, number> = {};
  for (const [key, item] of Object.entries(value.values)) {
    if (!text(key) || !Number.isSafeInteger(item)) return null;
    values[key] = item as number;
  }
  return {
    feature_version: "f1",
    values,
    currency: currency as ScoringInputs["currency"],
    history_rows: history,
    disclosures_used: disclosures,
    profile_home_currency: home as ScoringInputs["profile_home_currency"],
    profile_opened_at: opened,
  };
}

function acceptPolicy(value: unknown): PolicyStats | null {
  if (!isRecord(value)) return null;
  const flagged = count(value.flagged);
  const tp = count(value.tp);
  const fp = count(value.fp);
  const fn = count(value.fn);
  const tn = count(value.tn);
  const precision = rate(value.precision);
  const recall = rate(value.recall);
  const falsePositive = rate(value.false_positive_rate);
  if (
    flagged === null ||
    tp === null ||
    fp === null ||
    fn === null ||
    tn === null ||
    precision === undefined ||
    recall === undefined ||
    falsePositive === undefined
  ) {
    return null;
  }
  return {
    flagged,
    tp,
    fp,
    fn,
    tn,
    precision,
    recall,
    false_positive_rate: falsePositive,
  };
}

function acceptInterval(value: unknown): [number, number] | null | undefined {
  if (value === null) return null;
  if (!Array.isArray(value) || value.length !== 2) return undefined;
  const low = finite(value[0]);
  const high = finite(value[1]);
  if (low === null || high === null) return undefined;
  return [low, high];
}

export function acceptScorerInfo(value: unknown): ScorerInfo | null {
  if (!isRecord(value)) return null;
  if (value.mode !== "rule" && value.mode !== "model") return null;
  if (value.scoring_kind !== "rule" && value.scoring_kind !== "model") return null;
  if (typeof value.score_semantics !== "string" || !SEMANTICS.has(value.score_semantics)) return null;
  const scorer = acceptArtifact(value.scorer);
  const features = acceptArtifact(value.features);
  const thresholdPolicy = acceptArtifact(value.threshold_policy);
  const threshold = finite(value.threshold);
  if (!scorer || !features || !thresholdPolicy || threshold === null) return null;
  if (value.alert_rule !== "score >= threshold") return null;
  if (!Array.isArray(value.notes) || !value.notes.every((item) => typeof item === "string")) return null;
  let model: ModelProvenance | null = null;
  if (value.model !== null) {
    model = acceptModelProvenance(value.model);
    if (!model) return null;
  }
  if (value.results_id !== null && !text(value.results_id)) return null;
  return {
    mode: value.mode,
    scoring_kind: value.scoring_kind,
    score_semantics: value.score_semantics as ScorerInfo["score_semantics"],
    scorer,
    features,
    threshold_policy: thresholdPolicy,
    threshold,
    alert_rule: "score >= threshold",
    model,
    results_id: value.results_id === null ? null : (value.results_id as string),
    notes: value.notes as string[],
  };
}

function acceptSplit(value: unknown): SplitCounts | null {
  if (!isRecord(value)) return null;
  const rows = count(value.rows);
  const legitimate = count(value.legitimate);
  const fraud = count(value.fraud);
  const unknown = count(value.unknown_excluded);
  const days = count(value.decision_days);
  const observable = optionalCount(value, "labels_observable_by_horizon");
  if (
    rows === null ||
    legitimate === null ||
    fraud === null ||
    unknown === null ||
    days === null ||
    observable === undefined
  ) {
    return null;
  }
  return {
    rows,
    legitimate,
    fraud,
    unknown_excluded: unknown,
    labels_observable_by_horizon: observable,
    decision_days: days,
  };
}

function acceptSlice(value: unknown): SliceRow | null {
  const policy = acceptPolicy(value);
  if (!policy || !isRecord(value)) return null;
  const dimension = text(value.dimension);
  const sliceValue = typeof value.value === "string" ? value.value : null;
  const rows = count(value.rows);
  const fraud = count(value.fraud);
  if (!dimension || sliceValue === null || rows === null || fraud === null) return null;
  return { ...policy, dimension, value: sliceValue, rows, fraud };
}

function acceptBin(value: unknown): ReliabilityBin | null {
  if (!isRecord(value)) return null;
  const lo = finite(value.lo);
  const hi = finite(value.hi);
  const n = count(value.n);
  const mean = requiredNullableFinite(value, "mean_score");
  const fraudRate = requiredNullableFinite(value, "fraud_rate");
  if (lo === null || hi === null || n === null || mean === undefined || fraudRate === undefined) return null;
  return { lo, hi, n, mean_score: mean, fraud_rate: fraudRate };
}

export function acceptModelResults(value: unknown): ModelResults | null {
  if (!isRecord(value)) return null;
  if (value.label !== "offline synthetic benchmark" || value.synthetic !== true) return null;
  const resultsId = text(value.results_id);
  const protocolVersion = text(value.protocol_version);
  const protocolSha = text(value.protocol_sha256);
  const selectionSha = text(value.selection_sha256);
  const artifactSha = text(value.artifact_sha256);
  const selected = text(value.selected);
  const ranking = text(value.review_ranking);
  const reviewK = count(value.review_k_per_day);
  const frozen = finite(value.frozen_threshold);
  if (
    !resultsId ||
    !protocolVersion ||
    !protocolSha ||
    !HASH.test(protocolSha) ||
    !selectionSha ||
    !HASH.test(selectionSha) ||
    !artifactSha ||
    !HASH.test(artifactSha) ||
    !selected ||
    !ranking ||
    reviewK === null ||
    frozen === null
  ) {
    return null;
  }
  if (!isRecord(value.windows) || !isRecord(value.label_views) || !isRecord(value.splits)) return null;
  const windows: Record<string, [number, number]> = {};
  for (const [key, item] of Object.entries(value.windows)) {
    const pair = acceptInterval(item);
    if (!text(key) || !pair) return null;
    windows[key] = pair;
  }
  const labelViews: Record<string, string> = {};
  for (const [key, item] of Object.entries(value.label_views)) {
    if (!text(key) || typeof item !== "string") return null;
    labelViews[key] = item;
  }
  const splits: Record<string, SplitCounts> = {};
  for (const key of ["train", "validation", "test"]) {
    const split = acceptSplit(value.splits[key]);
    if (!split) return null;
    splits[key] = split;
  }
  if (!Array.isArray(value.candidates) || !isRecord(value.selected_policy)) return null;
  const candidates = [];
  for (const item of value.candidates) {
    if (!isRecord(item)) return null;
    const name = text(item.name);
    const kind = text(item.kind);
    const validationAp = finite(item.validation_average_precision);
    const testAp = finite(item.test_average_precision);
    const trapezoid = finite(item.test_pr_auc_trapezoid);
    const daily = acceptPolicy(item.test_daily_top_k);
    if (!("test_brier" in item)) return null;
    const brier = item.test_brier === null ? null : finite(item.test_brier);
    if (!name || !kind || validationAp === null || testAp === null || trapezoid === null || !daily || brier === null && item.test_brier !== null) {
      return null;
    }
    candidates.push({
      name,
      kind,
      validation_average_precision: validationAp,
      test_average_precision: testAp,
      test_pr_auc_trapezoid: trapezoid,
      test_daily_top_k: daily,
      test_brier: brier,
    });
  }
  const dailyTop = acceptPolicy(value.selected_policy.daily_top_k);
  const frozenPolicy = acceptPolicy(value.selected_policy.frozen_threshold);
  if (!dailyTop || !frozenPolicy || !isRecord(value.uncertainty) || !isRecord(value.calibration)) return null;
  const averagePrecision = acceptInterval(value.uncertainty.average_precision);
  const recallAt = acceptInterval(value.uncertainty.recall_at_capacity);
  const precisionAt = acceptInterval(value.uncertainty.precision_at_capacity);
  const replicates = count(value.uncertainty.replicates);
  const accounts = count(value.uncertainty.accounts);
  const skipped = count(value.uncertainty.skipped_one_class);
  const method = text(value.uncertainty.method);
  if (
    averagePrecision === undefined ||
    recallAt === undefined ||
    precisionAt === undefined ||
    replicates === null ||
    accounts === null ||
    skipped === null ||
    !method
  ) {
    return null;
  }
  const brier = finite(value.calibration.brier);
  if (brier === null || typeof value.calibration.note !== "string" || !Array.isArray(value.calibration.reliability)) {
    return null;
  }
  const reliability: ReliabilityBin[] = [];
  for (const item of value.calibration.reliability) {
    const bin = acceptBin(item);
    if (!bin) return null;
    reliability.push(bin);
  }
  if (!Array.isArray(value.slices) || !Array.isArray(value.pr_curve) || !Array.isArray(value.limitations)) return null;
  const slices: SliceRow[] = [];
  for (const item of value.slices) {
    const slice = acceptSlice(item);
    if (!slice) return null;
    slices.push(slice);
  }
  const prCurve: { recall: number; precision: number }[] = [];
  for (const item of value.pr_curve) {
    if (!isRecord(item)) return null;
    const recall = finite(item.recall);
    const precision = finite(item.precision);
    if (recall === null || precision === null) return null;
    prCurve.push({ recall, precision });
  }
  if (!value.limitations.every((item) => typeof item === "string")) return null;
  return {
    results_id: resultsId,
    label: "offline synthetic benchmark",
    synthetic: true,
    protocol_version: protocolVersion,
    protocol_sha256: protocolSha,
    selection_sha256: selectionSha,
    artifact_sha256: artifactSha,
    selected,
    windows,
    label_views: labelViews,
    review_k_per_day: reviewK,
    review_ranking: ranking,
    frozen_threshold: frozen,
    splits,
    candidates,
    selected_policy: { daily_top_k: dailyTop, frozen_threshold: frozenPolicy },
    uncertainty: {
      method,
      replicates,
      accounts,
      skipped_one_class: skipped,
      average_precision: averagePrecision,
      recall_at_capacity: recallAt,
      precision_at_capacity: precisionAt,
    },
    calibration: { brier, reliability, note: value.calibration.note },
    slices,
    pr_curve: prCurve,
    limitations: value.limitations as string[],
  };
}
