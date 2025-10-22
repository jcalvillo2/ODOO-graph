"""
Query module for Odoo ETL pipeline.

Provides functionality to query the Odoo dependency graph in Neo4j.
"""

from .query_dependencies import QueryInterface

__all__ = ["QueryInterface"]
