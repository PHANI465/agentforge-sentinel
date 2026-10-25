"""Candidate models from the frozen protocol: the production rule and two sklearn families.

Every fitted step (scaler, encoder, model) sees training rows only; validation and test are
transformed with the fitted pipeline unchanged. The currency encoder uses the protocol's
fixed category list (no data-dependent category discovery).
"""
from __future__ import annotations

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from sentinel.scoring import RULE_CONFIG


def signed_log1p(values):
    """Monotone squashing for heavy-tailed counts/amounts; keeps the -1 'no history' marker
    distinguishable (maps to -log 2). Stateless, so nothing is learned from any split."""
    x = np.asarray(values, dtype=float)
    return np.sign(x) * np.log1p(np.abs(x))


class RuleR1:
    """sentinel.scoring.rule_score (velocity-amount-rules r1) recomputed from the f1 features:
    0.6 if the amount reaches the currency's large-amount cutoff, plus 0.2 per prior
    transaction in the last hour (capped at 0.6), capped at 1. A heuristic, not a probability.
    """

    def __init__(self, feature_names: list[str]):
        self.amount = feature_names.index("amount_minor")
        self.count_1h = feature_names.index("count_1h")
        self.currency = len(feature_names)  # currency is appended after the f1 features

    def fit(self, X, y=None):
        return self

    def score(self, X) -> np.ndarray:
        large = np.array([float(row[self.amount]) >= RULE_CONFIG["large_amount_minor"][row[self.currency]]
                          for row in X], dtype=float)
        velocity = np.minimum(RULE_CONFIG["velocity_points_cap"],
                              RULE_CONFIG["velocity_points_per_prior"]
                              * X[:, self.count_1h].astype(float))
        return np.round(np.minimum(1.0, RULE_CONFIG["large_amount_points"] * large + velocity), 6)


def _preprocessor(protocol: dict, scale: bool) -> ColumnTransformer:
    n = len(protocol["features"])
    numeric = [("log", FunctionTransformer(signed_log1p))]
    if scale:
        numeric.append(("scale", StandardScaler()))
    currencies = protocol["categorical_features"]["currency"]["values"]
    return ColumnTransformer([
        ("numeric", Pipeline(numeric), list(range(n))),
        ("currency", OneHotEncoder(categories=[currencies], handle_unknown="error",
                                   sparse_output=False), [n]),
    ])


def build(protocol: dict, candidate: dict):
    kind, params, seed = candidate["kind"], candidate["params"], protocol["random_seed"]
    if kind == "rule":
        return RuleR1(list(protocol["features"]))
    if kind == "logistic_regression":
        return Pipeline([("prep", _preprocessor(protocol, scale=True)),
                         ("model", LogisticRegression(C=params["C"],
                                                      class_weight=params["class_weight"],
                                                      max_iter=params["max_iter"],
                                                      random_state=seed))])
    if kind == "hist_gradient_boosting":
        return Pipeline([("prep", _preprocessor(protocol, scale=False)),
                         ("model", HistGradientBoostingClassifier(
                             learning_rate=params["learning_rate"], max_iter=params["max_iter"],
                             max_leaf_nodes=params["max_leaf_nodes"],
                             class_weight=params["class_weight"], early_stopping=False,
                             random_state=seed))])
    raise ValueError(f"unknown candidate kind {kind!r}")


def scores(model, X) -> np.ndarray:
    if isinstance(model, RuleR1):
        return model.score(X)
    return model.predict_proba(X)[:, 1]
