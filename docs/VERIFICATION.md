# Initial domain contract verification

Verified October 23, 2026 directly in E:\PHANI\agentforge-sentinel, using its isolated .venv and uv.lock. Python 3.11.3, Pydantic 2.14.1, pytest 8.4.2, Ruff 0.17.2, Node 22.13.1.

## Results

| Command | Actual result | Exit |
| --- | --- | --- |
| .venv\Scripts\python.exe -B -m ruff check . | All checks passed | 0 |
| .venv\Scripts\python.exe -B -m pytest -q | 51 passed in 0.97 seconds | 0 |
| .venv\Scripts\python.exe -B -m unittest discover -s tests_handoff -v | 21 passed in 41.120 seconds | 0 |
| .venv\Scripts\python.exe -B scripts/export_contracts.py --check | 11 draft v1 schemas verified | 0 |
| node scripts/check_contract_examples.mjs | Synthetic transaction/money transport checks passed | 0 |

The 72 tests cover different scopes: 51 contract/schema tests and 21 coordination-helper regressions. Additional static checking and Node transport checks also passed. Temporary Git fixtures isolated external configuration/hooks/signing. No Git repository or commit was created in the Sentinel project.

## Scope and limits

This is working-tree evidence, not the strict helper's clean-commit PASS. Application checks are now configured; that helper still requires an actual clean committed repository. No application API, database/migration, live model call, trained fraud model, UI or hosted execution is verified by this increment. Authentication, durable state transitions, atomic approval consumption, idempotency and recovery still require implementation and integration tests.

The Node check verifies basic JSON transport and money bounds, not generated frontend types or full schema validation. Pure hash/precondition checks do not establish data authenticity, HTTP authorization, storage concurrency or tamper-proof audit.

Historical handoff-kit verification is preserved separately in HANDOFF_VERIFICATION_HISTORY.md; its earlier paths and hashes describe that historical artifact, not the updated project helpers.

## Source SHA256 values

- `pyproject.toml`: `4a4f179b6833acba2dab35bec7e7517917257a5cb25201deda360e38c3d4b366`
- `uv.lock`: `7c1835a27675ba2b9d501b030c02697d39bc1af517136164dced422377bf11ee`
- `src/sentinel/contracts/v1.py`: `8ddc9e1f5b7e5ec3787ead6bfa82bffcf150f87c2b7fa053491b05420857fe3d`
- `src/sentinel/contracts/guards.py`: `880379270667231e8a17e74b65a3b15654c83aef5b7391806f931a2386a2cef5`
- `tests/test_contracts.py`: `4c56206e8f970660c094f43f41f38156e9393fa568376ad334f2d6715085fee9`
- `tests/test_schema_exports.py`: `94ece3e166ff11af7b6abf6315951540a6b8525172ceb9da1fd7aa60a7922839`
- `scripts/agent_check.py`: `da3d10c9221dd731a9c888477224a72afe913deb2bf6dec7f5ef765c548d147c`
- `tests_handoff/test_handoff.py`: `a0319e363b5c344e640000a00a799de869aefb4a13180271936fd3e22758a2b0`
- `scripts/export_contracts.py`: `f8bb4574657581fa4c695ed55ea070b917550c680fddf5836cdebb199a9863d3`
- `scripts/check_contract_examples.mjs`: `6e9926b253b92a894135c5bc1f13c85c9904d2017a82846a08d50c37cd3dd2ba`
