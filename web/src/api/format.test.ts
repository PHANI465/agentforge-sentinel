import { describe, expect, it } from "vitest";
import {
  artifactLabel,
  factLabel,
  formatMoney,
  formatScore,
  investigatorLabel,
  messageFor,
  scoreLabel,
  unconfirmedMessage,
} from "./format";
import { moneyFromParts } from "./format";

describe("money and labels", () => {
  it("places the decimal from the exponent without binary division", () => {
    expect(formatMoney(moneyFromParts("USD", 250000))).toBe("2500.00 USD");
    expect(formatMoney(moneyFromParts("USD", 5))).toBe("0.05 USD");
    expect(formatMoney(moneyFromParts("JPY", 1500))).toBe("1500 JPY");
    expect(formatMoney(moneyFromParts("USD", 9_000_000_000_000))).toBe("90000000000.00 USD");
  });

  it("names rule scores and investigators from the server fields", () => {
    expect(scoreLabel("rule", "heuristic")).toBe("Rule score");
    expect(scoreLabel("model", "estimated_probability")).toBe("Estimated probability");
    expect(formatScore(null)).toBe("Unknown");
    expect(investigatorLabel({ name: "deterministic-investigator", version: "i1" })).toBe(
      "Deterministic investigator i1",
    );
    expect(investigatorLabel({ name: "claude-cli-investigator", version: "c1" })).toBe(
      "Local Claude investigator c1",
    );
    expect(investigatorLabel({ name: "custom-investigator", version: "x" })).toBe("custom-investigator x");
    expect(artifactLabel({ name: "velocity-amount-rules", version: "r1" })).toBe("velocity-amount-rules r1");
    expect(factLabel("transaction_count_1h", 3)).toBe("Transactions in the prior hour: 3");
  });

  it("keeps handled error text free of raw bodies", () => {
    expect(messageFor("stale_case_revision", [])).toContain("latest server state");
    expect(messageFor("invalid_request", ["extra_forbidden"])).toContain("extra_forbidden");
    expect(messageFor("<b>nope</b>", [])).toBe(unconfirmedMessage());
  });
});
