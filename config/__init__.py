"""
Configuration module for Odoo Tracker.

This module handles all application settings, environment variables,
and runtime configuration including performance parameters and logging setup.
"""

from .settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
