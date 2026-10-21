from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from app.services.errors import Conflict, InvalidRequest, NotFound


@contextmanager
def domain_errors() -> Iterator[None]:
    """Answers a service's NotFound with a 404, InvalidRequest with a 400 and Conflict with a 409,
    its message as the detail."""
    try:
        yield
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidRequest as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
