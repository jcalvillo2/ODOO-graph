"""
Graph database module for Odoo Tracker.

This module handles all Neo4j interactions:
- Database connection management
- Node and relationship creation
- Batch operations for performance
- Query execution

Exports:
- Neo4jConnection: Connection manager
- OdooIndexer: Main indexing orchestrator
- Schema components: Node labels, relationship types, properties
- Functions: initialize_schema, verify_schema, get_database_stats
"""

from graph.connection import Neo4jConnection
from graph.indexer import OdooIndexer
from graph.schema import (
    NodeLabel,
    RelationType,
    ModuleProperty,
    ModelProperty,
    FieldProperty,
    initialize_schema,
    verify_schema,
    get_database_stats
)

__all__ = [
    "Neo4jConnection",
    "OdooIndexer",
    "NodeLabel",
    "RelationType",
    "ModuleProperty",
    "ModelProperty",
    "FieldProperty",
    "initialize_schema",
    "verify_schema",
    "get_database_stats"
]
