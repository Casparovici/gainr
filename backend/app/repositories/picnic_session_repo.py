from sqlalchemy.orm import Session

from app.models.picnic_session import PicnicSession

SESSION_ID = 1  # single row -- one Picnic account for this single-user app


def get(db: Session) -> PicnicSession | None:
    return db.get(PicnicSession, SESSION_ID)


def set_auth_key(db: Session, auth_key: str) -> PicnicSession:
    session = db.get(PicnicSession, SESSION_ID)
    if session is None:
        session = PicnicSession(id=SESSION_ID, auth_key=auth_key)
        db.add(session)
    else:
        session.auth_key = auth_key
    db.flush()
    return session


def clear(db: Session) -> None:
    session = db.get(PicnicSession, SESSION_ID)
    if session is not None:
        db.delete(session)
        db.flush()
