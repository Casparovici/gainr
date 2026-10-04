from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import asset_repo, position_note_label_repo, position_note_repo
from app.schemas.position_note import (
    JournalNoteCreate,
    JournalNoteUpdate,
    PositionNoteLabelCreate,
    PositionNoteLabelOut,
    PositionNoteLabelReorder,
    PositionNoteLabelUpdate,
    PositionNoteOut,
)

router = APIRouter(prefix="/api/journal", tags=["journal"])


# -- notes (the cross-position view -- see PositionNote's docstring: same rows the per-asset
# Notes tab reads and writes, just a different aggregate query) -------------------------------


@router.get("/notes", response_model=list[PositionNoteOut])
def list_journal_notes(db: Session = Depends(get_db)):
    return position_note_repo.list_all_notes(db)


def _resolve_assets(db: Session, asset_ids: list[int]):
    """The positions a note is linked to, in ticker order -- 400 if any id isn't a real asset,
    rather than silently linking to fewer than were picked."""
    found = asset_repo.get_assets_by_ids(db, list(dict.fromkeys(asset_ids)))
    missing = sorted(set(asset_ids) - set(found))
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown position(s): {missing}")
    return sorted(found.values(), key=lambda a: a.ticker)


@router.post("/notes", response_model=PositionNoteOut)
def create_journal_note(payload: JournalNoteCreate, db: Session = Depends(get_db)):
    """Create a note about one or more positions. A position's own Notes tab keeps using
    POST /assets/{id}/notes, which links just that one."""
    assets = _resolve_assets(db, payload.asset_ids)
    labels = position_note_label_repo.get_by_ids(db, payload.label_ids)
    note = position_note_repo.create_note(db, title=payload.title, body=payload.body, assets=assets, labels=labels)
    db.commit()
    db.refresh(note)
    return note


@router.put("/notes/{note_id}", response_model=PositionNoteOut)
def update_journal_note(note_id: int, payload: JournalNoteUpdate, db: Session = Depends(get_db)):
    note = position_note_repo.get_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    fields = payload.model_dump(exclude_unset=True, exclude={"label_ids", "asset_ids"})
    if payload.label_ids is not None:
        fields["labels"] = position_note_label_repo.get_by_ids(db, payload.label_ids)
    if payload.asset_ids is not None:
        fields["assets"] = _resolve_assets(db, payload.asset_ids)
    position_note_repo.update_note(db, note, **fields)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/notes/{note_id}", status_code=204)
def delete_journal_note(note_id: int, db: Session = Depends(get_db)):
    note = position_note_repo.get_note(db, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    position_note_repo.delete_note(db, note)
    db.commit()


# -- labels ---------------------------------------------------------------------------------


@router.get("/labels", response_model=list[PositionNoteLabelOut])
def list_labels(include_archived: bool = False, db: Session = Depends(get_db)):
    return position_note_label_repo.list_labels(db, include_archived=include_archived)


@router.post("/labels", response_model=PositionNoteLabelOut)
def create_label(payload: PositionNoteLabelCreate, db: Session = Depends(get_db)):
    """Get-or-create by name, matching listr's catalog-item convention -- picking an existing
    label name in the quick-add flow returns that label rather than erroring or duplicating."""
    existing = position_note_label_repo.get_by_name(db, payload.name)
    if existing is not None:
        return existing
    sort_order = position_note_label_repo.next_sort_order(db)
    label = position_note_label_repo.create_label(db, name=payload.name, sort_order=sort_order)
    db.commit()
    db.refresh(label)
    return label


@router.put("/labels/reorder", status_code=204)
def reorder_labels(payload: PositionNoteLabelReorder, db: Session = Depends(get_db)):
    position_note_label_repo.reorder(db, payload.label_ids)
    db.commit()


@router.put("/labels/{label_id}", response_model=PositionNoteLabelOut)
def update_label(label_id: int, payload: PositionNoteLabelUpdate, db: Session = Depends(get_db)):
    label = position_note_label_repo.get_label(db, label_id)
    if label is None:
        raise HTTPException(status_code=404, detail="Label not found")
    fields = payload.model_dump(exclude_unset=True)
    if fields:
        position_note_label_repo.update_label(db, label, **fields)
    db.commit()
    db.refresh(label)
    return label
