import json
import os

import pytest

from conftest import FIXTURES, OTHER_SESSION, SESSION
from docworker.handles import HandleStore, StoreError
from docworker.limits import Limits


def test_resolve_requires_same_session_and_hides_existence(store, ingest):
    handle = ingest("csv_statement_usd.csv")
    assert store.resolve(handle, SESSION).format == "csv"
    codes = []
    for h, s in [(handle, OTHER_SESSION), ("h_" + "A" * 22, SESSION), ("../../etc", SESSION),
                 (handle + "x", SESSION), (None, SESSION)]:
        with pytest.raises(StoreError) as exc:
            store.resolve(h, s)
        codes.append(exc.value.code)
    assert set(codes) == {"not_found"}  # foreign, missing and malformed are indistinguishable


def test_session_token_is_never_stored(store, ingest):
    handle = ingest("csv_statement_usd.csv")
    meta = (store.root / "handles" / handle / "meta.json").read_text()
    assert SESSION not in meta and json.loads(meta)["session_sha256"]


def test_short_session_refused(store):
    with pytest.raises(StoreError) as exc:
        store.ingest_bytes(b"a,b\n", "csv", "short")
    assert exc.value.code == "invalid_session"


def test_expiry_and_purge(tmp_path):
    now = [1000.0]
    store = HandleStore(tmp_path / "s", Limits(handle_ttl_seconds=10), clock=lambda: now[0])
    store.init()
    handle = store.ingest_bytes(b"Date,Amount\n", "csv", SESSION)["handle_id"]
    store.resolve(handle, SESSION)
    now[0] = 1010.0
    with pytest.raises(StoreError):
        store.resolve(handle, SESSION)
    assert store.purge_expired() == {"removed": 1, "kept": 0}
    assert not (tmp_path / "s" / "handles" / handle).exists()


def test_tampered_bytes_detected(store, ingest):
    handle = ingest("csv_statement_usd.csv")
    (store.root / "handles" / handle / "blob").write_bytes(b"Date,Amount\n2026-01-01,999\n")
    resolved = store.resolve(handle, SESSION)
    with pytest.raises(StoreError) as exc:
        store.read_verified(resolved)
    assert exc.value.code == "integrity_mismatch"


def test_delete_is_verified_and_scoped(store, ingest):
    handle = ingest("csv_statement_usd.csv")
    with pytest.raises(StoreError):
        store.delete(handle, OTHER_SESSION)
    assert store.delete(handle, SESSION) == {"handle_id": handle, "deleted": True}
    with pytest.raises(StoreError):
        store.resolve(handle, SESSION)


@pytest.mark.parametrize("source", ["http://198.51.100.7/a.csv", "file:///etc/passwd",
                                    "https://example.invalid/x.pdf", r"\\server\share\a.csv"])
def test_uris_and_unc_refused(store, source):
    with pytest.raises(StoreError) as exc:
        store.ingest_file(source, "csv", SESSION)
    assert exc.value.code == "not_a_local_file"


def test_directory_and_wrong_extension_refused(store, tmp_path):
    with pytest.raises(StoreError) as exc:
        store.ingest_file(str(tmp_path), "csv", SESSION)
    assert exc.value.code == "not_a_local_file"
    with pytest.raises(StoreError) as exc:
        store.ingest_file(str(FIXTURES / "pdf_text_statement.pdf"), "csv", SESSION)
    assert exc.value.code == "format_mismatch"


def test_symlink_source_refused(store, tmp_path):
    link = tmp_path / "link.csv"
    try:
        os.symlink(FIXTURES / "csv_statement_usd.csv", link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted on this host")
    with pytest.raises(StoreError) as exc:
        store.ingest_file(str(link), "csv", SESSION)
    assert exc.value.code == "not_a_local_file"


def test_oversized_refused_before_copy(store, tmp_path):
    big = tmp_path / "big.csv"
    with open(big, "wb") as fh:
        fh.truncate(Limits().max_input_bytes + 1)
    with pytest.raises(StoreError) as exc:
        store.ingest_file(str(big), "csv", SESSION)
    assert exc.value.code == "too_large"
    assert list((store.root / "handles").iterdir()) == []


def test_unowned_directory_never_adopted(tmp_path):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "someone_else.txt").write_text("keep me")
    with pytest.raises(StoreError) as exc:
        HandleStore(foreign).init()
    assert exc.value.code == "not_owned"
    store = HandleStore(tmp_path / "orig")
    store.init()
    os.rename(tmp_path / "orig", tmp_path / "moved")
    with pytest.raises(StoreError):
        HandleStore(tmp_path / "moved").verify()
    assert (foreign / "someone_else.txt").read_text() == "keep me"
