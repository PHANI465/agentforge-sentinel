"""C06 review R27: the package checker requires the accepted model/data identity assets byte
for byte and refuses a missing, altered or extra shipped model file."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_package  # noqa: E402


def shipped() -> dict[str, bytes]:
    return {name: (ROOT / name).read_bytes() for name in check_package.MODEL_ASSETS}


def test_exact_assets_pass():
    assert check_package.check_assets(shipped(), "", "wheel", exclusive=True) == []


def test_a_missing_asset_fails():
    names = shipped()
    del names["ml/artifacts/p1/model.joblib"]
    assert check_package.check_assets(names, "", "wheel", exclusive=True) == [
        "wheel: model asset ml/artifacts/p1/model.joblib missing"]


def test_an_altered_asset_fails():
    names = shipped()
    names["ml/results/p1/test_report.json"] += b" "
    assert check_package.check_assets(names, "", "wheel", exclusive=True) == [
        "wheel: model asset ml/results/p1/test_report.json differs from source"]


def test_an_extra_shipped_model_file_fails_in_the_wheel():
    names = {**shipped(), "ml/artifacts/p2/model.joblib": b"x", "ml/models.py": b"code"}
    assert check_package.check_assets(names, "", "wheel", exclusive=True) == [
        "wheel: unexpected file ml/artifacts/p2/model.joblib"]


def test_the_asset_list_covers_the_four_migrations_and_registered_scorer():
    assert len(check_package.MIGRATIONS) == 4
    assert all((ROOT / asset).is_file() for asset in check_package.MODEL_ASSETS)
