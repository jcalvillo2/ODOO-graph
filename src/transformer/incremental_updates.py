"""
Incremental Update Tracking for Odoo ETL

This module provides functionality to track file modifications and enable
incremental ETL updates, reprocessing only changed files.

Author: ETL Pipeline Generator
Created: 2025-10-22
"""

import hashlib
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class FileState:
    """Represents the state of a file at a point in time."""

    path: str
    hash: str
    timestamp: float
    size: int


class StateTracker:
    """
    Tracks ETL state for incremental updates.

    Stores file hashes and timestamps to detect changes between ETL runs.
    """

    def __init__(self, state_db_path: str = ".etl_state.db"):
        """
        Initialize StateTracker.

        Args:
            state_db_path: Path to SQLite database for storing state
        """
        self.state_db_path = state_db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database schema."""
        self.conn = sqlite3.connect(self.state_db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS file_state (
                path TEXT PRIMARY KEY,
                hash TEXT NOT NULL,
                timestamp REAL NOT NULL,
                size INTEGER NOT NULL,
                last_processed REAL NOT NULL
            )
            """
        )
        self.conn.commit()
        logger.info(f"Initialized state database: {self.state_db_path}")

    def compute_file_hash(self, file_path: str) -> str:
        """
        Compute SHA-256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex string of file hash
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def get_file_state(self, file_path: str) -> Optional[FileState]:
        """
        Get stored state for a file.

        Args:
            file_path: Path to file

        Returns:
            FileState if found, None otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT path, hash, timestamp, size FROM file_state WHERE path = ?",
            (file_path,),
        )
        row = cursor.fetchone()

        if row:
            return FileState(path=row[0], hash=row[1], timestamp=row[2], size=row[3])

        return None

    def update_file_state(self, file_path: str):
        """
        Update stored state for a file.

        Args:
            file_path: Path to file
        """
        file_hash = self.compute_file_hash(file_path)
        timestamp = os.path.getmtime(file_path)
        size = os.path.getsize(file_path)
        now = datetime.now().timestamp()

        self.conn.execute(
            """
            INSERT OR REPLACE INTO file_state (path, hash, timestamp, size, last_processed)
            VALUES (?, ?, ?, ?, ?)
            """,
            (file_path, file_hash, timestamp, size, now),
        )
        self.conn.commit()

    def detect_changes(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """
        Detect which files have changed, are new, or deleted.

        Args:
            file_paths: List of current file paths to check

        Returns:
            Dictionary with keys: 'modified', 'new', 'deleted'
        """
        changes = {"modified": [], "new": [], "deleted": []}

        # Check each current file
        for file_path in file_paths:
            stored_state = self.get_file_state(file_path)

            if stored_state is None:
                # New file
                changes["new"].append(file_path)
            else:
                # Check if modified
                current_hash = self.compute_file_hash(file_path)
                if current_hash != stored_state.hash:
                    changes["modified"].append(file_path)

        # Find deleted files
        current_paths = set(file_paths)
        cursor = self.conn.cursor()
        cursor.execute("SELECT path FROM file_state")
        stored_paths = {row[0] for row in cursor.fetchall()}

        changes["deleted"] = list(stored_paths - current_paths)

        logger.info(
            f"Detected changes: {len(changes['new'])} new, "
            f"{len(changes['modified'])} modified, "
            f"{len(changes['deleted'])} deleted"
        )

        return changes

    def remove_deleted_files(self, deleted_paths: List[str]):
        """
        Remove deleted files from state database.

        Args:
            deleted_paths: List of deleted file paths
        """
        for path in deleted_paths:
            self.conn.execute("DELETE FROM file_state WHERE path = ?", (path,))
        self.conn.commit()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


class IncrementalUpdater:
    """
    Orchestrates incremental ETL updates.

    Detects changes and triggers selective reprocessing.
    """

    def __init__(self, state_tracker: StateTracker):
        """
        Initialize IncrementalUpdater.

        Args:
            state_tracker: StateTracker instance
        """
        self.state_tracker = state_tracker

    def process_changes(
        self, module_path: str, file_processor_func
    ) -> Dict[str, int]:
        """
        Process only changed files in a module.

        Args:
            module_path: Path to Odoo module
            file_processor_func: Function to process a file (receives file_path)

        Returns:
            Statistics dictionary
        """
        # Find all Python and XML files
        files = []
        for ext in ["*.py", "*.xml"]:
            files.extend(Path(module_path).rglob(ext))

        file_paths = [str(f) for f in files]

        # Detect changes
        changes = self.state_tracker.detect_changes(file_paths)

        # Process new and modified files
        processed = 0
        for file_path in changes["new"] + changes["modified"]:
            try:
                file_processor_func(file_path)
                self.state_tracker.update_file_state(file_path)
                processed += 1
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")

        # Clean up deleted files
        self.state_tracker.remove_deleted_files(changes["deleted"])

        return {
            "processed": processed,
            "new": len(changes["new"]),
            "modified": len(changes["modified"]),
            "deleted": len(changes["deleted"]),
        }


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    print("Incremental Update Tracker")
    print("Usage: Track file changes for incremental ETL")

    # Example
    tracker = StateTracker()
    print(f"State database: {tracker.state_db_path}")
    tracker.close()
