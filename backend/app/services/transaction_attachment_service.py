"""Rules for files attached to a transaction (gainr's and gripr's alike): what's allowed in, and what it's called.

The type is decided from the file's own bytes. A browser-supplied Content-Type or extension is
whatever the sender says, and the file is served back from this origin, so only formats that are
inert when displayed are accepted (no HTML, no SVG).
"""

import os
import re
from dataclasses import dataclass
from typing import BinaryIO
from urllib.parse import quote

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENTS_PER_TRANSACTION = 10

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class AttachmentRejected(ValueError):
    """The upload can't be stored; the message says why, for the person who tried to attach it."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class AcceptedFile:
    filename: str
    content_type: str
    size_bytes: int


def sniff_content_type(content: bytes) -> str | None:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def clean_filename(raw: str | None) -> str:
    """The name as shown and offered for download: no path, no control characters, bounded."""
    name = os.path.basename((raw or "").replace("\\", "/"))
    name = _CONTROL_CHARS.sub("", name).strip()
    if len(name) > 255:
        stem, ext = os.path.splitext(name)
        name = stem[: 255 - len(ext)] + ext
    return name or "attachment"


def validate_upload(filename: str | None, content: bytes, existing_count: int) -> AcceptedFile:
    if existing_count >= MAX_ATTACHMENTS_PER_TRANSACTION:
        raise AttachmentRejected(
            f"A transaction can have at most {MAX_ATTACHMENTS_PER_TRANSACTION} attachments.", status_code=409
        )
    if not content:
        raise AttachmentRejected("That file is empty.")
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise AttachmentRejected(f"That file is larger than {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB.", status_code=413)
    content_type = sniff_content_type(content)
    if content_type is None:
        raise AttachmentRejected("Only PDF, PNG, JPEG and WebP files can be attached.", status_code=415)
    return AcceptedFile(filename=clean_filename(filename), content_type=content_type, size_bytes=len(content))


def accept_upload(file: BinaryIO, filename: str | None, existing_count: int) -> tuple[AcceptedFile, bytes]:
    """Reads at most one byte past the cap, so an oversized upload is refused without being held in
    memory, then validates it. Returns what to store alongside the bytes."""
    content = file.read(MAX_ATTACHMENT_BYTES + 1)
    return validate_upload(filename, content, existing_count), content


def content_disposition(filename: str) -> str:
    """Shown in the browser's own viewer (PDF/image); the name is only a hint for saving it."""
    return f"inline; filename*=UTF-8''{quote(filename, safe='')}"
