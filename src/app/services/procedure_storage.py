"""Uploaded procedure files on disk.

The directory is resolved by Settings.procedure_dir(): PROCEDURE_STORAGE_PATH, then the App
Store FILE_STORAGE add-on's STORAGE_MOUNT_PATH plus /procedures, then /data/procedures. Boot
proves it accepts a real write (appstore-gate-compliance), so a read-only or root-owned mount
stops the container with the errno in the log instead of failing at the first upload.

Each file is stored as <procedure id><extension>; the uploaded filename never reaches the
filesystem beyond a short, plain extension.
"""

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings, get_settings

_PREVIEW_MAX_BYTES = 64 * 1024
_PREVIEWABLE_TYPES = frozenset({"text/plain", "text/markdown", "application/json", "text/csv"})
_PLAIN_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,16}")


@dataclass(frozen=True)
class StoredFile:
    path: Path
    size_bytes: int
    file_hash: str


def prepare_storage(settings: Settings) -> Path:
    """Create the procedure directory and prove it accepts a write. Raises OSError if not."""
    root = Path(settings.procedure_dir())
    root.mkdir(parents=True, exist_ok=True)
    probe = root / f".write-check-{uuid.uuid4().hex}"
    probe.write_bytes(b"ok")
    probe.unlink()
    return root


def _root() -> Path:
    return Path(get_settings().procedure_dir())


def _path_for(procedure_id: uuid.UUID, filename: str) -> Path:
    suffix = Path(filename).suffix
    if not _PLAIN_EXTENSION.fullmatch(suffix):
        suffix = ""
    return _root() / f"{procedure_id}{suffix}"


def write_file(procedure_id: uuid.UUID, filename: str, data: bytes) -> StoredFile:
    root = _root()
    root.mkdir(parents=True, exist_ok=True)
    path = _path_for(procedure_id, filename)
    path.write_bytes(data)
    return StoredFile(
        path=path,
        size_bytes=len(data),
        file_hash=hashlib.sha256(data).hexdigest(),
    )


def delete_file(procedure_id: uuid.UUID, filename: str) -> None:
    _path_for(procedure_id, filename).unlink(missing_ok=True)


def read_file_bytes(procedure_id: uuid.UUID, filename: str) -> bytes:
    return _path_for(procedure_id, filename).read_bytes()


def read_preview(
    procedure_id: uuid.UUID,
    filename: str,
    content_type: str,
) -> tuple[str | None, bool]:
    """Return (text content, truncated flag) for previewable types, else (None, False)."""
    if content_type not in _PREVIEWABLE_TYPES:
        return None, False
    path = _path_for(procedure_id, filename)
    if not path.exists():
        return None, False
    raw = path.read_bytes()
    truncated = len(raw) > _PREVIEW_MAX_BYTES
    return raw[:_PREVIEW_MAX_BYTES].decode("utf-8", errors="replace"), truncated
