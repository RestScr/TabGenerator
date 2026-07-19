from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.settings import Settings

CHUNK_SIZE = 1024 * 1024


class UploadValidationError(ValueError):
    pass


class UploadTooLargeError(ValueError):
    pass


@dataclass(frozen=True)
class StoredUpload:
    original_filename: str
    storage_key: str
    path: Path
    content_type: str | None
    size_bytes: int
    sha256: str


def _validate_upload(upload: UploadFile, settings: Settings) -> tuple[str, str]:
    original_filename = Path(upload.filename or "audio").name
    extension = Path(original_filename).suffix.lower()
    if extension not in settings.allowed_audio_extensions:
        allowed = ", ".join(settings.allowed_audio_extensions)
        raise UploadValidationError(f"Unsupported audio format. Allowed formats: {allowed}")

    if upload.content_type and not upload.content_type.startswith("audio/"):
        raise UploadValidationError("Uploaded file must have an audio content type")

    return original_filename, extension


async def store_audio_upload(upload: UploadFile, settings: Settings) -> StoredUpload:
    original_filename, extension = _validate_upload(upload, settings)
    now = datetime.now(timezone.utc)
    relative_dir = Path(now.strftime("%Y")) / now.strftime("%m")
    filename = f"{uuid4()}{extension}"
    destination_dir = settings.uploads_dir / relative_dir
    destination_path = destination_dir / filename
    destination_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    size_bytes = 0

    try:
        with destination_path.open("wb") as output_file:
            while chunk := await upload.read(CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > settings.max_upload_bytes:
                    raise UploadTooLargeError(f"Audio file exceeds the {settings.max_upload_bytes} byte limit")
                digest.update(chunk)
                output_file.write(chunk)
    except Exception:
        destination_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    storage_key = str(relative_dir / filename)
    return StoredUpload(
        original_filename=original_filename,
        storage_key=storage_key,
        path=destination_path,
        content_type=upload.content_type,
        size_bytes=size_bytes,
        sha256=digest.hexdigest(),
    )
