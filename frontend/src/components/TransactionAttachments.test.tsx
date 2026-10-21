import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AttachmentSource, TransactionAttachment } from "../api/types";
import TransactionAttachments from "./TransactionAttachments";

const source = {
  key: "test",
  invalidates: [["transactions"]],
  list: vi.fn(),
  upload: vi.fn(),
  remove: vi.fn(),
  url: (t: number, a: number) => `/api/transactions/${t}/attachments/${a}`,
} satisfies AttachmentSource;

const invoice: TransactionAttachment = {
  id: 7,
  transaction_id: 3,
  filename: "invoice.pdf",
  content_type: "application/pdf",
  size_bytes: 2048,
  created_at: "2026-10-05T10:00:00",
};

function renderField(opts: { variant?: "gainr" | "gripr"; transactionId: number | null; pending?: File[]; onPendingChange?: (f: File[]) => void }) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TransactionAttachments
        source={source}
        variant={opts.variant}
        transactionId={opts.transactionId}
        pending={opts.pending ?? []}
        onPendingChange={opts.onPendingChange ?? vi.fn()}
      />
    </QueryClientProvider>,
  );
}

const pdf = (name = "new.pdf") => new File(["%PDF-1.7"], name, { type: "application/pdf" });

describe("TransactionAttachments on a saved transaction", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows the files with a link that opens each one", async () => {
    vi.mocked(source.list).mockResolvedValue([invoice]);
    renderField({ transactionId: 3 });

    const link = await screen.findByRole("link", { name: /invoice\.pdf/ });

    expect(link).toHaveAttribute("href", "/api/transactions/3/attachments/7");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveTextContent("2 KB");
  });

  it("says so when there are none yet", async () => {
    vi.mocked(source.list).mockResolvedValue([]);
    renderField({ transactionId: 3 });

    expect(await screen.findByText(/No attachments yet/)).toBeInTheDocument();
  });

  it("says so when the list can't be loaded", async () => {
    vi.mocked(source.list).mockRejectedValue(new Error("500"));
    renderField({ transactionId: 3 });

    expect(await screen.findByText(/Couldn't load this transaction's attachments/)).toBeInTheDocument();
  });

  it("uploads a picked file straight away", async () => {
    vi.mocked(source.list).mockResolvedValue([]);
    vi.mocked(source.upload).mockResolvedValue(invoice);
    renderField({ transactionId: 3 });
    const file = pdf();

    await userEvent.upload(screen.getByLabelText("Choose files to attach"), file);

    await waitFor(() => expect(source.upload).toHaveBeenCalledWith(3, file));
  });

  it("shows why a file was refused", async () => {
    vi.mocked(source.list).mockResolvedValue([]);
    vi.mocked(source.upload).mockRejectedValue(
      new Error('413 Request Entity Too Large: {"detail":"That file is larger than 10 MB."}'),
    );
    renderField({ transactionId: 3 });

    await userEvent.upload(screen.getByLabelText("Choose files to attach"), pdf("big.pdf"));

    expect(await screen.findByText(/big\.pdf — That file is larger than 10 MB\./)).toBeInTheDocument();
  });

  it("deletes a file only after confirming", async () => {
    vi.mocked(source.list).mockResolvedValue([invoice]);
    vi.mocked(source.remove).mockResolvedValue(undefined);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    renderField({ transactionId: 3 });
    const button = await screen.findByRole("button", { name: "Delete invoice.pdf" });

    await userEvent.click(button);
    expect(source.remove).not.toHaveBeenCalled();

    await userEvent.click(button);
    await waitFor(() => expect(source.remove).toHaveBeenCalledWith(3, 7));
    confirmSpy.mockRestore();
  });
});

describe("TransactionAttachments on a new transaction", () => {
  afterEach(() => vi.resetAllMocks());

  it("queues picked files for the parent instead of uploading", async () => {
    const onPendingChange = vi.fn();
    renderField({ transactionId: null, onPendingChange });
    const file = pdf();

    await userEvent.upload(screen.getByLabelText("Choose files to attach"), file);

    expect(onPendingChange).toHaveBeenCalledWith([file]);
    expect(source.upload).not.toHaveBeenCalled();
    expect(source.list).not.toHaveBeenCalled();
  });

  it("lists the queued files and lets one be dropped", async () => {
    const onPendingChange = vi.fn();
    const keep = pdf("keep.pdf");
    const drop = pdf("drop.pdf");
    renderField({ transactionId: null, pending: [keep, drop], onPendingChange });

    expect(screen.getByText(/keep\.pdf/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Don't attach drop.pdf" }));

    expect(onPendingChange).toHaveBeenCalledWith([keep]);
  });
});
