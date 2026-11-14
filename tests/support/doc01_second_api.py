"""A second, separate API process sharing one document store (DOC01 Part B, R62).

Run as: python doc01_second_api.py SPEC_JSON_PATH
SPEC: {"database_url", "store", "fake_bridge", "token", "handle", "now"}. The token is read from the
spec file written by the test (never argv). The process builds its own Sentinel service,
DocumentService and app, asks for a recovery pass, then requests one analysis over HTTP.
It prints one JSON object: {"pid", "recover", "status", "body"}.
"""
import json
import os
import sys


def main() -> int:
    spec = json.loads(open(sys.argv[1], encoding="utf-8").read())
    from fastapi.testclient import TestClient

    from sentinel.api import create_app
    from sentinel.documents import DocumentService, WorkerConfig
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import ServiceError, Sentinel

    from datetime import datetime
    now = datetime.fromisoformat(spec["now"])  # the test's own clock (sessions use it)
    service = Sentinel(spec["database_url"], DeterministicInvestigator(), lambda: now)
    documents = DocumentService(WorkerConfig(argv=(sys.executable, "-I", spec["fake_bridge"]),
                                             store=spec["store"]))
    try:
        recovered = documents.recover()
    except ServiceError as error:
        recovered = {"error": error.code}
    client = TestClient(create_app(service, documents))
    response = client.post(f"/v1/documents/{spec['handle']}/analysis", json={},
                           headers={"Authorization": f"Bearer {spec['token']}"})
    print(json.dumps({"pid": os.getpid(), "recover": recovered,
                      "status": response.status_code, "body": response.json()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
