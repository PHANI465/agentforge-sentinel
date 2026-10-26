# N4: actual Linux PostgreSQL startup defect

Found during the first approved native Linux verification on October 26, 2026. Tested source: clean N2 3c860d4, Ubuntu 24.04.3 / PostgreSQL 16.15, unprivileged sentinel UID 1000. **Blocking for the native Linux database-dependent suite; does not invalidate verified Windows main a456f51.**

## Failure and cause

src/sentinel/devdb.py, Cluster.start, passes a port and listen_addresses=127.0.0.1 but inherits the server package's Unix-socket default. This Ubuntu build attempts /var/run/postgresql, which is not writable by the project test account. PostgreSQL binds the test TCP port, then exits with a permission-denied socket-lock error. initdb as the correct non-root account already succeeds; this is not fixed by running the server as root.

The unmodified focused Linux run gave 13 pass/one failure. All six N2 startup variants passed; the failing lifecycle case stops at pg_ctl start before its intended missing API factory can be exercised.

## Independent controlled diagnosis

Created a fresh owned cluster under /home/sentinel/.local/share/sentinel-bootstrap/probes/. Default Cluster.start failed with the same /var/run/postgresql socket-lock permission error. A direct start of the same cluster with unix_socket_directories empty passed over loopback TCP. The query confirmed current_user=sentinel and empty Unix-socket configuration. pg_ctl status confirmed the owned cluster stopped afterwards. No project source, shared socket permissions, group membership or Windows database service was changed.

Evidence: canonical .agent/wsl-setup/pg-startup-diagnostic.json and native-focused.xml/log. Diagnostic script: E:/PHANI/Interview/tmp/sentinel-wsl-pg-diagnostic-20261026.py. The manual TCP-only launch is diagnostic evidence, not a passing unmodified project test or CI result.

## Required narrow correction

Make disposable-cluster startup select an owned socket location or explicitly disable Unix sockets when using the existing TCP-only URL profile. Preserve loopback binding, random/test-selected ports, timeout/cleanup behavior and Windows compatibility. Do not grant access to a system socket directory, run tests as root, alter the gate, skip database tests or regenerate frozen model artifacts.

Add meaningful real startup/connect/stop regression coverage with a controlled unwritable default on POSIX, restoring test-owned permissions in finally. Keep useful Windows coverage without a new platform skip. Reproduce baseline failure for the actual startup reason, then run the changed lifecycle/startup and full platform checks on the corrected commit.

Ownership is explicitly added to Claude's N3/N4 task for src/sentinel/devdb.py and focused tests only. Preserve the accepted N2 branch and main; Codex reviews the combined candidate. PostgreSQL documents that an empty unix_socket_directories disables Unix sockets while TCP can remain configured: [version 16 connection settings](https://www.postgresql.org/docs/16/runtime-config-connection.html).
