export type Suite = "legacy" | "trace";
export const TRACE_APP: string;
export function resolveSuite(value: string | undefined): Suite;
export function stackStartArgs(suite: Suite, stacksDir: string): string[];
export function testMatchFor(suite: Suite): string;
