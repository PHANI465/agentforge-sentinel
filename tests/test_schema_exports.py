from pathlib import Path
import subprocess
import sys


def test_exported_schemas_match_contract_code():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-B", str(root / "scripts/export_contracts.py"),
                             "--check"], capture_output=True, text=True, cwd=root)
    assert result.returncode == 0, result.stdout + result.stderr
