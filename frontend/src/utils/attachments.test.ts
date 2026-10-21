import { afterEach, describe, expect, it, vi } from "vitest";

import { attachmentErrorMessage, formatFileSize, warnFailedAttachments } from "./attachments";

describe("formatFileSize", () => {
  it("picks the unit by magnitude", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(2048)).toBe("2 KB");
    expect(formatFileSize(1.5 * 1024 * 1024)).toBe("1,5 MB");
  });
});

describe("attachmentErrorMessage", () => {
  it("reads the backend's reason out of the thrown message", () => {
    const error = new Error('413 Request Entity Too Large: {"detail":"That file is larger than 10 MB."}');

    expect(attachmentErrorMessage(error)).toBe("That file is larger than 10 MB.");
  });

  it("falls back to a generic line when there is no reason to show", () => {
    expect(attachmentErrorMessage(new Error("Failed to fetch"))).toBe("The upload failed.");
    expect(attachmentErrorMessage(new Error('422 Unprocessable: {"detail":[{"msg":"x"}]}'))).toBe("The upload failed.");
    expect(attachmentErrorMessage("nope")).toBe("The upload failed.");
  });
});

describe("warnFailedAttachments", () => {
  afterEach(() => vi.restoreAllMocks());

  it("stays silent when every file went through", () => {
    const alert = vi.spyOn(window, "alert").mockImplementation(() => {});

    warnFailedAttachments([]);

    expect(alert).not.toHaveBeenCalled();
  });

  it("names each file that failed", () => {
    const alert = vi.spyOn(window, "alert").mockImplementation(() => {});

    warnFailedAttachments(["a.pdf (too big)", "b.png (empty)"]);

    expect(alert).toHaveBeenCalledOnce();
    expect(alert.mock.calls[0][0]).toContain("a.pdf (too big)");
    expect(alert.mock.calls[0][0]).toContain("b.png (empty)");
  });
});
