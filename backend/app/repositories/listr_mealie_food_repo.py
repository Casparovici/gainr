from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.listr_mealie_food import ListrMealieFood


def list_mappings(db: Session) -> dict[str, ListrMealieFood]:
    rows = db.execute(select(ListrMealieFood).options(joinedload(ListrMealieFood.grocery_item))).scalars().all()
    return {row.mealie_food_id: row for row in rows}


def set_mapping(db: Session, mealie_food_id: str, mealie_food_name: str, grocery_item_id: int) -> ListrMealieFood:
    """Creates or repoints the mapping for one Mealie food -- picking again replaces the old choice."""
    row = db.get(ListrMealieFood, mealie_food_id)
    if row is None:
        row = ListrMealieFood(mealie_food_id=mealie_food_id)
        db.add(row)
    row.mealie_food_name = mealie_food_name
    row.grocery_item_id = grocery_item_id
    db.flush()
    return row
