# 52. listr: supermarkets, and a list in the order of the aisles

## Status

Accepted

## Context

Every supermarket lays its products out differently, and a shopping list is used walking through
one. listr grouped a list by category, in alphabetical order of the category's name, so the list never
matched the walk (issue #98). Categories already had a `sort_order` and a reorder endpoint, but the
list ignored it and no screen arranged it.

## Decision

**A supermarket is an order of the categories.** `grecipe_stores` holds the shops the user shops at;
`grecipe_store_categories` holds, per store, the position of each category in its walk (first aisle
to last). Order is by category, the aisle, not by product: that is how a shop is laid out, and a store
takes a dozen moves to set up rather than hundreds. A per-product override (milk at the back) can come
later, on top.

**A list follows one store, or none.** `grecipe_lists.store_id` is nullable. Without a store a list
follows the global category order (`ListrCategory.sort_order`, then name); a new category goes last,
so until someone arranges them that is the order the categories were made in. The chosen store is
saved on the list, so it follows the reader from phone to laptop, and a duplicated list keeps it (the
next trip is usually to the same shop).

**The server says which order.** `GET /api/listr/lists/{id}` returns `category_order`, every category
id in the order the list shows its groups: the store's own aisles first, then the rest in the global
order. The whole set, archived categories included, so a line whose category was archived afterwards
still has a place. The frontend only sorts its groups by it; a category it doesn't know comes last.
`GET /api/listr/stores` returns the same full order per store (`category_order`), for the editor.
The rule lives in `listr_store_service.category_order`.

**Arranging.** `POST/PUT/DELETE /api/listr/stores`, and `PUT /stores/{id}/order` with the categories
first to last (a category left out follows the arranged ones; an unknown one is refused). A new store
can start from another store's order (`copy_order_from_id`), for two shops of one chain. Deleting a
store sends its lists back to the global order (explicitly, since the app doesn't enable SQLite's
foreign keys). The standard order is arranged with the existing `PUT /categories/reorder`.

**The screen.** A native "Winkel" select on a list (the standard order, each store, "Winkels
beheren…"). The last option opens a sheet that lists the stores and the standard order; opening one
shows the categories with an up and a down arrow each, saved at once. Arrows rather than dragging,
which is awkward on a phone, and the same arrow buttons the kit already has for reordering.

## Alternatives considered

- **Order by product.** The most exact, and hundreds of moves per store. Aisle order is what a shop
  is; a product override is a later refinement.
- **The chosen store per device (localStorage).** Nothing to store, but the phone in the shop and the
  laptop at home would disagree.
- **A store-less list stays alphabetical.** Then the existing category order would stay unused, and
  nothing would arrange the standard order.
- **Sorting in the frontend.** It would copy the "arranged first, then the rest" rule into the page;
  the server returns the order instead.

## Consequences

- A migration: two tables and a nullable column, nothing to backfill.
- The category order a list without a store shows changes from alphabetical to the global order. With
  the starter catalogue that is a shopping-trip-like order (produce, dairy, meat, bakery, …) rather
  than A to Z.
- A store's order only affects how lines are grouped when shown; no line, quantity or Picnic mapping
  changes.
