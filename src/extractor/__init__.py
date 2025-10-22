"""
Extractor module for Odoo ETL pipeline.

Provides functionality to extract metadata from Odoo modules, models, and views.
"""

from .parse_modules import discover_modules, ModuleParser, ModuleMetadata
from .index_models import index_models, ModelIndexer, ModelMetadata, FieldMetadata
from .index_views import index_views, ViewIndexer, ViewMetadata

__all__ = [
    "discover_modules",
    "ModuleParser",
    "ModuleMetadata",
    "index_models",
    "ModelIndexer",
    "ModelMetadata",
    "FieldMetadata",
    "index_views",
    "ViewIndexer",
    "ViewMetadata",
]
