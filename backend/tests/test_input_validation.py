"""Inputs that would otherwise be stored as nonsense: a care schedule every 0 days (whose next due
date never moves), a list or recipe quantity of zero or less, a recipe for zero people."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.gardnr import GardenCareScheduleCreate, GardenCareScheduleUpdate
from app.schemas.listr import ListrListItemCreate, ListrListItemUpdate, ListrRecipeCreate, ListrRecipeIngredientCreate, ListrRecipeUpdate


@pytest.mark.parametrize("value", [0, -2])
def test_a_care_schedule_repeats_at_least_every_one_unit(value):
    with pytest.raises(ValidationError):
        GardenCareScheduleCreate(action_type="water", interval_value=value, frequency="daily")
    with pytest.raises(ValidationError):
        GardenCareScheduleUpdate(interval_value=value)
    assert GardenCareScheduleUpdate(interval_value=3).interval_value == 3
    assert GardenCareScheduleCreate(action_type="water", interval_value=1, frequency="daily").interval_value == 1


@pytest.mark.parametrize("value", ["0", "-1"])
def test_quantities_are_positive(value):
    for build in (
        lambda: ListrListItemCreate(grocery_item_id=1, quantity=Decimal(value)),
        lambda: ListrListItemUpdate(quantity=Decimal(value)),
        lambda: ListrRecipeIngredientCreate(grocery_item_id=1, quantity=Decimal(value)),
    ):
        with pytest.raises(ValidationError):
            build()
    assert ListrListItemCreate(grocery_item_id=1, quantity=Decimal("0.5")).quantity == Decimal("0.5")


def test_a_recipe_serves_at_least_one():
    with pytest.raises(ValidationError):
        ListrRecipeCreate(title="Soep", servings=0)
    with pytest.raises(ValidationError):
        ListrRecipeUpdate(servings=0)
    assert ListrRecipeCreate(title="Soep").servings is None
