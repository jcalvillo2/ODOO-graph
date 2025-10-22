"""
File hashing utilities for change detection.

This module provides functions to compute file hashes and detect
when files have changed, enabling incremental indexing.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: Path) -> str:
    """
    Compute SHA256 hash of a file's contents.

    Uses a streaming approach to handle large files efficiently
    without loading them entirely into memory.

    Args:
        file_path: Path to the file to hash

    Returns:
        Hexadecimal hash string

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file can't be read
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    hash_obj = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            # Read file in chunks to avoid loading entire file into memory
            for chunk in iter(lambda: f.read(8192), b""):
                hash_obj.update(chunk)
    except PermissionError:
        logger.error(f"Permission denied reading file: {file_path}")
        raise

    return hash_obj.hexdigest()


def has_file_changed(file_path: Path, previous_hash: Optional[str]) -> bool:
    """
    Check if a file has changed since the last hash was computed.

    Args:
        file_path: Path to the file to check
        previous_hash: Previously computed hash, or None if first check

    Returns:
        True if file has changed or previous_hash is None, False otherwise
    """
    if previous_hash is None:
        return True

    try:
        current_hash = compute_file_hash(file_path)
        return current_hash != previous_hash
    except (FileNotFoundError, PermissionError) as e:
        logger.warning(f"Could not check file {file_path}: {e}")
        # Assume changed if we can't verify
        return True


def compute_directory_hash(directory: Path, pattern: str = "**/*.py") -> str:
    """
    Compute a combined hash for all files matching a pattern in a directory.

    This is useful for detecting if any file in a module has changed.

    Args:
        directory: Directory to scan
        pattern: Glob pattern for files to include (default: all Python files)

    Returns:
        Combined hash string
    """
    hash_obj = hashlib.sha256()

    # Sort files to ensure consistent ordering
    files = sorted(directory.glob(pattern))

    for file_path in files:
        if file_path.is_file():
            try:
                file_hash = compute_file_hash(file_path)
                # Include both filename and hash for uniqueness
                hash_obj.update(f"{file_path.name}:{file_hash}".encode())
            except (FileNotFoundError, PermissionError) as e:
                logger.warning(f"Skipping file {file_path}: {e}")
                continue

    return hash_obj.hexdigest()
