"""
Logging configuration for Odoo Tracker.

This module sets up structured logging with both file and console output.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "odoo_tracker",
    level: str = "INFO",
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Configure and return a logger instance.

    Sets up both console (stdout) and file logging with appropriate
    formatting and log levels.

    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    logger.handlers = []

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_formatter = logging.Formatter(
        "%(levelname)s: %(message)s"
    )

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (if log_file specified)
    if log_file:
        try:
            # Ensure parent directory exists
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(detailed_formatter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not create log file {log_file}: {e}")

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    This is a convenience wrapper around logging.getLogger that
    returns a logger that inherits from the main odoo_tracker logger.

    Args:
        name: Logger name (will be prefixed with 'odoo_tracker.')

    Returns:
        Logger instance
    """
    if not name.startswith("odoo_tracker"):
        name = f"odoo_tracker.{name}"

    return logging.getLogger(name)
