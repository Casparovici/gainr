"""Errors a service raises when a request can't be carried out, so the service needn't know about
HTTP. Routers turn them into responses with `app.routers.errors.domain_errors`."""


class NotFound(LookupError):
    """Something the request refers to doesn't exist (a 404). The message says what."""


class InvalidRequest(ValueError):
    """The request contradicts itself or the data (a 400). The message says why."""


class Conflict(Exception):
    """The request clashes with what's already there (a 409). The message says how."""
