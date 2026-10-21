import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { notrApi } from "../api/notrClient";
import MarkdownEditor from "./MarkdownEditor";

vi.mock("../api/notrClient", () => ({ notrApi: { uploadImage: vi.fn() } }));

function Harness({ initial = "" }: { initial?: string }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <MarkdownEditor value={value} onChange={setValue} />
      <output data-testid="value">{value}</output>
    </>
  );
}

const text = () => screen.getByRole("textbox", { name: "Note text" }) as HTMLTextAreaElement;
const value = () => screen.getByTestId("value").textContent;
const picture = (name = "chart.png", type = "image/png") => new File(["x"], name, { type });

beforeEach(() => {
  vi.mocked(notrApi.uploadImage).mockResolvedValue({ id: 9, url: "/api/notr/images/9", content_type: "image/png", size_bytes: 1 });
});
afterEach(() => vi.clearAllMocks());

describe("MarkdownEditor", () => {
  it("formats the selection from the toolbar", async () => {
    render(<Harness initial="a big deal" />);
    text().focus();
    text().setSelectionRange(2, 5);

    await userEvent.click(screen.getByRole("button", { name: "Bold" }));

    expect(value()).toBe("a **big** deal");
  });

  it("starts a checklist on the line the caret is on", async () => {
    render(<Harness initial="one" />);
    text().focus();
    text().setSelectionRange(0, 0);

    await userEvent.click(screen.getByRole("button", { name: "Checklist" }));

    expect(value()).toBe("- [ ] one");
  });

  it("continues a list on Enter and ends it on an empty item", async () => {
    render(<Harness />);

    await userEvent.type(text(), "- one{Enter}two{Enter}{Enter}after");

    expect(value()).toBe("- one\n- two\nafter");
  });

  it("previews the Markdown, and says so when there is nothing yet", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));
    expect(screen.getByText("Nothing to preview yet.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: "Write" }));
    await userEvent.type(text(), "Hello **world**");
    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));

    expect(screen.getByText("world").tagName).toBe("STRONG");
  });

  it("puts a picked picture into the text as Markdown", async () => {
    render(<Harness initial="Before" />);

    await userEvent.upload(screen.getByLabelText("Add picture", { selector: "input" }), picture());

    await waitFor(() => expect(value()).toBe("Before\n\n![chart](/api/notr/images/9)\n"));
    expect(notrApi.uploadImage).toHaveBeenCalledTimes(1);
  });

  it("uploads a picture pasted from the clipboard", async () => {
    render(<Harness />);

    fireEvent.paste(text(), { clipboardData: { files: [picture("image.png")] } });

    await waitFor(() => expect(value()).toBe("![](/api/notr/images/9)\n"));
  });

  it("uploads a picture dropped on the text", async () => {
    render(<Harness />);

    fireEvent.drop(text(), { dataTransfer: { files: [picture("holiday.jpg", "image/jpeg")], types: ["Files"] } });

    await waitFor(() => expect(value()).toBe("![holiday](/api/notr/images/9)\n"));
  });

  it("pastes text as usual", () => {
    render(<Harness />);

    fireEvent.paste(text(), { clipboardData: { files: [] } });

    expect(notrApi.uploadImage).not.toHaveBeenCalled();
  });

  it("ignores a file that is not a picture", async () => {
    render(<Harness />);

    fireEvent.drop(text(), { dataTransfer: { files: [new File(["x"], "a.pdf", { type: "application/pdf" })], types: ["Files"] } });

    expect(notrApi.uploadImage).not.toHaveBeenCalled();
  });

  it("says why a picture was refused and keeps the text", async () => {
    vi.mocked(notrApi.uploadImage).mockRejectedValue(new Error("Only PNG, JPEG and WebP pictures can be added"));
    render(<Harness initial="Keep me" />);

    await userEvent.upload(screen.getByLabelText("Add picture", { selector: "input" }), picture());

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't add that picture: Only PNG, JPEG and WebP pictures can be added");
    expect(value()).toBe("Keep me");
  });

  it("adds several pictures one after the other without losing any", async () => {
    vi.mocked(notrApi.uploadImage)
      .mockResolvedValueOnce({ id: 1, url: "/api/notr/images/1", content_type: "image/png", size_bytes: 1 })
      .mockResolvedValueOnce({ id: 2, url: "/api/notr/images/2", content_type: "image/png", size_bytes: 1 });
    render(<Harness />);

    await userEvent.upload(screen.getByLabelText("Add picture", { selector: "input" }), [picture("a.png"), picture("b.png")]);

    await waitFor(() => expect(value()).toContain("/api/notr/images/2"));
    expect(value()).toContain("![a](/api/notr/images/1)");
    expect(value()).toContain("![b](/api/notr/images/2)");
  });
});
