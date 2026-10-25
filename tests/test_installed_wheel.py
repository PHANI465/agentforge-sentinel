"""C07: the built wheel alone serves the accepted model. It is installed into a fresh venv
outside the checkout, with the lock's ml pins and no network, then run isolated (python -I,
no PYTHONPATH, neutral cwd) so nothing can be imported from the source tree."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from sentinel import scorers

ROOT = Path(__file__).resolve().parents[1]
VECTOR = {"amount_minor": 725_000.0, "is_credit": 0.0, "is_foreign_currency": 1.0,
          "account_age_days": 40.0, "count_1h": 2.0, "count_24h": 5.0, "small_count_1h": 1.0,
          "same_currency_sum_24h": 90_000.0, "credit_sum_24h": 0.0, "seconds_since_prev": 400.0,
          "amount_to_median_bps": 170_000.0, "prior_known_fraud": 1.0}

PROBE = r"""
import json, sys
import numpy as np
import sentinel, ml, data_pipeline
from sentinel import db, model_results, scorers
vector = json.loads(sys.argv[1])
m = scorers.ModelScorer(scorers.REGISTRY["hgb_balanced@p1"])
names = list(m.protocol["features"])
X = np.empty((1, len(names) + 1), dtype=object)
X[0, :len(names)] = [vector[n] for n in names]
X[0, len(names)] = "GBP"
print(json.dumps({
    "files": [sentinel.__file__, ml.__file__, data_pipeline.__file__],
    "score": float(m.pipeline.predict_proba(X)[0, 1]),
    "artifact": m.model.artifact_sha256,
    "migrations": sorted(p.name for p in db.MIGRATIONS.glob("*.sql")),
    "results": model_results.load("p1")["frozen_threshold"],
    "sys_path_has_src": any("sentinel-wt" in p or "agentforge" in p for p in sys.path),
}))
"""


def run(cmd, **kw):
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=600, **kw)
    assert done.returncode == 0, (cmd, done.stdout[-2000:], done.stderr[-2000:])
    return done.stdout


def test_wheel_installed_outside_the_checkout_binds_and_infers(tmp_path):
    uv = shutil.which("uv")
    assert uv, "uv is required to build and install the wheel"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
    run([uv, "build", "--wheel", "--out-dir", str(tmp_path / "dist"), str(ROOT)], env=env)
    wheel = next((tmp_path / "dist").glob("*.whl"))
    reqs = tmp_path / "requirements.txt"
    run([uv, "export", "--locked", "--extra", "ml", "--no-dev", "--no-emit-project",
         "--no-hashes", "--output-file", str(reqs)], cwd=ROOT, env=env)
    venv = tmp_path / "venv"
    run([uv, "venv", "--python", sys.executable, str(venv)], env=env)
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([uv, "pip", "install", "--offline", "--python", str(python), "--no-deps",
         "-r", str(reqs), str(wheel)], env=env)
    neutral = tmp_path / "neutral"
    neutral.mkdir()
    out = json.loads(run([str(python), "-I", "-c", PROBE, json.dumps(VECTOR)],
                         cwd=neutral, env=env))

    assert all(Path(f).resolve().is_relative_to(venv.resolve()) for f in out["files"])
    assert not out["sys_path_has_src"]
    model = scorers.ModelScorer(scorers.REGISTRY["hgb_balanced@p1"])  # in-checkout reference
    names = list(model.protocol["features"])
    X = np.empty((1, len(names) + 1), dtype=object)
    X[0, :len(names)] = [VECTOR[n] for n in names]
    X[0, len(names)] = "GBP"
    assert out["score"] == float(model.pipeline.predict_proba(X)[0, 1])
    assert out["artifact"] == model.accepted.artifact_sha256
    assert out["migrations"] == sorted(p.name for p in
                                       (ROOT / "src/sentinel/db/migrations").glob("*.sql"))
    assert "0004_scoring_profiles.sql" in out["migrations"]
    assert out["results"] == model.threshold
