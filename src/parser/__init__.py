"""
Parsers para módulos y modelos de Odoo.
"""

from .manifest_parser import ManifestParser
from .model_parser import ModelParser
from .view_parser import ViewParser

__all__ = ['ManifestParser', 'ModelParser', 'ViewParser']
