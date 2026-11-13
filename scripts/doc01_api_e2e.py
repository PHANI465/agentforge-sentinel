"""DOC01 Part B real-process check: production API + separately locked worker + disposable
Postgres. Separate from the app gate (it needs the worker's own environment); run explicitly:

    (cd tools/document_worker && uv sync --locked)
    uv run --locked python scripts/doc01_api_e2e.py REPORT.json [--worker-python PATH]

It starts a throwaway Postgres cluster and a real `uvicorn sentinel.api:create_app` process
configured with the registered worker interpreter and a fresh marker-owned store. Over plain
HTTP it then uploads, analyses, pages, refuses, restarts the API, deletes and recovers. It
checks the store is empty, no parser process is left and no token or database URL appears in
the API's output or the store. Synthetic fixtures only. Exit 0 only if every check passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
WORKER = ROOT / "tools" / "document_worker"
FIXTURES = WORKER / "fixtures"
EXAMPLES = ROOT / "contracts" / "http" / "examples-v1.3"
ANALYST = {"ingest_transaction", "read_case", "approve_action", "execute_simulated_action"}


def default_worker_python() -> Path:
    venv = WORKER / ".venv"
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


class Api:
    def __init__(self, env: dict, log: Path):
        self.env, self.log, self.proc = env, log, None
        self.port = self._free_port()
        self.base = f"http://127.0.0.1:{self.port}"

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def start(self):
        out = open(self.log, "ab")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "sentinel.api:create_app", "--factory", "--host",
             "127.0.0.1", "--port", str(self.port), "--no-access-log"],
            env=self.env, stdout=out, stderr=out, cwd=str(ROOT))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if self.request("GET", "/healthz")[0] == 200:
                    return
            except OSError:
                pass
            time.sleep(0.2)
        raise RuntimeError("API did not start")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=20)

    def request(self, method, path, token=None, data=None, json_body=None, media=None,
                timeout=180):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        elif media:
            headers["Content-Type"] = media
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read() or b"null")
        except urllib.error.HTTPError as err:
            body = err.read()
            try:
                return err.code, json.loads(body)
            except ValueError:
                return err.code, body.decode("latin-1")[:200]


def declared_oversize(api: "Api", token: str, size: int) -> tuple[int, object]:
    """Send only the request head, declaring `size` bytes, and read the answer: the API must
    refuse a declared oversize body without reading any of it (a client that kept sending
    the body would instead see the connection reset once the server has answered)."""
    with socket.create_connection(("127.0.0.1", api.port), timeout=30) as conn:
        crlf = "\r\n"
        lines = ["POST /v1/documents?format=csv HTTP/1.1", "Host: 127.0.0.1",
                 f"Authorization: Bearer {token}", "Content-Type: text/csv",
                 f"Content-Length: {size}", "Connection: close", "", ""]
        conn.sendall(crlf.join(lines).encode("latin-1"))
        raw = b""
        while chunk := conn.recv(65536):
            raw += chunk
    head, _, body = raw.partition(b"\r\n\r\n")
    status = int(head.split(b" ", 2)[1])
    try:
        return status, json.loads(body)
    except ValueError:
        return status, body[:200].decode("latin-1")


def _diff(a, b, path="") -> list[str]:
    """JSON paths where a and b differ (paths only; no values are reported)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            out += _diff(a.get(key), b.get(key), f"{path}.{key}")
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in _diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [path or "."]


def _normalise(analysis: dict) -> dict:
    """Fields that legitimately differ between runs: the handle, the run's own timing, the
    platform's containment kind and the worker source digest. The digest is provenance that
    changes with any worker source change, so the frozen example keeps the one it was
    recorded with; the containment and the digest are each checked separately."""
    out = json.loads(json.dumps(analysis))
    out.pop("handle_id", None)
    out["worker_run"].pop("elapsed_ms", None)
    out["worker_run"].pop("containment", None)
    out["parser"].pop("worker_source_sha256", None)
    return out


def registered_digest(worker_python: Path, store: Path) -> str | None:
    """The worker's own status answer: the digest the API registers and must enforce."""
    header = json.dumps({"protocol": "sentinel.doc01.bridge/0.1", "op": "status"}) + "\n"
    proc = subprocess.run([str(worker_python), "-I", "-m", "docworker.bridge", "--store",
                           str(store)], input=header.encode(), capture_output=True,
                          timeout=120)
    try:
        return json.loads(proc.stdout)["worker_source_sha256"]
    except (ValueError, KeyError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report")
    parser.add_argument("--worker-python", default=str(default_worker_python()))
    args = parser.parse_args()
    from sentinel import db, devdb
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import Sentinel

    checks: list[dict] = []

    def check(name, ok, **detail):
        checks.append({"check": name, "ok": bool(ok), **detail})
        return ok

    # absolute(), not resolve(): a POSIX venv's bin/python is a symlink to the base
    # interpreter, and resolving it would lose the venv (and docworker) entirely.
    worker_python = Path(args.worker_python).absolute()
    if not worker_python.is_file():
        print(f"worker interpreter not found: {worker_python}", file=sys.stderr)
        return 2
    bin_dir = devdb.find_pg_bin()
    if bin_dir is None:
        print("Postgres initdb not found; set SENTINEL_PG_BIN.", file=sys.stderr)
        return 2
    report = {"kind": "doc01_api_e2e", "started_at": datetime.now(timezone.utc).isoformat(),
              "platform": sys.platform, "python": sys.version.split()[0],
              "worker_python": "registered worker environment (path not recorded)"}
    with tempfile.TemporaryDirectory(prefix="doc01-e2e-") as tmp:
        tmp = Path(tmp)
        cluster = devdb.Cluster(bin_dir, tmp / "pg", devdb.free_port())
        cluster.init()
        cluster.start()
        api = None
        try:
            url = cluster.create_database("doc01_e2e")
            db.migrate(url)
            store = tmp / "doc-store"
            init = subprocess.run([str(worker_python), "-I", "-m", "docworker", "init",
                                   "--store", str(store)], capture_output=True, timeout=120)
            check("store_initialised", init.returncode == 0 and (store / "handles").is_dir(),
                  returncode=init.returncode)
            service = Sentinel(url, DeterministicInvestigator())
            token = service.create_session(frozenset(ANALYST | {"analyze_document"}),
                                           ttl=timedelta(hours=1))[0]
            other = service.create_session(frozenset(ANALYST | {"analyze_document"}))[0]
            plain = service.create_session(frozenset(ANALYST))[0]
            base_env = {k: v for k, v in os.environ.items()
                        if not k.startswith("SENTINEL_DOC")}
            env = dict(base_env, SENTINEL_DATABASE_URL=url, SENTINEL_LOG_LEVEL="INFO",
                       SENTINEL_DOC_WORKER_PYTHON=str(worker_python),
                       SENTINEL_DOC_STORE=str(store))
            api_log = tmp / "api.log"
            api = Api(env, api_log)
            api.start()

            def upload(name, fmt=None, media="application/octet-stream", who=token):
                data = (FIXTURES / name).read_bytes()
                fmt = fmt or name.rsplit(".", 1)[1]
                return api.request("POST", f"/v1/documents?format={fmt}", who, data=data,
                                   media=media), hashlib.sha256(data).hexdigest()

            (status, body), sha = upload("csv_statement_usd.csv", media="text/csv")
            check("upload_csv_201", status == 201 and body.get("sha256") == sha, status=status,
                  body=body if status != 201 else None)
            handle = body.get("handle_id")
            status, analysis = api.request("POST", f"/v1/documents/{handle}/analysis", token,
                                           json_body={"records_limit": 5})
            check("analysis_complete", status == 200 and analysis.get("status") == "complete",
                  status=status)
            frozen = json.loads((EXAMPLES / "document_analysis_complete_paged.json")
                                .read_text(encoding="utf-8"))["response"]
            if status == 200:
                differences = _diff(_normalise(analysis), _normalise(frozen))
            else:
                differences = ["<no analysis>"]
            expected_containment = ("windows_job_object" if os.name == "nt"
                                    else "posix_session_rlimits")
            check("containment_matches_platform",
                  analysis.get("worker_run", {}).get("containment") == expected_containment)
            check("real_worker_matches_frozen_example", not differences, differences=differences)
            digest = analysis.get("parser", {}).get("worker_source_sha256")
            check("analysis_bound_to_registered_worker",
                  digest is not None and digest == registered_digest(worker_python, store),
                  worker_source_sha256=digest)
            recon = (analysis.get("measures") or {}).get("reconciliation", {}).get(
                "currencies", [])
            check("reconciliation_usd_zero", [(c["currency"], c["difference_minor"])
                                              for c in recon] == [("USD", "0")])
            seen, offset = len(analysis.get("records", [])), analysis.get("records_next_offset")
            while offset is not None:
                status, page = api.request(
                    "GET", f"/v1/documents/{handle}/records?offset={offset}&limit=3", token)
                if status != 200:
                    break
                seen += len(page["records"])
                offset = page["next_offset"]
            check("records_paged_to_total", seen == analysis.get("records_total") == 10,
                  seen=seen)

            outcomes = {}
            for name, expected in (("xlsx_statement.xlsx", "complete"),
                                   ("xlsx_hostile.xlsx", "partial"),
                                   ("pdf_scanned_mixed.pdf", "partial"),
                                   ("pdf_encrypted.pdf", "unsupported"),
                                   ("pdf_truncated.pdf", "error"),
                                   ("csv_two_currency.csv", "complete")):
                (status, body), _sha = upload(name)
                h = body.get("handle_id") if status == 201 else None
                status, res = api.request("POST", f"/v1/documents/{h}/analysis", token,
                                          json_body={}) if h else (status, {})
                outcomes[name] = res.get("status") if isinstance(res, dict) else None
                check(f"analysis_{name}", status == 200 and outcomes[name] == expected,
                      status=status, got=outcomes[name])
                api.request("DELETE", f"/v1/documents/{h}", token)
            (status, body), _ = upload("pdf_not_really.pdf")
            check("refused_format_mismatch", (status, body) == (415, {"error": "format_mismatch"}))
            (status, body), _ = upload("xlsx_ole_container.xlsx")
            check("refused_ole", (status, body) == (415, {"error": "unsupported_container"}))
            status, body = declared_oversize(api, token, 10 * 1024 * 1024 + 1)
            check("refused_declared_oversize_unread",
                  (status, body) == (413, {"error": "body_too_large"}), status=status)
            (status, body), _ = upload("csv_statement_usd.csv", who=plain)
            check("default_session_403", status == 403)
            status, body = api.request("POST", f"/v1/documents/{handle}/analysis", other,
                                       json_body={})
            check("foreign_session_404", (status, body) == (404, {"error": "not_found"}))

            api.stop()
            check("api_stopped", api.proc.returncode is not None)
            api = Api(env, api_log)
            api.start()
            status, page = api.request("GET", f"/v1/documents/{handle}/records?offset=0&limit=2",
                                       token)
            check("after_restart_records", status == 200 and len(page.get("records", [])) == 2)
            status, again = api.request("POST", f"/v1/documents/{handle}/analysis", token,
                                        json_body={"records_limit": 5})
            check("after_restart_analysis", status == 200 and again.get("status") == "complete")
            status, body = api.request("DELETE", f"/v1/documents/{handle}", token)
            check("deleted", status == 200 and body.get("deleted") is True)
            status, body = api.request("GET", f"/v1/documents/{handle}/records", token)
            check("deleted_is_404", status == 404)
            api.stop()

            recover = subprocess.run([str(worker_python), "-I", "-m", "docworker", "recover",
                                      "--store", str(store)], capture_output=True, timeout=120)
            check("recover_clean", recover.returncode == 0 and
                  json.loads(recover.stdout or b"{}").get("records") == [])
            leftovers = {sub: sorted(p.name for p in (store / sub).iterdir())
                         if (store / sub).is_dir() else ["<missing directory>"]
                         for sub in ("handles", "runs", "recovery")}
            check("store_empty", leftovers == {"handles": [], "runs": [], "recovery": []},
                  leftovers=leftovers)
            log_text = api_log.read_text(encoding="utf-8", errors="replace")
            stored = "".join(p.read_text(errors="ignore") for p in store.rglob("*")
                             if p.is_file())
            for label, secret in (("token", token), ("other_token", other),
                                  ("database_url", url)):
                check(f"no_{label}_in_api_output_or_store",
                      secret not in log_text and secret not in stored)
            check("no_traceback_in_api_output", "Traceback" not in log_text)
            check("handles_not_logged", handle is not None and handle not in log_text)
            if os.name != "nt":
                left = subprocess.run(["pgrep", "-f", "docworker"], capture_output=True)
                check("no_worker_processes_left", left.returncode == 1)
            else:
                left = subprocess.run(["tasklist", "/V", "/FO", "CSV"], capture_output=True)
                check("no_worker_processes_left",
                      b"docworker" not in left.stdout, note="tasklist window titles")
            report["api_log_lines"] = len(log_text.splitlines())
            # The API's own safe-log events (route templates and codes only), for diagnosis.
            report["api_log_events"] = [line for line in log_text.splitlines()
                                        if line.startswith('{"event"')][-40:]
        except Exception as exc:  # noqa: BLE001 - recorded as a failed check, never hidden
            check("unexpected_exception", False, error_type=type(exc).__name__)
        finally:
            if api is not None:
                api.stop()
            cluster.stop()
    report["checks"] = checks
    report["ok"] = all(c["ok"] for c in checks) and len(checks) > 20
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    failed = [c["check"] for c in checks if not c["ok"]]
    print(json.dumps({"ok": report["ok"], "checks": len(checks), "failed": failed}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
