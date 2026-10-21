"""How-to demos for gym exercises, from free-exercise-db (public domain, ADR 0040).

The catalogue is vendored as `app/data/trainr_exercise_demos.json`, trimmed to what trainr shows
and pinned to one upstream commit; the two photos per exercise (start and end position) are served
by jsDelivr from that same commit, so a URL never changes under a linked exercise. Nothing here
talks to the network -- the browser loads the photos -- so a missing or odd entry just means no
demo, never an error.
"""

import json
import re
from functools import cache
from pathlib import Path
from urllib.parse import quote

from pydantic import BaseModel, Field

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "trainr_exercise_demos.json"
REPO = "yuhonas/free-exercise-db"
# Ids and image paths become URL path segments; anything outside this set is dropped on load.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,120}$")
_SAFE_PATH = re.compile(r"^[A-Za-z0-9_\-]{1,120}/[0-9]{1,2}\.jpg$")


class _Entry(BaseModel):
    id: str
    name: str = Field(min_length=1, max_length=200)
    equipment: str | None = None
    images: list[str]
    instructions: list[str] = []


class _Catalogue(BaseModel):
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    exercises: list[_Entry]


class ExerciseDemo(BaseModel):
    id: str
    name: str
    equipment: str | None
    image_urls: list[str]
    instructions: list[str]


def _normalise(text: str) -> str:
    """Lowercase letters and digits only, so "Push-up", "push up" and "Pushup" meet."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


@cache
def _load() -> dict[str, ExerciseDemo]:
    catalogue = _Catalogue.model_validate(json.loads(DATA_FILE.read_text(encoding="utf-8")))
    base = f"https://cdn.jsdelivr.net/gh/{REPO}@{catalogue.commit}/exercises"
    demos: dict[str, ExerciseDemo] = {}
    for entry in catalogue.exercises:
        images = [p for p in entry.images if _SAFE_PATH.match(p)]
        if not _SAFE_ID.match(entry.id) or not images:
            continue
        demos[entry.id] = ExerciseDemo(
            id=entry.id,
            name=entry.name,
            equipment=entry.equipment,
            image_urls=[f"{base}/{quote(p)}" for p in images],
            instructions=entry.instructions,
        )
    return demos


def get_demo(demo_id: str | None) -> ExerciseDemo | None:
    return _load().get(demo_id) if demo_id else None


def search(query: str, limit: int = 20) -> list[ExerciseDemo]:
    """Names holding the most words of the query (ignoring case, punctuation and a plural "s"), so
    a typo in one word ("Dumbell shoulder press") still finds the rest; among equals the exact
    name first, then names that start with the query, then the shortest -- "curl" should offer
    "Barbell Curl" before "Close-Grip Standing Barbell Curl"."""
    words = [_normalise(w).removesuffix("s") for w in query.split()]
    words = [w for w in words if w]
    if not words:
        return []
    wanted = _normalise(query)
    hits = []
    for demo in _load().values():
        name = _normalise(demo.name)
        matched = sum(w in name for w in words)
        if matched:
            hits.append(((-matched, name != wanted, not name.startswith(wanted), len(name), name), demo))
    hits.sort(key=lambda hit: hit[0])
    return [demo for _, demo in hits[:limit]]
