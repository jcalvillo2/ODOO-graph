"""
Batch operations for efficiently loading data into Neo4j.

This module provides functions to insert nodes and relationships in batches,
minimizing network round-trips and transaction overhead.
"""

import json
from typing import List, Dict, Any
from utils.logger import get_logger
from graph.schema import (
    NodeLabel,
    RelationType,
    ModuleProperty,
    ModelProperty,
    FieldProperty
)

logger = get_logger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def _serialize_for_neo4j(value: Any) -> Any:
    """
    Convert Python values to Neo4j-compatible types.

    Neo4j cannot store nested collections, so we convert them to JSON strings.

    Args:
        value: Python value to convert

    Returns:
        Neo4j-compatible value
    """
    if value is None:
        return None
    elif isinstance(value, (list, dict)):
        # Convert nested collections to JSON string
        return json.dumps(value)
    elif isinstance(value, bool):
        return value
    elif isinstance(value, (int, float, str)):
        return value
    else:
        # Convert other types to string
        return str(value)


def _prepare_fields_for_neo4j(fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prepare field dictionaries for Neo4j insertion.

    Converts nested collections to JSON strings.

    Args:
        fields: List of field dictionaries

    Returns:
        List of Neo4j-compatible field dictionaries
    """
    prepared = []
    for field in fields:
        prepared_field = {}
        for key, value in field.items():
            prepared_field[key] = _serialize_for_neo4j(value)
        prepared.append(prepared_field)
    return prepared


# ============================================================================
# Module Operations
# ============================================================================

def create_modules_batch(connection, modules: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Create Module nodes in batch.

    Args:
        connection: Neo4jConnection instance
        modules: List of module dictionaries

    Returns:
        Dictionary with operation results
    """
    if not modules:
        return {"created": 0, "errors": 0}

    query = f"""
        UNWIND $batch AS module
        MERGE (m:{NodeLabel.MODULE} {{{ModuleProperty.NAME}: module.name}})
        SET m.{ModuleProperty.DISPLAY_NAME} = module.display_name,
            m.{ModuleProperty.VERSION} = module.version,
            m.{ModuleProperty.CATEGORY} = module.category,
            m.{ModuleProperty.SUMMARY} = module.summary,
            m.{ModuleProperty.DESCRIPTION} = module.description,
            m.{ModuleProperty.AUTHOR} = module.author,
            m.{ModuleProperty.WEBSITE} = module.website,
            m.{ModuleProperty.LICENSE} = module.license,
            m.{ModuleProperty.INSTALLABLE} = module.installable,
            m.{ModuleProperty.AUTO_INSTALL} = module.auto_install,
            m.{ModuleProperty.APPLICATION} = module.application,
            m.{ModuleProperty.FILE_PATH} = module.file_path,
            m.{ModuleProperty.FILE_HASH} = module.file_hash
        RETURN count(m) as created
    """

    try:
        result = connection.execute_batch(query, modules)
        created = result.get("nodes_created", 0) + result.get("properties_set", 0) // 13  # Approximate (13 properties now)
        logger.info(f"Created/updated {created} Module nodes")
        return {"created": created, "errors": 0}
    except Exception as e:
        logger.error(f"Failed to create modules batch: {str(e)}")
        return {"created": 0, "errors": len(modules)}


def create_module_dependencies_batch(
    connection,
    dependencies: List[Dict[str, str]]
) -> Dict[str, int]:
    """
    Create DEPENDS_ON relationships between modules in batch.

    Args:
        connection: Neo4jConnection instance
        dependencies: List of {"from": "module1", "to": "module2"} dictionaries

    Returns:
        Dictionary with operation results
    """
    if not dependencies:
        return {"created": 0, "errors": 0}

    query = f"""
        UNWIND $batch AS dep
        MATCH (from:{NodeLabel.MODULE} {{{ModuleProperty.NAME}: dep.from}})
        MATCH (to:{NodeLabel.MODULE} {{{ModuleProperty.NAME}: dep.to}})
        MERGE (from)-[r:{RelationType.DEPENDS_ON}]->(to)
        RETURN count(r) as created
    """

    try:
        result = connection.execute_batch(query, dependencies)
        created = result.get("relationships_created", 0)
        logger.info(f"Created {created} DEPENDS_ON relationships")
        return {"created": created, "errors": 0}
    except Exception as e:
        logger.error(f"Failed to create module dependencies: {str(e)}")
        return {"created": 0, "errors": len(dependencies)}


# ============================================================================
# Model Operations
# ============================================================================

def create_models_batch(connection, models: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Create Model nodes in batch.

    Args:
        connection: Neo4jConnection instance
        models: List of model dictionaries

    Returns:
        Dictionary with operation results
    """
    if not models:
        return {"created": 0, "errors": 0}

    query = f"""
        UNWIND $batch AS model
        MERGE (m:{NodeLabel.MODEL} {{{ModelProperty.NAME}: model.name}})
        SET m.{ModelProperty.DESCRIPTION} = model.description,
            m.{ModelProperty.MODULE} = model.module,
            m.{ModelProperty.FILE_PATH} = model.file_path,
            m.{ModelProperty.LINE_NUMBER} = model.line_number,
            m.{ModelProperty.CLASS_NAME} = model.class_name,
            m.{ModelProperty.FILE_HASH} = model.file_hash
        RETURN count(m) as created
    """

    try:
        result = connection.execute_batch(query, models)
        created = result.get("nodes_created", 0) + result.get("properties_set", 0) // 6  # Approximate
        logger.info(f"Created/updated {created} Model nodes")
        return {"created": created, "errors": 0}
    except Exception as e:
        logger.error(f"Failed to create models batch: {str(e)}")
        return {"created": 0, "errors": len(models)}


def create_model_module_relationships_batch(
    connection,
    relationships: List[Dict[str, str]]
) -> Dict[str, int]:
    """
    Create DEFINED_IN relationships between models and modules in batch.

    Args:
        connection: Neo4jConnection instance
        relationships: List of {"model": "model_name", "module": "module_name"} dicts

    Returns:
        Dictionary with operation results
    """
    if not relationships:
        return {"created": 0, "errors": 0}

    query = f"""
        UNWIND $batch AS rel
        MATCH (model:{NodeLabel.MODEL} {{{ModelProperty.NAME}: rel.model}})
        MATCH (module:{NodeLabel.MODULE} {{{ModuleProperty.NAME}: rel.module}})
        MERGE (model)-[r:{RelationType.DEFINED_IN}]->(module)
        RETURN count(r) as created
    """

    try:
        result = connection.execute_batch(query, relationships)
        created = result.get("relationships_created", 0)
        logger.info(f"Created {created} DEFINED_IN relationships")
        return {"created": created, "errors": 0}
    except Exception as e:
        logger.error(f"Failed to create model-module relationships: {str(e)}")
        return {"created": 0, "errors": len(relationships)}


def create_model_inheritance_batch(
    connection,
    inheritances: List[Dict[str, str]]
) -> Dict[str, int]:
    """
    Create INHERITS_FROM relationships between models in batch.

    Args:
        connection: Neo4jConnection instance
        inheritances: List of {"from": "child_model", "to": "parent_model"} dicts

    Returns:
        Dictionary with operation results
    """
    if not inheritances:
        return {"created": 0, "errors": 0}

    query = f"""
        UNWIND $batch AS inh
        MATCH (from:{NodeLabel.MODEL} {{{ModelProperty.NAME}: inh.from}})
        MATCH (to:{NodeLabel.MODEL} {{{ModelProperty.NAME}: inh.to}})
        MERGE (from)-[r:{RelationType.INHERITS_FROM}]->(to)
        RETURN count(r) as created
    """

    try:
        result = connection.execute_batch(query, inheritances)
        created = result.get("relationships_created", 0)
        logger.info(f"Created {created} INHERITS_FROM relationships")
        return {"created": created, "errors": 0}
    except Exception as e:
        logger.error(f"Failed to create model inheritance: {str(e)}")
        return {"created": 0, "errors": len(inheritances)}


def create_model_delegation_batch(
    connection,
    delegations: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Create DELEGATES_TO relationships between models in batch.

    Args:
        connection: Neo4jConnection instance
        delegations: List of {"from": "model", "to": "delegated_model", "field": "field_name"}

    Returns:
        Dictionary with operation results
    """
    if not delegations:
        return {"created": 0, "errors": 0}

    query = f"""
        UNWIND $batch AS del
        MATCH (from:{NodeLabel.MODEL} {{{ModelProperty.NAME}: del.from}})
        MATCH (to:{NodeLabel.MODEL} {{{ModelProperty.NAME}: del.to}})
        MERGE (from)-[r:{RelationType.DELEGATES_TO} {{field: del.field}}]->(to)
        RETURN count(r) as created
    """

    try:
        result = connection.execute_batch(query, delegations)
        created = result.get("relationships_created", 0)
        logger.info(f"Created {created} DELEGATES_TO relationships")
        return {"created": created, "errors": 0}
    except Exception as e:
        logger.error(f"Failed to create model delegation: {str(e)}")
        return {"created": 0, "errors": len(delegations)}


# ============================================================================
# Field Operations
# ============================================================================

def create_fields_batch(connection, fields: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Create Field nodes in batch.

    Args:
        connection: Neo4jConnection instance
        fields: List of field dictionaries with all parameters

    Returns:
        Dictionary with operation results
    """
    if not fields:
        return {"created": 0, "errors": 0}

    # Prepare fields for Neo4j (convert nested collections to JSON)
    prepared_fields = _prepare_fields_for_neo4j(fields)

    # Build SET clause dynamically for all field properties
    query = f"""
        UNWIND $batch AS field
        MERGE (f:{NodeLabel.FIELD} {{
            {FieldProperty.NAME}: field.name,
            model_name: field.model_name
        }})
        SET f.{FieldProperty.NAME} = field.name,
            f.model_name = field.model_name,
            f.{FieldProperty.FIELD_TYPE} = field.field_type,
            f.{FieldProperty.STRING} = field.string,
            f.{FieldProperty.REQUIRED} = field.required,
            f.{FieldProperty.READONLY} = field.readonly,
            f.{FieldProperty.HELP} = field.help,
            f.{FieldProperty.DEFAULT} = field.default,
            f.{FieldProperty.COMPUTE} = field.compute,
            f.{FieldProperty.STORE} = field.store,
            f.{FieldProperty.RELATED} = field.related,
            f.{FieldProperty.DEPENDS} = field.depends,
            f.{FieldProperty.INVERSE_NAME} = field.inverse_name,
            f.{FieldProperty.COMODEL_NAME} = field.comodel_name,
            f.{FieldProperty.DOMAIN} = field.domain,
            f.{FieldProperty.SELECTION} = field.selection,
            f.{FieldProperty.STATES} = field.states,
            f.{FieldProperty.COPY} = field.copy,
            f.{FieldProperty.INDEX} = field.index,
            f.{FieldProperty.TRANSLATE} = field.translate,
            f.{FieldProperty.DIGITS} = field.digits,
            f.{FieldProperty.SANITIZE} = field.sanitize,
            f.{FieldProperty.STRIP_STYLE} = field.strip_style
        RETURN count(f) as created
    """

    try:
        result = connection.execute_batch(query, prepared_fields)
        created = result.get("nodes_created", 0)
        logger.info(f"Created {created} Field nodes")
        return {"created": created, "errors": 0}
    except Exception as e:
        logger.error(f"Failed to create fields batch: {str(e)}")
        return {"created": 0, "errors": len(fields)}


def create_field_model_relationships_batch(
    connection,
    relationships: List[Dict[str, str]]
) -> Dict[str, int]:
    """
    Create BELONGS_TO relationships between fields and models in batch.

    Args:
        connection: Neo4jConnection instance
        relationships: List of {"field_name": "name", "model_name": "model"} dicts

    Returns:
        Dictionary with operation results
    """
    if not relationships:
        return {"created": 0, "errors": 0}

    query = f"""
        UNWIND $batch AS rel
        MATCH (field:{NodeLabel.FIELD} {{
            {FieldProperty.NAME}: rel.field_name,
            model_name: rel.model_name
        }})
        MATCH (model:{NodeLabel.MODEL} {{{ModelProperty.NAME}: rel.model_name}})
        MERGE (field)-[r:{RelationType.BELONGS_TO}]->(model)
        RETURN count(r) as created
    """

    try:
        result = connection.execute_batch(query, relationships)
        created = result.get("relationships_created", 0)
        logger.info(f"Created {created} BELONGS_TO relationships")
        return {"created": created, "errors": 0}
    except Exception as e:
        logger.error(f"Failed to create field-model relationships: {str(e)}")
        return {"created": 0, "errors": len(relationships)}


def create_field_references_batch(
    connection,
    references: List[Dict[str, str]]
) -> Dict[str, int]:
    """
    Create REFERENCES relationships between fields and models in batch.
    Used for relational fields (Many2one, One2many, Many2many).

    Args:
        connection: Neo4jConnection instance
        references: List of {"field_name": "name", "model_name": "model", "comodel": "target"}

    Returns:
        Dictionary with operation results
    """
    if not references:
        return {"created": 0, "errors": 0}

    query = f"""
        UNWIND $batch AS ref
        MATCH (field:{NodeLabel.FIELD} {{
            {FieldProperty.NAME}: ref.field_name,
            model_name: ref.model_name
        }})
        MATCH (target:{NodeLabel.MODEL} {{{ModelProperty.NAME}: ref.comodel}})
        MERGE (field)-[r:{RelationType.REFERENCES}]->(target)
        RETURN count(r) as created
    """

    try:
        result = connection.execute_batch(query, references)
        created = result.get("relationships_created", 0)
        logger.info(f"Created {created} REFERENCES relationships")
        return {"created": created, "errors": 0}
    except Exception as e:
        logger.error(f"Failed to create field references: {str(e)}")
        return {"created": 0, "errors": len(references)}


# ============================================================================
# Utility Functions
# ============================================================================

def process_in_batches(
    connection,
    items: List[Any],
    batch_size: int,
    operation_func,
    operation_name: str
) -> Dict[str, int]:
    """
    Process items in batches using a specified operation function.

    Args:
        connection: Neo4jConnection instance
        items: List of items to process
        batch_size: Number of items per batch
        operation_func: Function to call for each batch
        operation_name: Name for logging

    Returns:
        Dictionary with aggregated results
    """
    if not items:
        logger.info(f"No items to process for {operation_name}")
        return {"created": 0, "errors": 0}

    total_created = 0
    total_errors = 0
    total_batches = (len(items) + batch_size - 1) // batch_size

    logger.info(f"Processing {len(items)} items in {total_batches} batches for {operation_name}")

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_num = i // batch_size + 1

        logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} items)")

        result = operation_func(connection, batch)
        total_created += result.get("created", 0)
        total_errors += result.get("errors", 0)

    logger.info(
        f"Completed {operation_name}: "
        f"{total_created} created, {total_errors} errors"
    )

    return {"created": total_created, "errors": total_errors}
