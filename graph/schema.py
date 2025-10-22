"""
Neo4j schema definitions for Odoo dependency tracker.

This module defines:
- Node labels (Module, Model, Field)
- Relationship types
- Index and constraint creation
- Schema initialization
"""

from typing import Dict, List
from utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# Node Labels
# ============================================================================

class NodeLabel:
    """Node label constants."""
    MODULE = "Module"
    MODEL = "Model"
    FIELD = "Field"


# ============================================================================
# Relationship Types
# ============================================================================

class RelationType:
    """Relationship type constants."""
    DEPENDS_ON = "DEPENDS_ON"           # Module -> Module
    INHERITS_FROM = "INHERITS_FROM"     # Model -> Model (_inherit)
    DELEGATES_TO = "DELEGATES_TO"       # Model -> Model (_inherits)
    DEFINED_IN = "DEFINED_IN"           # Model -> Module
    BELONGS_TO = "BELONGS_TO"           # Field -> Model
    REFERENCES = "REFERENCES"           # Field -> Model (for relational fields)


# ============================================================================
# Property Keys
# ============================================================================

class ModuleProperty:
    """Module node property keys."""
    NAME = "name"                       # Technical module name (directory name)
    DISPLAY_NAME = "display_name"       # Human-readable name from manifest
    VERSION = "version"
    CATEGORY = "category"
    SUMMARY = "summary"
    DESCRIPTION = "description"
    AUTHOR = "author"
    WEBSITE = "website"
    LICENSE = "license"
    INSTALLABLE = "installable"
    AUTO_INSTALL = "auto_install"
    APPLICATION = "application"
    FILE_PATH = "file_path"
    FILE_HASH = "file_hash"


class ModelProperty:
    """Model node property keys."""
    NAME = "name"                       # _name
    DESCRIPTION = "description"         # _description
    MODULE = "module"                   # Module where it's defined
    FILE_PATH = "file_path"
    LINE_NUMBER = "line_number"
    CLASS_NAME = "class_name"
    FILE_HASH = "file_hash"
    # Note: _inherit and _inherits are stored as relationships


class FieldProperty:
    """Field node property keys."""
    NAME = "name"                       # Field name
    FIELD_TYPE = "field_type"           # Char, Integer, Many2one, etc.
    STRING = "string"                   # Human-readable label
    REQUIRED = "required"
    READONLY = "readonly"
    HELP = "help"
    DEFAULT = "default"
    COMPUTE = "compute"
    STORE = "store"
    RELATED = "related"
    DEPENDS = "depends"
    INVERSE_NAME = "inverse_name"       # For One2many
    COMODEL_NAME = "comodel_name"       # For relational fields
    DOMAIN = "domain"
    SELECTION = "selection"
    STATES = "states"
    COPY = "copy"
    INDEX = "index"
    TRANSLATE = "translate"
    DIGITS = "digits"
    SANITIZE = "sanitize"
    STRIP_STYLE = "strip_style"


# ============================================================================
# Schema Creation Queries
# ============================================================================

def get_constraint_queries() -> List[Dict[str, str]]:
    """
    Get Cypher queries to create uniqueness constraints.

    Constraints ensure data integrity and automatically create indexes.

    Returns:
        List of query dictionaries with 'name' and 'query' keys
    """
    return [
        {
            "name": "Module name uniqueness",
            "query": f"""
                CREATE CONSTRAINT module_name_unique IF NOT EXISTS
                FOR (m:{NodeLabel.MODULE})
                REQUIRE m.{ModuleProperty.NAME} IS UNIQUE
            """
        },
        {
            "name": "Model name uniqueness",
            "query": f"""
                CREATE CONSTRAINT model_name_unique IF NOT EXISTS
                FOR (m:{NodeLabel.MODEL})
                REQUIRE m.{ModelProperty.NAME} IS UNIQUE
            """
        },
        {
            "name": "Field composite uniqueness",
            "query": f"""
                CREATE CONSTRAINT field_composite_unique IF NOT EXISTS
                FOR (f:{NodeLabel.FIELD})
                REQUIRE (f.{FieldProperty.NAME}, f.model_name) IS UNIQUE
            """
        }
    ]


def get_index_queries() -> List[Dict[str, str]]:
    """
    Get Cypher queries to create indexes for faster lookups.

    Returns:
        List of query dictionaries with 'name' and 'query' keys
    """
    return [
        # Module indexes
        {
            "name": "Module category index",
            "query": f"""
                CREATE INDEX module_category_idx IF NOT EXISTS
                FOR (m:{NodeLabel.MODULE})
                ON (m.{ModuleProperty.CATEGORY})
            """
        },
        {
            "name": "Module installable index",
            "query": f"""
                CREATE INDEX module_installable_idx IF NOT EXISTS
                FOR (m:{NodeLabel.MODULE})
                ON (m.{ModuleProperty.INSTALLABLE})
            """
        },
        {
            "name": "Module application index",
            "query": f"""
                CREATE INDEX module_application_idx IF NOT EXISTS
                FOR (m:{NodeLabel.MODULE})
                ON (m.{ModuleProperty.APPLICATION})
            """
        },

        # Model indexes
        {
            "name": "Model module index",
            "query": f"""
                CREATE INDEX model_module_idx IF NOT EXISTS
                FOR (m:{NodeLabel.MODEL})
                ON (m.{ModelProperty.MODULE})
            """
        },

        # Field indexes
        {
            "name": "Field type index",
            "query": f"""
                CREATE INDEX field_type_idx IF NOT EXISTS
                FOR (f:{NodeLabel.FIELD})
                ON (f.{FieldProperty.FIELD_TYPE})
            """
        },
        {
            "name": "Field model name index",
            "query": f"""
                CREATE INDEX field_model_name_idx IF NOT EXISTS
                FOR (f:{NodeLabel.FIELD})
                ON (f.model_name)
            """
        },
        {
            "name": "Field comodel index",
            "query": f"""
                CREATE INDEX field_comodel_idx IF NOT EXISTS
                FOR (f:{NodeLabel.FIELD})
                ON (f.{FieldProperty.COMODEL_NAME})
            """
        },
        {
            "name": "Field required index",
            "query": f"""
                CREATE INDEX field_required_idx IF NOT EXISTS
                FOR (f:{NodeLabel.FIELD})
                ON (f.{FieldProperty.REQUIRED})
            """
        }
    ]


def get_schema_info_query() -> str:
    """
    Get query to retrieve schema information.

    Returns:
        Cypher query string
    """
    return """
        CALL db.indexes()
        YIELD name, type, state, populationPercent
        RETURN name, type, state, populationPercent
        ORDER BY name
    """


# ============================================================================
# Schema Initialization
# ============================================================================

def initialize_schema(connection) -> Dict[str, any]:
    """
    Initialize the Neo4j schema with constraints and indexes.

    Args:
        connection: Neo4jConnection instance

    Returns:
        Dictionary with initialization results
    """
    logger.info("Initializing Neo4j schema...")

    results = {
        "constraints_created": 0,
        "indexes_created": 0,
        "errors": []
    }

    # Create constraints
    logger.info("Creating constraints...")
    for constraint in get_constraint_queries():
        try:
            connection.execute_write(constraint["query"], {})
            results["constraints_created"] += 1
            logger.info(f"✓ Created constraint: {constraint['name']}")
        except Exception as e:
            error_msg = f"Failed to create constraint '{constraint['name']}': {str(e)}"
            logger.warning(error_msg)
            results["errors"].append(error_msg)

    # Create indexes
    logger.info("Creating indexes...")
    for index in get_index_queries():
        try:
            connection.execute_write(index["query"], {})
            results["indexes_created"] += 1
            logger.info(f"✓ Created index: {index['name']}")
        except Exception as e:
            error_msg = f"Failed to create index '{index['name']}': {str(e)}"
            logger.warning(error_msg)
            results["errors"].append(error_msg)

    logger.info(
        f"Schema initialization complete: "
        f"{results['constraints_created']} constraints, "
        f"{results['indexes_created']} indexes, "
        f"{len(results['errors'])} errors"
    )

    return results


def verify_schema(connection) -> Dict[str, any]:
    """
    Verify that the schema is properly set up.

    Args:
        connection: Neo4jConnection instance

    Returns:
        Dictionary with schema verification results
    """
    logger.info("Verifying Neo4j schema...")

    try:
        indexes = connection.execute_query(get_schema_info_query(), {})

        results = {
            "total_indexes": len(indexes),
            "indexes": indexes,
            "valid": len(indexes) > 0
        }

        logger.info(f"Schema verification: {results['total_indexes']} indexes found")

        return results

    except Exception as e:
        logger.error(f"Schema verification failed: {str(e)}")
        return {
            "total_indexes": 0,
            "indexes": [],
            "valid": False,
            "error": str(e)
        }


# ============================================================================
# Helper Functions
# ============================================================================

def get_node_count_query(label: str) -> str:
    """
    Get query to count nodes of a specific label.

    Args:
        label: Node label (Module, Model, or Field)

    Returns:
        Cypher query string
    """
    return f"MATCH (n:{label}) RETURN count(n) as count"


def get_relationship_count_query(rel_type: str) -> str:
    """
    Get query to count relationships of a specific type.

    Args:
        rel_type: Relationship type

    Returns:
        Cypher query string
    """
    return f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"


def get_database_stats(connection) -> Dict[str, int]:
    """
    Get comprehensive database statistics.

    Args:
        connection: Neo4jConnection instance

    Returns:
        Dictionary with node and relationship counts
    """
    stats = {}

    # Count nodes
    for label in [NodeLabel.MODULE, NodeLabel.MODEL, NodeLabel.FIELD]:
        try:
            result = connection.execute_query(get_node_count_query(label), {})
            stats[f"{label.lower()}_count"] = result[0]["count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to count {label} nodes: {str(e)}")
            stats[f"{label.lower()}_count"] = 0

    # Count relationships
    for rel_type in [
        RelationType.DEPENDS_ON,
        RelationType.INHERITS_FROM,
        RelationType.DELEGATES_TO,
        RelationType.DEFINED_IN,
        RelationType.BELONGS_TO,
        RelationType.REFERENCES
    ]:
        try:
            result = connection.execute_query(get_relationship_count_query(rel_type), {})
            stats[f"{rel_type.lower()}_count"] = result[0]["count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to count {rel_type} relationships: {str(e)}")
            stats[f"{rel_type.lower()}_count"] = 0

    return stats
