"""C04 end-to-end on a tiny protocol: select freezes without test labels, test runs once,
--reproduce verifies, and a changed protocol is refused."""
import json

import pytest

from ml import dataset, run
from ml import protocol as proto

TINY = {
    "accounts": 40, "days": 75, "fraud_account_rate": 0.6, "lookalike_account_rate": 0.2,
    "daily_rate_range": [0.5, 1.5], "max_rows": 100000,
}


@pytest.fixture
def paths(tmp_path):
    document, _ = proto.load()
    document = json.loads(json.dumps(document))
    document["protocol_version"] = "tiny"
    document["generator"].update(TINY)
    document["windows"].update({"burn_in": [0, 3], "train": [3, 25], "validation": [26, 40],
                                "test": [45, 75]})
    document["label_views"]["train"]["labels_known_by_day"] = 55
    document["label_views"]["validation"]["labels_known_by_day"] = 70
    document["review_policy"]["k_per_day"] = 3
    document["uncertainty"]["replicates"] = 20
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(document))
    return run.Paths(protocol=protocol_path, data=tmp_path / "data", run=tmp_path / "run",
                     artifacts=tmp_path / "artifacts", evals=tmp_path / "evals")


def test_select_never_touches_test_labels(paths, monkeypatch):
    seen = []
    real = dataset.splits

    def spy(protocol, snapshot, names=("train", "validation", "test")):
        seen.append(set(names))
        return real(protocol, snapshot, names)

    monkeypatch.setattr(dataset, "splits", spy)
    selection = run.select(paths)
    assert seen == [{"train", "validation"}]  # test labels are never even computed
    assert "test" not in selection["splits"]
    assert len(selection["candidates"]) == 5
    assert selection["selected"] in {c["name"] for c in selection["candidates"]}
    assert (paths.artifacts / "tiny" / "manifest.json").exists()
    assert not (paths.evals / "test_report.json").exists()


def test_frozen_test_runs_once_and_reproduces(paths):
    run.select(paths)
    report = run.test(paths)
    assert report["selected_policy"]["daily_top_k"]["flagged"] > 0
    assert {c["name"] for c in report["candidates"]} == {
        "rule_r1", "logreg_balanced", "logreg_unweighted", "hgb_unweighted", "hgb_balanced"}
    for name in ("report.md", "slices.csv", "candidates.csv", "pr_curve_selected.svg"):
        assert (paths.evals / name).exists()
    with pytest.raises(run.StageError, match="already exists"):
        run.test(paths)
    assert run.test(paths, reproduce=True) == {"reproduced": True}


def test_changed_protocol_after_selection_refuses_test(paths):
    run.select(paths)
    document = json.loads(paths.protocol.read_text())
    document["review_policy"]["k_per_day"] = 4  # any edit after selection
    paths.protocol.write_text(json.dumps(document))
    with pytest.raises(run.StageError, match="protocol changed"):
        run.test(paths)


def test_test_without_selection_is_refused(paths):
    with pytest.raises(run.StageError, match="no frozen selection"):
        run.test(paths)


def test_outputs_are_lf_and_provenance_is_line_ending_independent(paths):
    """Regression: Windows text-mode writes produced CRLF files, and the report hashed the
    selection file's raw bytes, so a fresh LF checkout could not reproduce the report."""
    run.select(paths)
    report = run.test(paths)
    written = [p for root in (paths.run, paths.artifacts, paths.evals)
               for p in root.rglob("*") if p.is_file() and p.suffix != ".joblib"]
    assert written and all(b"\r\n" not in p.read_bytes() for p in written), \
        [p.name for p in written if b"\r\n" in p.read_bytes()]
    selection = json.loads((paths.run / "selection.json").read_text(encoding="utf-8"))
    assert report["selection_sha256"] == proto.digest(selection)
