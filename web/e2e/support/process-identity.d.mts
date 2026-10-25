export type ObservedProcess = {
  available: boolean;
  found?: boolean;
  creation?: string;
  executable?: string;
  commandLine?: string;
  reason?: string;
};

export type ViteIdentity = {
  pid: number;
  creation: string;
  executable: string;
  script: string;
  commandLine: string;
};

export type ViteDecision = {
  action: "terminate" | "refuse" | "skip_exited";
  reason: string;
  pid?: number;
};

export type CommandRunner = (command: string, args: string[]) => { status: number | null; stdout?: string };

export function commandHasScript(commandLine: string, script: string): boolean;

export function queryProcess(pid: number, run: CommandRunner): ObservedProcess;

export function decideViteAction(expected: Partial<ViteIdentity> | null, observed: ObservedProcess | null): ViteDecision;

export function planChildShutdown(input: {
  childExited: boolean;
  expected: Partial<ViteIdentity> | null;
  observed: ObservedProcess | null;
}): ViteDecision;

export function executeViteAction(decision: ViteDecision, run: CommandRunner): { killed: boolean; reason: string };

export function runAuthority(currentRunId: string, runtimeRunId: string | undefined): { ok: boolean; reason: string };

export function interpretStop(report: { ok?: boolean } | null): { success: boolean; retainRecovery: boolean; reason: string };

export function planOwnedShutdown(input: {
  currentRunId: string;
  runtimeRunId: string | undefined;
  childExited: boolean;
  expected: Partial<ViteIdentity> | null;
  observed: ObservedProcess | null;
  stopReport?: { ok?: boolean } | null;
}): {
  kill: boolean;
  stop: boolean;
  retainRecovery: boolean;
  reason: string;
  vite: ViteDecision;
  stopResult: { success: boolean; retainRecovery: boolean; reason: string } | null;
};

export function recoveryDocument(details: {
  runId: string;
  reasons: string[];
  manifestPath?: string;
  vitePid?: number;
  stackDir?: string;
}): {
  runId: string;
  uncertain: boolean;
  reasons: string[];
  manifestPath?: string;
  vitePid?: number;
  stackDir?: string;
};
