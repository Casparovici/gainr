"""notr: notes -- a title and a Markdown body, with labels, links to positions, plants and recipes,
and pictures (docs/adr/0050-notr-notes.md)."""

import io
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.notr_note import NotrNote
from app.models.notr_note_image import NotrNoteImage
from app.repositories import (
    asset_repo,
    garden_plant_repo,
    listr_recipe_repo,
    notr_label_repo,
    notr_note_repo,
)
from app.services.errors import InvalidRequest, NotFound
from app.services.transaction_attachment_service import sniff_content_type

IMAGE_URL_PREFIX = "/api/notr/images/"
# What the Markdown holds for a picture; the id is what ties it to its row.
_IMAGE_REF = re.compile(re.escape(IMAGE_URL_PREFIX) + r"(\d+)")

# The upload cap only guards against decoding something absurd; the real size control is the
# resize below, since every byte stored lands in the whole-database backups (docs/adr/0013).
MAX_IMAGE_UPLOAD_BYTES = 25 * 1024 * 1024
IMAGE_MAX_DIMENSION = 1600
# A PNG (a screenshot, a diagram) stays one while it's small or has transparency; a big one is
# a photo saved as PNG and goes to JPEG, where it's a fraction of the size.
PNG_KEEP_BYTES = 600 * 1024
# An upload whose note is never saved is cleaned up the next time anything is uploaded.
UNCLAIMED_IMAGE_MAX_AGE = timedelta(days=1)
PIN_PREVIEW_CHARS = 80


def _utcnow() -> datetime:
    # Naive UTC, like every DateTime column here.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def image_url(image_id: int) -> str:
    return f"{IMAGE_URL_PREFIX}{image_id}"


def referenced_image_ids(body: str) -> list[int]:
    """The pictures a Markdown body shows, in order of appearance."""
    return list(dict.fromkeys(int(m) for m in _IMAGE_REF.findall(body or "")))


# -- notes ----------------------------------------------------------------------------------


def _links(db: Session, *, asset_ids, plant_ids, recipe_ids) -> dict:
    """The things a note is about, for the ids given (None: not given, so not in the result).
    An id that isn't real is a 400 rather than a note quietly linked to fewer than were picked."""
    found: dict = {}
    for key, ids, fetch in (
        ("assets", asset_ids, lambda i: asset_repo.get_asset(db, i)),
        ("plants", plant_ids, lambda i: garden_plant_repo.get_plant(db, i)),
        ("recipes", recipe_ids, lambda i: listr_recipe_repo.get_recipe(db, i)),
    ):
        if ids is None:
            continue
        rows = [(i, fetch(i)) for i in dict.fromkeys(ids)]
        missing = [i for i, row in rows if row is None]
        if missing:
            raise InvalidRequest(f"Unknown {key[:-1]}(s): {missing}")
        found[key] = [row for _, row in rows]
    return found


def create_note(db: Session, *, label_ids, asset_ids, plant_ids, recipe_ids, created_at=None, **fields) -> NotrNote:
    links = _links(db, asset_ids=asset_ids, plant_ids=plant_ids, recipe_ids=recipe_ids)
    if created_at is not None:
        # Stored the way the server's own clock stamps rows: naive UTC. Both dates, so an
        # imported entry doesn't read as edited today.
        if created_at.tzinfo is not None:
            created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
        fields["created_at"] = created_at
        fields["updated_at"] = created_at
    note = notr_note_repo.create_note(db, labels=notr_label_repo.get_by_ids(db, label_ids), **links, **fields)
    sync_images(db, note)
    return note


def update_note(db: Session, note: NotrNote, *, label_ids=None, asset_ids=None, plant_ids=None, recipe_ids=None, **fields) -> NotrNote:
    links = _links(db, asset_ids=asset_ids, plant_ids=plant_ids, recipe_ids=recipe_ids)
    if label_ids is not None:
        links["labels"] = notr_label_repo.get_by_ids(db, label_ids)
    notr_note_repo.update_note(db, note, **links, **fields)
    if "body" in fields:
        sync_images(db, note)
    return note


def delete_note(db: Session, note: NotrNote) -> None:
    for image in notr_note_repo.images_of(db, note.id):
        notr_note_repo.delete_image(db, image)
    notr_note_repo.delete_note(db, note)


def toggle_task(db: Session, note: NotrNote, index: int, checked: bool) -> NotrNote:
    """Ticks (or unticks) the `index`-th task-list item (`- [ ]` / `- [x]`) in the body, counting
    from zero in the order they appear -- what a checkbox in the rendered note asks for."""
    pattern = re.compile(r"^(\s*(?:[-*+]|\d+[.)])\s+\[)([ xX])(\]\s)", re.MULTILINE)
    seen = -1

    def swap(match: re.Match) -> str:
        nonlocal seen
        seen += 1
        if seen != index:
            return match.group(0)
        return f"{match.group(1)}{'x' if checked else ' '}{match.group(3)}"

    body = pattern.sub(swap, note.body)
    if seen < index:
        raise NotFound(f"The note has no task number {index}")
    notr_note_repo.update_note(db, note, body=body)
    return note


def pinned_for_today(db: Session, limit: int = 5) -> list[dict]:
    """The pinned notes Vandaag lists: id, title and, for an untitled one, the start of its body."""
    result = []
    for note in notr_note_repo.pinned_notes(db, limit):
        first_line = next((ln.strip() for ln in note.body.splitlines() if ln.strip()), "")
        first_line = re.sub(r"^[#>\-*+\s]+|!?\[[^\]]*\]\([^)]*\)", "", first_line).strip()
        result.append({"id": note.id, "title": note.title, "preview": first_line[:PIN_PREVIEW_CHARS]})
    return result


# -- labels ---------------------------------------------------------------------------------


def get_or_create_label(db: Session, name: str):
    """The label of that name, made if it doesn't exist -- the quick-add flow's "type a name,
    reuse it if it's there" convention, so picking an existing name never duplicates or errors."""
    name = name.strip()
    if not name:
        raise InvalidRequest("A label needs a name")
    existing = notr_label_repo.get_by_name(db, name)
    if existing is not None:
        return existing
    return notr_label_repo.create_label(db, name=name, sort_order=notr_label_repo.next_sort_order(db))


# -- pictures -------------------------------------------------------------------------------


def _reencode(raw: bytes) -> tuple[bytes, str]:
    """The picture capped at IMAGE_MAX_DIMENSION on its longest side, as a JPEG -- or a PNG for
    a small or transparent one. exif_transpose bakes in a phone photo's rotation, which a
    re-served plain file would otherwise lose."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((IMAGE_MAX_DIMENSION, IMAGE_MAX_DIMENSION))
        has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
        if has_alpha or sniff_content_type(raw) in ("image/png", "image/webp"):
            png = io.BytesIO()
            image.convert("RGBA" if has_alpha else "RGB").save(png, format="PNG", optimize=True)
            if has_alpha or len(png.getvalue()) <= PNG_KEEP_BYTES:
                return png.getvalue(), "image/png"
        rgb = image.convert("RGB")
        jpeg = io.BytesIO()
        rgb.save(jpeg, format="JPEG", quality=85)
        return jpeg.getvalue(), "image/jpeg"


def add_image(db: Session, raw: bytes) -> NotrNoteImage:
    """Stores an uploaded picture, unattached until a note's body references it. Only PNG, JPEG
    and WebP, decided from the bytes themselves: an upload is served back from this origin, so
    HTML and SVG (which would run as part of the app) are never stored."""
    if not raw:
        raise InvalidRequest("That file is empty")
    if len(raw) > MAX_IMAGE_UPLOAD_BYTES:
        raise InvalidRequest("Picture too large")
    if sniff_content_type(raw) not in ("image/png", "image/jpeg", "image/webp"):
        raise InvalidRequest("Only PNG, JPEG and WebP pictures can be added")
    try:
        content, content_type = _reencode(raw)
    except Exception as exc:
        raise InvalidRequest("Could not read that as a picture") from exc
    notr_note_repo.delete_unclaimed_images_before(db, _utcnow() - UNCLAIMED_IMAGE_MAX_AGE)
    return notr_note_repo.add_image(db, content=content, content_type=content_type)


def sync_images(db: Session, note: NotrNote) -> None:
    """Makes the note's pictures what its body shows. A picture the body references and nobody
    has claimed becomes the note's; one the note has but the body no longer shows is deleted.
    The Markdown is the source of truth, so removing the line removes the picture."""
    referenced = set(referenced_image_ids(note.body))
    for image in notr_note_repo.images_of(db, note.id):
        if image.id not in referenced:
            notr_note_repo.delete_image(db, image)
    for image_id in referenced:
        image = notr_note_repo.get_image(db, image_id)
        if image is not None and image.note_id is None:
            image.note_id = note.id
    db.flush()
