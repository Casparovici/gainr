import { describe, expect, it } from "vitest";

import { griprCategoryKindFor, griprSignedAmount } from "./griprTransactionType";

describe("griprCategoryKindFor", () => {
  it("files a refund under an expense category, since it nets against spend", () => {
    expect(griprCategoryKindFor("refund")).toBe("expense");
  });

  it("maps expense and income to their own kind and a transfer to none", () => {
    expect(griprCategoryKindFor("expense")).toBe("expense");
    expect(griprCategoryKindFor("income")).toBe("income");
    expect(griprCategoryKindFor("transfer")).toBeNull();
  });
});

describe("griprSignedAmount", () => {
  it("counts a refund as money coming in", () => {
    expect(griprSignedAmount({ type: "refund", amount: "30.00" })).toBe(30);
  });

  it("counts an expense as money going out", () => {
    expect(griprSignedAmount({ type: "expense", amount: "60.00" })).toBe(-60);
  });
});
