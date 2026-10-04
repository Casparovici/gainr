from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ListrItem(Base):
    """The grocery catalog -- a reference product one can add to a list or use as a recipe
    ingredient. Seeded once from backend/scripts/seed_listr.py (~220 common Dutch groceries),
    then extended by hand through the Producten page as needed."""

    __tablename__ = "grecipe_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("grecipe_categories.id"))
    # A plain string ("stuks", "gram", "kg", "liter", "pak", "fles", "zak", "blik", ...), not an
    # enum -- Dutch grocery units don't reduce to a short fixed set, same looseness as
    # Asset.asset_class/native_currency elsewhere in this app. The default a list/recipe line
    # starts from; editable per line.
    default_unit: Mapped[str] = mapped_column(String(32))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    # Set once, the first time this item is pushed to a Picnic cart (see listr_picnic_service)
    # -- a search-and-confirm step the reader does once per item, remembered from then on.
    # picnic_product_name is a display cache of what it was called at mapping time; Picnic's own
    # catalog is never re-queried just to render it.
    picnic_product_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    picnic_product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # The mapped Picnic product's price per selling unit (EUR -- Picnic only sells in euros) and
    # that unit ("1 kilo", "6 stuks"), as of picnic_price_at: saved when the product is picked,
    # refreshed by listr_picnic_service.refresh_prices (daily on the homecloud, or on demand).
    picnic_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    picnic_unit_quantity: Mapped[str | None] = mapped_column(String(60), nullable=True)
    picnic_price_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Picnic's image id for the linked product (public picture, see picnic_image_url).
    picnic_image_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # NULL means "not tracked in the inventory" -- most of the ~220-item catalog isn't something
    # kept at home, so tracking is opt-in per item rather than every item defaulting into it.
    # One of "in_stock" / "low" / "out" when tracked -- a status, not a counted quantity, on
    # purpose -- see docs/adr/0015-listr-inventory.md for why (the same unit-guessing problem the
    # catalog's quantity+unit model already refuses to solve for merging list lines). Originally
    # set by hand; now computed server-side from inventory_count vs inventory_minimum on every
    # write, per the ADR's second addendum -- never written directly by the client.
    inventory_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # A bare tally -- "I have 3 of these" -- adjusted with +/- buttons in the Voorraad UI, not
    # the rejected "quantity + unit" model above: there's no unit attached and nothing ever
    # merges or converts it against a list line or recipe ingredient, so it doesn't reopen the
    # unit-guessing problem inventory_status was chosen to avoid. Manual, same as everything else
    # in Voorraad -- never adjusted by cooking, checking off a list, or a Picnic push -- with one
    # exception: a delivered Picnic order adds what it contained, when that's switched on (see
    # picnic_sync_service and ADR 0027).
    inventory_count: Mapped[int] = mapped_column(Integer, default=0)
    # The reorder point: at or above this, inventory_status computes to in_stock; below it, low;
    # 0 left is always out regardless of this value (there's nothing left to be "low" on).
    # Defaults to 0, which (since count can't be negative) means "always in_stock until count
    # drops to 0" -- a reasonable floor until the reader sets a real minimum for that product.
    inventory_minimum: Mapped[int] = mapped_column(Integer, default=0)

    category = relationship("ListrCategory", back_populates="items")
