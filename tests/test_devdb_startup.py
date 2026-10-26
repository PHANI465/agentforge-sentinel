"""N4: a disposable cluster is TCP-only, so an unusable Unix-socket default cannot stop it.

Ubuntu's PostgreSQL defaults unix_socket_directories to /var/run/postgresql, which the
unprivileged test account cannot write, so startup failed after binding its TCP port. Here
the cluster's own postgresql.conf names a test-owned unusable socket location (on POSIX a
directory without write permission, restored in finally; on Windows a missing directory),
then the real Cluster.start, a loopback connection and Cluster.stop must all succeed."""
import os
import stat
import subprocess

import pytest

from sentinel import devdb

PG_BIN = devdb.find_pg_bin()
pytestmark = pytest.mark.skipif(PG_BIN is None, reason="needs PostgreSQL binaries")


def pg_status(cluster: devdb.Cluster) -> int:
    return subprocess.run([str(cluster.bin_dir / "pg_ctl"), "-D", str(cluster.data_dir),
                           "status"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=60).returncode


def test_cluster_starts_connects_and_stops_with_an_unusable_socket_default(tmp_path):
    import psycopg

    cluster = devdb.Cluster(PG_BIN, tmp_path / "pg" / "data", devdb.free_port())
    cluster.init()
    blocked = tmp_path / "socket-default"
    if os.name != "nt":
        assert os.geteuid() != 0, "run as an unprivileged user: root ignores permissions"
        blocked.mkdir()
    with open(cluster.data_dir / "postgresql.conf", "a", encoding="utf-8") as conf:
        conf.write(f"\nunix_socket_directories = '{blocked.as_posix()}'\n")
    mode = blocked.stat().st_mode if blocked.exists() else None
    try:
        if mode is not None:
            blocked.chmod(stat.S_IRUSR | stat.S_IXUSR)  # owned, but no socket can be made
            assert not os.access(blocked, os.W_OK)
        cluster.start()
        with psycopg.connect(cluster.url(), connect_timeout=10) as conn:
            row = conn.execute("SELECT current_user, host(inet_server_addr()), "
                               "current_setting('unix_socket_directories')").fetchone()
        assert row == (devdb.USER, "127.0.0.1", "")
        if blocked.exists():
            assert list(blocked.iterdir()) == []
        cluster.stop()
        assert pg_status(cluster) == 3  # pg_ctl: no server running
    finally:
        if mode is not None:
            blocked.chmod(mode)
        if (cluster.data_dir / "postmaster.pid").exists():
            try:  # our own cluster, by its data directory
                cluster.stop()
            except (subprocess.SubprocessError, OSError):
                pass
