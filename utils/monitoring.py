"""
Memory monitoring utilities for tracking resource usage.

This module provides tools to monitor memory consumption and
ensure the application stays within configured limits.
"""

import logging
from typing import Optional

import psutil

logger = logging.getLogger(__name__)


class MemoryMonitor:
    """
    Monitor memory usage and provide warnings when limits are exceeded.

    This class helps prevent out-of-memory errors by tracking current
    memory usage and comparing it against configured thresholds.
    """

    def __init__(self, max_percent: float = 70.0):
        """
        Initialize the memory monitor.

        Args:
            max_percent: Maximum allowed memory usage as percentage (0-100)
        """
        if not (0 < max_percent <= 100):
            raise ValueError("max_percent must be between 0 and 100")

        self.max_percent = max_percent
        self.process = psutil.Process()

    def get_current_usage(self) -> dict:
        """
        Get current memory usage statistics.

        Returns:
            Dictionary with memory usage information including:
            - percent: Current system memory usage as percentage
            - used_mb: Memory used by this process in MB
            - available_mb: Available system memory in MB
            - total_mb: Total system memory in MB
        """
        memory = psutil.virtual_memory()
        process_memory = self.process.memory_info()

        return {
            "percent": memory.percent,
            "used_mb": process_memory.rss / (1024 * 1024),  # Convert to MB
            "available_mb": memory.available / (1024 * 1024),
            "total_mb": memory.total / (1024 * 1024),
        }

    def is_memory_ok(self) -> bool:
        """
        Check if current memory usage is within acceptable limits.

        Returns:
            True if memory usage is below threshold, False otherwise
        """
        current = self.get_current_usage()
        return current["percent"] < self.max_percent

    def check_and_warn(self) -> bool:
        """
        Check memory usage and log warning if threshold exceeded.

        Returns:
            True if memory is OK, False if threshold exceeded
        """
        stats = self.get_current_usage()

        if stats["percent"] >= self.max_percent:
            logger.warning(
                f"Memory usage high: {stats['percent']:.1f}% "
                f"(threshold: {self.max_percent}%). "
                f"Process using {stats['used_mb']:.1f}MB. "
                f"Available: {stats['available_mb']:.1f}MB"
            )
            return False

        return True

    def log_stats(self, level: int = logging.INFO):
        """
        Log current memory statistics.

        Args:
            level: Logging level (default: INFO)
        """
        stats = self.get_current_usage()
        logger.log(
            level,
            f"Memory: {stats['percent']:.1f}% system, "
            f"{stats['used_mb']:.1f}MB process, "
            f"{stats['available_mb']:.1f}MB available",
        )


def check_memory_usage(max_percent: float = 70.0) -> Optional[dict]:
    """
    Quick check of current memory usage.

    Args:
        max_percent: Maximum allowed memory usage as percentage

    Returns:
        Memory statistics dict if usage exceeds threshold, None otherwise
    """
    monitor = MemoryMonitor(max_percent)
    stats = monitor.get_current_usage()

    if stats["percent"] >= max_percent:
        return stats

    return None
