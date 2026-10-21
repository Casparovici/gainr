from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import notr_label_repo, notr_note_repo
from app.routers.errors import domain_errors
from app.schemas.notr import (
    NotrImageOut,
    NotrLabelCreate,
    NotrLabelOut,
    NotrLabelReorder,
    NotrLabelUpdate,
    NotrNoteCreate,
    NotrNoteOut,
    NotrNoteUpdate,
)
from app.services import notr_note_service

router = APIRouter(prefix="/api/notr", tags=["notr"])

# Not a user's data, so it may be cached for as long as it's wanted: a picture never changes, a
# replaced one is a new id.
_IMAGE_HEADERS = {"Cache-Control": "private, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"}


# -- notes ----------------------------------------------------------------------------------


@router.get("/notes", response_model=list[NotrNoteOut])
def list_notes(
    q: str | None = None,
    label_id: int | None = None,
    asset_id: int | None = None,
    plant_id: int | None = None,
    recipe_id: int | None = None,
    positions_only: bool = False,
    archived: bool = False,
    db: Session = Depends(get_db),
):
    """Every note, or those matching the filters given. `positions_only` is gainr's Journal: the
    notes linked to at least one position."""
    return notr_note_repo.list_notes(
        db, q=q, label_id=label_id, asset_id=asset_id, plant_id=plant_id, recipe_id=recipe_id,
        positions_only=positions_only, archived=archived,
    )


@router.get("/notes/{note_id}", response_model=NotrNoteOut)
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = notr_note_repo.get_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.post("/notes", response_model=NotrNoteOut)
def create_note(payload: NotrNoteCreate, db: Session = Depends(get_db)):
    with domain_errors():
        note = notr_note_service.create_note(db, **payload.model_dump())
    db.commit()
    db.refresh(note)
    return note


@router.put("/notes/{note_id}", response_model=NotrNoteOut)
def update_note(note_id: int, payload: NotrNoteUpdate, db: Session = Depends(get_db)):
    note = notr_note_repo.get_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    with domain_errors():
        notr_note_service.update_note(db, note, **payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(note)
    return note


class TaskToggle(BaseModel):
    index: int
    checked: bool


@router.put("/notes/{note_id}/tasks", response_model=NotrNoteOut)
def toggle_task(note_id: int, payload: TaskToggle, db: Session = Depends(get_db)):
    """Ticks a checkbox in the rendered note: the `index`-th task-list item of its body."""
    note = notr_note_repo.get_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    with domain_errors():
        notr_note_service.toggle_task(db, note, payload.index, payload.checked)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = notr_note_repo.get_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    notr_note_service.delete_note(db, note)
    db.commit()


# -- pictures -------------------------------------------------------------------------------


@router.post("/images", response_model=NotrImageOut)
def upload_image(image: UploadFile, db: Session = Depends(get_db)):
    """A picture for a note's Markdown. Uploaded on its own, before the note is saved (a new note
    has no id yet); the note claims it when its body shows it. A plain `def` so the Pillow resize
    runs in FastAPI's thread pool, not on the event loop."""
    # One byte past the cap is enough to know it's too big, without holding all of it.
    raw = image.file.read(notr_note_service.MAX_IMAGE_UPLOAD_BYTES + 1)
    with domain_errors():
        stored = notr_note_service.add_image(db, raw)
    db.commit()
    return NotrImageOut(
        id=stored.id, url=notr_note_service.image_url(stored.id), content_type=stored.content_type, size_bytes=stored.size_bytes
    )


@router.get("/images/{image_id}")
def get_image(image_id: int, db: Session = Depends(get_db)):
    image = notr_note_repo.get_image(db, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Picture not found")
    return Response(content=image.content, media_type=image.content_type, headers=_IMAGE_HEADERS)


# -- labels ---------------------------------------------------------------------------------


@router.get("/labels", response_model=list[NotrLabelOut])
def list_labels(include_archived: bool = False, db: Session = Depends(get_db)):
    return notr_label_repo.list_labels(db, include_archived=include_archived)


@router.post("/labels", response_model=NotrLabelOut)
def create_label(payload: NotrLabelCreate, db: Session = Depends(get_db)):
    """Get-or-create by name (see notr_note_service.get_or_create_label)."""
    with domain_errors():
        label = notr_note_service.get_or_create_label(db, payload.name)
    db.commit()
    db.refresh(label)
    return label


@router.put("/labels/reorder", status_code=204)
def reorder_labels(payload: NotrLabelReorder, db: Session = Depends(get_db)):
    notr_label_repo.reorder(db, payload.label_ids)
    db.commit()


@router.put("/labels/{label_id}", response_model=NotrLabelOut)
def update_label(label_id: int, payload: NotrLabelUpdate, db: Session = Depends(get_db)):
    label = notr_label_repo.get_label(db, label_id)
    if label is None:
        raise HTTPException(status_code=404, detail="Label not found")
    fields = payload.model_dump(exclude_unset=True)
    if fields:
        notr_label_repo.update_label(db, label, **fields)
    db.commit()
    db.refresh(label)
    return label
