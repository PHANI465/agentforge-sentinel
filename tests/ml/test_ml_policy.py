"""C04 metric and policy definitions, checked against hand-computed examples."""
import numpy as np
import pytest

from ml import evaluate


def test_average_precision_is_not_trapezoidal_pr_auc():
    y, s = [1, 0, 1, 0], [0.9, 0.8, 0.7, 0.6]
    # AP = sum (R_n - R_{n-1}) P_n = 0.5 * 1 + 0.5 * (2/3)
    assert evaluate.average_precision(y, s) == pytest.approx(5 / 6)
    # Trapezoid over the curve points (R, P): (0,1) (0.5,1) (0.5,0.5) (1,2/3) (1,0.5)
    # = 0.5 * 1 + 0.5 * (0.5 + 2/3) / 2 = 0.791667
    assert evaluate.pr_auc_trapezoid(y, s) == pytest.approx(0.5 + 0.5 * (0.5 + 2 / 3) / 2)


def test_daily_top_k_breaks_ties_by_external_id_and_resets_each_day():
    scores = [0.5, 0.5, 0.5, 0.1, 0.9, 0.2]
    ids = ["c", "a", "b", "d", "z", "y"]
    days = [1, 1, 1, 1, 2, 2]
    flagged = evaluate.daily_top_k(scores, ids, days, k=2)
    assert flagged.tolist() == [False, True, True, False, True, True]


def test_frozen_threshold_uses_validation_rank_only():
    val_scores, val_ids = [0.9, 0.7, 0.7, 0.2], ["d", "c", "b", "a"]
    threshold = evaluate.frozen_threshold(val_scores, val_ids, n_days=2, k=1)
    assert threshold == 0.7  # rank 2 by (score desc, id asc): d(0.9), b(0.7)
    test_scores = np.array([0.95, 0.7, 0.1])
    assert (test_scores >= threshold).tolist() == [True, True, False]


def test_at_policy_counts_and_rates():
    stats = evaluate.at_policy([1, 1, 0, 0, 0], [True, False, True, False, False])
    assert stats == {"flagged": 2, "tp": 1, "fp": 1, "fn": 1, "tn": 2, "precision": 0.5,
                     "recall": 0.5, "false_positive_rate": round(1 / 3, 6)}
    assert evaluate.at_policy([0, 0], [False, False])["precision"] is None


def test_brier_and_reliability_bins():
    assert evaluate.brier([1, 0], [0.8, 0.4]) == pytest.approx((0.04 + 0.16) / 2)
    bins = evaluate.reliability([1, 0, 0, 1], [0.05, 0.15, 0.95, 1.0], bins=10)
    assert [b["n"] for b in bins] == [1, 1, 0, 0, 0, 0, 0, 0, 0, 2]
    assert bins[9]["fraud_rate"] == 0.5


def test_account_bootstrap_keeps_accounts_together_and_is_seeded():
    y = np.array([1, 1, 0, 0, 0, 0])
    scores = np.array([0.9, 0.8, 0.3, 0.2, 0.1, 0.4])
    flagged = np.array([True, True, False, False, False, False])
    accounts = np.array(["A", "A", "B", "B", "C", "C"])
    one = evaluate.bootstrap(y, scores, flagged, accounts, replicates=50, seed=3)
    two = evaluate.bootstrap(y, scores, flagged, accounts, replicates=50, seed=3)
    assert one == two and one["accounts"] == 3
    # Account A holds every positive: replicates that miss it are one-class and skipped.
    assert one["skipped_one_class"] > 0
    assert one["recall_at_capacity"] == [1.0, 1.0]  # A's rows are always flagged together
