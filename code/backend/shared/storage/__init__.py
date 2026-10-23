import hashlib
import mimetypes
import os
import re
from pathlib import Path
from typing import BinaryIO, Tuple, Union

from config.settings import MAX_MEDIA_SIZE_BYTES, STORAGE_DIR

SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

class StorageError(Exception):
    pass

class FileSizeLimitExceededError(StorageError):
    pass

class PathTraversalError(StorageError):
    pass


class ControlledStorage:
    def __init__(self, base_dir: Path = STORAGE_DIR):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _validate_id(self, val: str, field_name: str) -> None:
        if not val or not SAFE_ID_PATTERN.match(val):
            raise PathTraversalError(f"Invalid {field_name}: '{val}' contains unsafe characters or is empty.")

    def _sanitize_filename(self, filename: str) -> str:
        if not filename or "\x00" in filename:
            raise PathTraversalError("Filename contains null byte or is empty.")
        safe_name = Path(filename).name.strip()
        if not safe_name or safe_name in (".", ".."):
            raise PathTraversalError(f"Dangerous or empty filename: '{filename}'")
        stem = Path(safe_name).stem.upper()
        if stem in WINDOWS_RESERVED_NAMES:
            raise PathTraversalError(f"Reserved Windows filename: '{safe_name}'")
        return safe_name

    def _resolve_safe_path(self, project_id: str, asset_id: str, filename: str) -> Path:
        self._validate_id(project_id, "project_id")
        self._validate_id(asset_id, "asset_id")
        safe_name = self._sanitize_filename(filename)

        target_dir = (self.base_dir / project_id / asset_id).resolve()
        # Strict parent-child relationship check
        try:
            target_dir.relative_to(self.base_dir)
        except ValueError:
            raise PathTraversalError(f"Target directory escapes base directory: {target_dir}")

        if target_dir == self.base_dir:
            raise PathTraversalError("Target directory cannot be base directory root.")

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = (target_dir / safe_name).resolve()

        try:
            target_path.relative_to(target_dir)
        except ValueError:
            raise PathTraversalError(f"Target file escapes target directory: {target_path}")

        if target_path.is_symlink():
            raise PathTraversalError("Symlinks are forbidden in controlled storage.")

        return target_path

    def save_stream(
        self,
        stream: BinaryIO,
        filename: str,
        project_id: str,
        asset_id: str,
        max_bytes: int = MAX_MEDIA_SIZE_BYTES,
    ) -> Tuple[str, int, str, str]:
        """
        Saves a binary stream safely, computes SHA256 and size.
        Raises FileSizeLimitExceededError if exceeds max_bytes (default 500MiB).
        Returns: (checksum_sha256, size_bytes, relative_uri, mime_type)
        """
        target_path = self._resolve_safe_path(project_id, asset_id, filename)
        sha256 = hashlib.sha256()
        total_size = 0
        chunk_size = 64 * 1024

        try:
            with open(target_path, "wb") as f:
                while True:
                    chunk = stream.read(chunk_size)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > max_bytes:
                        raise FileSizeLimitExceededError(
                            f"File size exceeds limit of {max_bytes} bytes (500MiB limit)."
                        )
                    sha256.update(chunk)
                    f.write(chunk)
        except Exception:
            if target_path.exists():
                try:
                    target_path.unlink()
                except OSError:
                    pass
            raise

        mime_type, _ = mimetypes.guess_type(target_path.name)
        mime_type = mime_type or "application/octet-stream"
        rel_uri = str(target_path.relative_to(self.base_dir)).replace("\\", "/")
        return sha256.hexdigest(), total_size, rel_uri, mime_type

    def save_bytes(
        self,
        data: bytes,
        filename: str,
        project_id: str,
        asset_id: str,
        max_bytes: int = MAX_MEDIA_SIZE_BYTES,
    ) -> Tuple[str, int, str, str]:
        if len(data) > max_bytes:
            raise FileSizeLimitExceededError(
                f"File size ({len(data)} bytes) exceeds limit of {max_bytes} bytes."
            )
        import io
        return self.save_stream(io.BytesIO(data), filename, project_id, asset_id, max_bytes)

    def get_real_path(self, relative_uri: str) -> Path:
        if not relative_uri or "\x00" in relative_uri:
            raise PathTraversalError("Invalid URI")

        # Normalize slashes
        clean_rel = relative_uri.replace("\\", "/").strip()
        if clean_rel.startswith("/") or ".." in clean_rel.split("/"):
            raise PathTraversalError(f"Path traversal detected in URI: {relative_uri}")

        target = (self.base_dir / clean_rel).resolve()
        try:
            target.relative_to(self.base_dir)
        except ValueError:
            raise PathTraversalError(f"Asset file escapes base storage directory: {relative_uri}")

        if target == self.base_dir:
            raise PathTraversalError("URI cannot resolve to storage root.")

        if target.is_symlink():
            raise PathTraversalError("Symlinks are forbidden.")

        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Asset file not found or inaccessible: {relative_uri}")

        return target


default_storage = ControlledStorage()
