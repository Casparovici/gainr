import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ListrListItem } from "../../api/listrTypes";
import ListItemSheet from "./ListItemSheet";

const item: ListrListItem = {
  id: 5, list_id: 1, grocery_item_id: 9, grocery_item_name: "Aardappelen", category_id: 2, category_name: "Groente & Fruit",
  quantity: "1.5", unit: "kg", is_checked: false, sort_order: 0, picnic_product_id: null, picnic_product_name: null,
  picnic_price: null, picnic_unit_quantity: null, picnic_image_url: null,
};

function renderSheet() {
  const h = { onQuantity: vi.fn(), onDelete: vi.fn(), onClose: vi.fn() };
  render(<ListItemSheet item={item} picnicConnected={false} {...h} />);
  return h;
}

describe("ListItemSheet", () => {
  it("saves every +/- step and a typed amount on Enter", async () => {
    const h = renderSheet();
    await userEvent.click(screen.getByRole("button", { name: "Een meer" }));
    expect(h.onQuantity).toHaveBeenLastCalledWith("2.5");
    const field = screen.getByLabelText("Hoeveelheid");
    await userEvent.clear(field);
    await userEvent.type(field, "3,25{Enter}");
    expect(h.onQuantity).toHaveBeenLastCalledWith("3.25");
  });

  it("puts a typed nonsense amount back and doesn't step below one", async () => {
    const h = renderSheet();
    const field = screen.getByLabelText("Hoeveelheid");
    await userEvent.clear(field);
    await userEvent.type(field, "abc{Enter}");
    expect(h.onQuantity).not.toHaveBeenCalled();
    expect(field).toHaveValue("1,5");
    expect(screen.getByRole("button", { name: "Een minder" })).toBeEnabled();
  });

  it("removes the item from the list and closes", async () => {
    const h = renderSheet();
    await userEvent.click(screen.getByRole("button", { name: "Van de lijst halen" }));
    expect(h.onDelete).toHaveBeenCalled();
    expect(h.onClose).toHaveBeenCalled();
  });
});
