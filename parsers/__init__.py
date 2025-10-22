"""
Parsers module for Odoo Tracker.

This module contains parsers for Odoo source files:
- Manifest parser: Parse __manifest__.py files
- Model parser: Parse Python model files using AST
- XML parser: Parse Odoo view XML files
"""

from .manifest_parser import (
    find_modules,
    parse_manifest,
    get_manifest_dependencies,
    is_module_installable,
)

from .model_parser import (
    find_model_files,
    parse_model_file,
    is_odoo_model,
)

__all__ = [
    # Manifest parser
    "find_modules",
    "parse_manifest",
    "get_manifest_dependencies",
    "is_module_installable",
    # Model parser
    "find_model_files",
    "parse_model_file",
    "is_odoo_model",
]
