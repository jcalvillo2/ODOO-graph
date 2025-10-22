"""
Transformer module for Odoo ETL pipeline.

Provides functionality for data transformation and incremental update tracking.
"""

from .incremental_updates import StateTracker, IncrementalUpdater, FileState

__all__ = ["StateTracker", "IncrementalUpdater", "FileState"]
