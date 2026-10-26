import { describe, expect, it } from "vitest";
import { beginExecution, finishExecution } from "./idempotency";

describe("execution idempotency", () => {
  it("keeps one key across an ambiguous retry and clears it after a handled result", () => {
    const first = beginExecution(null, "approval-1", () => "key-1");
    const retry = beginExecution(finishExecution(first, "approval-1", true), "approval-1", () => "key-2");
    expect(retry.key).toBe("key-1");
    const next = beginExecution(finishExecution(retry, "approval-1", false), "approval-1", () => "key-3");
    expect(next.key).toBe("key-3");
    const other = beginExecution(first, "approval-2", () => "key-4");
    expect(other.key).toBe("key-4");
  });
});
