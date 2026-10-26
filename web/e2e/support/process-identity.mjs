function norm(value) {
  return String(value ?? "").replaceAll("/", "\\").toLowerCase();
}

export function commandHasScript(commandLine, script) {
  if (!commandLine || !script) return false;
  return norm(commandLine).includes(norm(script));
}

function integerPid(pid) {
  return Number.isInteger(pid) && pid > 0 ? pid : 0;
}

export function queryProcess(pid, run) {
  const checked = integerPid(pid);
  if (!checked) return { available: false, reason: "pid_invalid" };
  const script = [
    `$p = Get-CimInstance Win32_Process -Filter "ProcessId=${checked}"`,
    "if (-not $p) { Write-Output '{\"found\":false}'; exit 0 }",
    "$created = $p.CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')",
    "$payload = @{ found = $true; creation = $created; executable = [string]$p.ExecutablePath; commandLine = [string]$p.CommandLine }",
    "[Console]::Out.Write(($payload | ConvertTo-Json -Compress))",
  ].join("; ");
  let result;
  try {
    result = run("powershell", ["-NoProfile", "-Command", script]);
  } catch {
    return { available: false, reason: "query_failed" };
  }
  if (!result || result.status !== 0 || !result.stdout) return { available: false, reason: "query_failed" };
  try {
    const parsed = JSON.parse(String(result.stdout).trim());
    if (!parsed.found) return { available: true, found: false };
    if (!parsed.creation || !parsed.executable || !parsed.commandLine) {
      return { available: false, reason: "query_incomplete" };
    }
    return {
      available: true,
      found: true,
      creation: String(parsed.creation),
      executable: String(parsed.executable),
      commandLine: String(parsed.commandLine),
    };
  } catch {
    return { available: false, reason: "query_unreadable" };
  }
}

export function decideViteAction(expected, observed) {
  if (!expected?.pid || !expected.creation || !expected.executable || !expected.script || !expected.commandLine) {
    return { action: "refuse", reason: "identity_missing" };
  }
  if (!observed || observed.available === false) return { action: "refuse", reason: "identity_unavailable" };
  if (!observed.found) return { action: "skip_exited", reason: "already_exited" };
  if (observed.creation !== expected.creation) return { action: "refuse", reason: "creation_mismatch" };
  if (norm(observed.executable) !== norm(expected.executable)) return { action: "refuse", reason: "executable_mismatch" };
  if (norm(observed.commandLine) !== norm(expected.commandLine)) return { action: "refuse", reason: "command_mismatch" };
  if (!commandHasScript(observed.commandLine, expected.script)) return { action: "refuse", reason: "script_mismatch" };
  return { action: "terminate", pid: expected.pid, reason: "identity_matched" };
}

export function planChildShutdown({ childExited, expected, observed }) {
  if (childExited) return { action: "skip_exited", reason: "child_exited" };
  return decideViteAction(expected, observed);
}

export function executeViteAction(decision, run) {
  if (!decision || decision.action !== "terminate") {
    return { killed: false, reason: decision?.reason ?? "not_terminated" };
  }
  let result;
  try {
    result = run("taskkill", ["/PID", String(decision.pid), "/T", "/F"]);
  } catch {
    return { killed: false, reason: "taskkill_failed" };
  }
  if (!result || result.status !== 0) return { killed: false, reason: "taskkill_failed" };
  return { killed: true, reason: "terminated" };
}

export function runAuthority(currentRunId, runtimeRunId) {
  if (typeof currentRunId !== "string" || !/^[0-9a-f]{32}$/.test(currentRunId)) {
    return { ok: false, reason: "current_run_missing" };
  }
  if (runtimeRunId !== currentRunId) return { ok: false, reason: "stale_runtime" };
  return { ok: true, reason: "current_run" };
}

export function interpretStop(report) {
  if (!report || report.ok !== true) return { success: false, retainRecovery: true, reason: "stop_incomplete" };
  return { success: true, retainRecovery: false, reason: "stopped" };
}

export function planOwnedShutdown({ currentRunId, runtimeRunId, childExited, expected, observed, stopReport }) {
  const auth = runAuthority(currentRunId, runtimeRunId);
  if (!auth.ok) {
    return { kill: false, stop: false, retainRecovery: true, reason: auth.reason, vite: { action: "refuse", reason: auth.reason } };
  }
  const vite = planChildShutdown({ childExited, expected, observed });
  const stop = stopReport === undefined ? null : interpretStop(stopReport);
  const retainRecovery = vite.action === "refuse" || stop?.success === false;
  return {
    kill: vite.action === "terminate",
    stop: true,
    retainRecovery,
    reason: vite.reason,
    vite,
    stopResult: stop,
  };
}

export function recoveryDocument({ runId, reasons, manifestPath, vitePid, stackDir }) {
  return {
    runId,
    uncertain: true,
    reasons: Array.isArray(reasons) ? reasons.map((item) => String(item)) : [],
    manifestPath: manifestPath ? String(manifestPath) : undefined,
    vitePid: integerPid(vitePid) || undefined,
    stackDir: stackDir ? String(stackDir) : undefined,
  };
}
