"""
Settings management for Odoo Tracker.

This module loads configuration from environment variables and provides
a centralized settings object with validation and defaults.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


@dataclass
class Settings:
    """
    Application settings loaded from environment variables.

    All settings have sensible defaults for development and can be
    overridden via environment variables or .env file.
    """

    # Neo4j Configuration
    neo4j_uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"))

    # Odoo Addons Paths
    addons_paths: List[str] = field(default_factory=lambda: _parse_paths(
        os.getenv("ADDONS_PATHS", "")
    ))

    # Performance Settings
    batch_size: int = field(default_factory=lambda: int(os.getenv("BATCH_SIZE", "50")))
    max_memory_percent: float = field(default_factory=lambda: float(os.getenv("MAX_MEMORY_PERCENT", "70.0")))
    enable_cache: bool = field(default_factory=lambda: os.getenv("ENABLE_CACHE", "true").lower() == "true")
    cache_dir: Path = field(default_factory=lambda: Path(os.getenv("CACHE_DIR", ".cache")))
    enable_parallel: bool = field(default_factory=lambda: os.getenv("ENABLE_PARALLEL", "false").lower() == "true")
    max_workers: int = field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "4")))
    enable_incremental: bool = field(default_factory=lambda: os.getenv("ENABLE_INCREMENTAL", "true").lower() == "true")

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_file: Optional[str] = field(default_factory=lambda: os.getenv("LOG_FILE", "odoo_tracker.log"))

    def __post_init__(self):
        """Validate settings after initialization."""
        self._validate()

    def _validate(self):
        """Validate critical settings."""
        if self.batch_size <= 0:
            raise ValueError("BATCH_SIZE must be greater than 0")

        if not (0 < self.max_memory_percent <= 100):
            raise ValueError("MAX_MEMORY_PERCENT must be between 0 and 100")

        if self.max_workers <= 0:
            raise ValueError("MAX_WORKERS must be greater than 0")

        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Invalid LOG_LEVEL: {self.log_level}")

        # Create cache directory if it doesn't exist
        if self.enable_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict:
        """Convert settings to dictionary for display."""
        return {
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "addons_paths": self.addons_paths,
            "batch_size": self.batch_size,
            "max_memory_percent": self.max_memory_percent,
            "enable_cache": self.enable_cache,
            "cache_dir": str(self.cache_dir),
            "enable_parallel": self.enable_parallel,
            "max_workers": self.max_workers,
            "enable_incremental": self.enable_incremental,
            "log_level": self.log_level,
            "log_file": self.log_file,
        }


def _parse_paths(paths_str: str) -> List[str]:
    """
    Parse comma-separated paths from environment variable.

    Args:
        paths_str: Comma-separated string of paths

    Returns:
        List of path strings, empty list if input is empty
    """
    if not paths_str:
        return []
    return [p.strip() for p in paths_str.split(",") if p.strip()]


# Global settings instance
_settings: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    """
    Get the global settings instance (singleton pattern).

    Args:
        reload: If True, reload settings from environment

    Returns:
        Settings instance
    """
    global _settings

    if _settings is None or reload:
        _settings = Settings()

    return _settings
