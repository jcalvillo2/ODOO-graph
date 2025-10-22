"""
Predefined Cypher queries for common operations.

This module provides ready-to-use queries for:
- Finding models and modules
- Analyzing dependencies
- Tracing inheritance
- Searching fields
"""

from typing import Dict, List, Any
from graph.schema import NodeLabel, RelationType, ModuleProperty, ModelProperty, FieldProperty


# ============================================================================
# Module Queries
# ============================================================================

def find_module_by_name(module_name: str) -> tuple[str, Dict[str, str]]:
    """
    Find a module by name.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH (m:{NodeLabel.MODULE} {{{ModuleProperty.NAME}: $name}})
        RETURN m
    """
    return query, {"name": module_name}


def get_module_dependencies(module_name: str) -> tuple[str, Dict[str, str]]:
    """
    Get all modules that a given module depends on.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH (m:{NodeLabel.MODULE} {{{ModuleProperty.NAME}: $name}})
              -[:{RelationType.DEPENDS_ON}]->(dep:{NodeLabel.MODULE})
        RETURN dep.{ModuleProperty.NAME} as dependency,
               dep.{ModuleProperty.VERSION} as version,
               dep.{ModuleProperty.CATEGORY} as category
        ORDER BY dep.{ModuleProperty.NAME}
    """
    return query, {"name": module_name}


def get_module_dependents(module_name: str) -> tuple[str, Dict[str, str]]:
    """
    Get all modules that depend on a given module.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH (dependent:{NodeLabel.MODULE})
              -[:{RelationType.DEPENDS_ON}]->(m:{NodeLabel.MODULE} {{{ModuleProperty.NAME}: $name}})
        RETURN dependent.{ModuleProperty.NAME} as dependent,
               dependent.{ModuleProperty.VERSION} as version,
               dependent.{ModuleProperty.CATEGORY} as category
        ORDER BY dependent.{ModuleProperty.NAME}
    """
    return query, {"name": module_name}


def list_all_modules(category: str = None, installable: bool = None) -> tuple[str, Dict[str, Any]]:
    """
    List all modules with optional filters.

    Args:
        category: Filter by category (optional)
        installable: Filter by installable flag (optional)

    Returns:
        Tuple of (query, parameters)
    """
    conditions = []
    params = {}

    if category:
        conditions.append(f"m.{ModuleProperty.CATEGORY} = $category")
        params["category"] = category

    if installable is not None:
        conditions.append(f"m.{ModuleProperty.INSTALLABLE} = $installable")
        params["installable"] = installable

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    query = f"""
        MATCH (m:{NodeLabel.MODULE})
        {where_clause}
        RETURN m.{ModuleProperty.NAME} as name,
               m.{ModuleProperty.VERSION} as version,
               m.{ModuleProperty.CATEGORY} as category,
               m.{ModuleProperty.SUMMARY} as summary,
               m.{ModuleProperty.INSTALLABLE} as installable
        ORDER BY m.{ModuleProperty.NAME}
    """
    return query, params


# ============================================================================
# Model Queries
# ============================================================================

def find_model_by_name(model_name: str) -> tuple[str, Dict[str, str]]:
    """
    Find a model by name.

    Returns all definitions (base + extensions via inheritance).
    The base definition (from core modules) is prioritized first based on file path.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH (model:{NodeLabel.MODEL} {{{ModelProperty.NAME}: $name}})
        OPTIONAL MATCH (model)-[:{RelationType.DEFINED_IN}]->(module:{NodeLabel.MODULE})
        WITH model, module,
             CASE
                // Prioritize by file path - base modules are in /addons/<module_name>/
                WHEN model.{ModelProperty.FILE_PATH} CONTAINS '/addons/stock/' THEN 1
                WHEN model.{ModelProperty.FILE_PATH} CONTAINS '/addons/sale/' THEN 1
                WHEN model.{ModelProperty.FILE_PATH} CONTAINS '/addons/account/' THEN 1
                WHEN model.{ModelProperty.FILE_PATH} CONTAINS '/addons/purchase/' THEN 1
                WHEN model.{ModelProperty.FILE_PATH} CONTAINS '/addons/mrp/' THEN 1
                WHEN model.{ModelProperty.FILE_PATH} CONTAINS '/addons/project/' THEN 1
                // Then modules that don't contain l10n
                WHEN NOT model.{ModelProperty.FILE_PATH} CONTAINS '/l10n_' THEN 2
                // Last: localization modules
                ELSE 3
             END as priority
        RETURN DISTINCT model,
               module.{ModuleProperty.NAME} as module_name,
               priority
        ORDER BY priority, model.{ModelProperty.FILE_PATH}
        LIMIT 5
    """
    return query, {"name": model_name}


def get_model_inheritance_tree(model_name: str, max_depth: int = 10) -> tuple[str, Dict[str, Any]]:
    """
    Get the inheritance tree for a model.

    Args:
        model_name: Model name
        max_depth: Maximum inheritance depth

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH path = (m:{NodeLabel.MODEL} {{{ModelProperty.NAME}: $name}})
                     -[:{RelationType.INHERITS_FROM}*0..{max_depth}]->(parent:{NodeLabel.MODEL})
        RETURN m.{ModelProperty.NAME} as model,
               parent.{ModelProperty.NAME} as parent,
               length(path) as depth
        ORDER BY depth
    """
    return query, {"name": model_name}


def get_model_children(model_name: str) -> tuple[str, Dict[str, str]]:
    """
    Get all models that inherit from a given model.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH (child:{NodeLabel.MODEL})
              -[:{RelationType.INHERITS_FROM}]->(parent:{NodeLabel.MODEL} {{{ModelProperty.NAME}: $name}})
        RETURN child.{ModelProperty.NAME} as child,
               child.{ModelProperty.DESCRIPTION} as description
        ORDER BY child.{ModelProperty.NAME}
    """
    return query, {"name": model_name}


def get_model_delegation(model_name: str) -> tuple[str, Dict[str, str]]:
    """
    Get models that a given model delegates to (_inherits).

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH (m:{NodeLabel.MODEL} {{{ModelProperty.NAME}: $name}})
              -[r:{RelationType.DELEGATES_TO}]->(delegated:{NodeLabel.MODEL})
        RETURN delegated.{ModelProperty.NAME} as delegated_model,
               r.field as field_name
        ORDER BY delegated.{ModelProperty.NAME}
    """
    return query, {"name": model_name}


def list_models_in_module(module_name: str) -> tuple[str, Dict[str, str]]:
    """
    List all models defined in a module.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH (model:{NodeLabel.MODEL})
              -[:{RelationType.DEFINED_IN}]->(module:{NodeLabel.MODULE} {{{ModuleProperty.NAME}: $name}})
        RETURN model.{ModelProperty.NAME} as name,
               model.{ModelProperty.DESCRIPTION} as description,
               model.{ModelProperty.FILE_PATH} as file_path
        ORDER BY model.{ModelProperty.NAME}
    """
    return query, {"name": module_name}


def list_all_models(module: str = None) -> tuple[str, Dict[str, Any]]:
    """
    List all models with optional module filter.

    Returns:
        Tuple of (query, parameters)
    """
    params = {}
    where_clause = ""

    if module:
        where_clause = f"WHERE model.{ModelProperty.MODULE} = $module"
        params["module"] = module

    query = f"""
        MATCH (model:{NodeLabel.MODEL})
        {where_clause}
        RETURN model.{ModelProperty.NAME} as name,
               model.{ModelProperty.DESCRIPTION} as description,
               model.{ModelProperty.MODULE} as module
        ORDER BY model.{ModelProperty.NAME}
    """
    return query, params


# ============================================================================
# Field Queries
# ============================================================================

def get_model_fields(model_name: str) -> tuple[str, Dict[str, str]]:
    """
    Get all fields for a model.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH (field:{NodeLabel.FIELD})
              -[:{RelationType.BELONGS_TO}]->(model:{NodeLabel.MODEL} {{{ModelProperty.NAME}: $name}})
        RETURN field.{FieldProperty.NAME} as name,
               field.{FieldProperty.FIELD_TYPE} as type,
               field.{FieldProperty.STRING} as string,
               field.{FieldProperty.REQUIRED} as required,
               field.{FieldProperty.READONLY} as readonly,
               field.{FieldProperty.HELP} as help,
               field.{FieldProperty.COMODEL_NAME} as comodel_name
        ORDER BY field.{FieldProperty.NAME}
    """
    return query, {"name": model_name}


def find_field_by_name(field_name: str, model_name: str = None) -> tuple[str, Dict[str, Any]]:
    """
    Find fields by name across all models or in a specific model.

    Returns:
        Tuple of (query, parameters)
    """
    params = {"field_name": field_name}
    where_clauses = [f"field.{FieldProperty.NAME} = $field_name"]

    if model_name:
        where_clauses.append("field.model_name = $model_name")
        params["model_name"] = model_name

    where_clause = "WHERE " + " AND ".join(where_clauses)

    query = f"""
        MATCH (field:{NodeLabel.FIELD})
              -[:{RelationType.BELONGS_TO}]->(model:{NodeLabel.MODEL})
        {where_clause}
        RETURN field.{FieldProperty.NAME} as name,
               model.{ModelProperty.NAME} as model,
               field.{FieldProperty.FIELD_TYPE} as type,
               field.{FieldProperty.STRING} as string,
               field.{FieldProperty.REQUIRED} as required
        ORDER BY model.{ModelProperty.NAME}
    """
    return query, params


def find_relational_fields(model_name: str = None) -> tuple[str, Dict[str, Any]]:
    """
    Find all relational fields (Many2one, One2many, Many2many).

    Returns:
        Tuple of (query, parameters)
    """
    params = {}
    where_clause = ""

    if model_name:
        where_clause = "WHERE field.model_name = $model_name"
        params["model_name"] = model_name

    query = f"""
        MATCH (field:{NodeLabel.FIELD})
              -[:{RelationType.REFERENCES}]->(target:{NodeLabel.MODEL})
        {where_clause}
        RETURN field.{FieldProperty.NAME} as field_name,
               field.model_name as source_model,
               field.{FieldProperty.FIELD_TYPE} as field_type,
               target.{ModelProperty.NAME} as target_model
        ORDER BY field.model_name, field.{FieldProperty.NAME}
    """
    return query, params


def find_computed_fields(model_name: str = None) -> tuple[str, Dict[str, Any]]:
    """
    Find all computed fields.

    Returns:
        Tuple of (query, parameters)
    """
    params = {}
    where_clauses = [f"field.{FieldProperty.COMPUTE} IS NOT NULL"]

    if model_name:
        where_clauses.append("field.model_name = $model_name")
        params["model_name"] = model_name

    where_clause = "WHERE " + " AND ".join(where_clauses)

    query = f"""
        MATCH (field:{NodeLabel.FIELD})
              -[:{RelationType.BELONGS_TO}]->(model:{NodeLabel.MODEL})
        {where_clause}
        RETURN field.{FieldProperty.NAME} as field_name,
               model.{ModelProperty.NAME} as model,
               field.{FieldProperty.FIELD_TYPE} as type,
               field.{FieldProperty.COMPUTE} as compute_method,
               field.{FieldProperty.STORE} as stored
        ORDER BY model.{ModelProperty.NAME}, field.{FieldProperty.NAME}
    """
    return query, params


# ============================================================================
# Advanced Queries
# ============================================================================

def detect_circular_dependencies(max_depth: int = 10) -> tuple[str, Dict[str, int]]:
    """
    Detect circular dependencies in modules.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH path = (m:{NodeLabel.MODULE})
                     -[:{RelationType.DEPENDS_ON}*1..{max_depth}]->(m)
        RETURN m.{ModuleProperty.NAME} as module,
               length(path) as cycle_length,
               [node in nodes(path) | node.{ModuleProperty.NAME}] as cycle_path
        ORDER BY cycle_length
    """
    return query, {"max_depth": max_depth}


def get_dependency_chain(from_module: str, to_module: str, max_depth: int = 10) -> tuple[str, Dict[str, Any]]:
    """
    Find dependency path between two modules.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH path = shortestPath(
            (from:{NodeLabel.MODULE} {{{ModuleProperty.NAME}: $from}})
            -[:{RelationType.DEPENDS_ON}*1..{max_depth}]->
            (to:{NodeLabel.MODULE} {{{ModuleProperty.NAME}: $to}})
        )
        RETURN [node in nodes(path) | node.{ModuleProperty.NAME}] as path,
               length(path) as depth
    """
    return query, {"from": from_module, "to": to_module, "max_depth": max_depth}


def get_model_relationship_graph(model_name: str, depth: int = 2) -> tuple[str, Dict[str, Any]]:
    """
    Get a subgraph of model relationships.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH path = (m:{NodeLabel.MODEL} {{{ModelProperty.NAME}: $name}})
                     -[:{RelationType.INHERITS_FROM}|{RelationType.DELEGATES_TO}*0..{depth}]-
                     (related:{NodeLabel.MODEL})
        RETURN DISTINCT
               m.{ModelProperty.NAME} as center_model,
               related.{ModelProperty.NAME} as related_model,
               type(relationships(path)[0]) as relationship_type,
               length(path) as distance
        ORDER BY distance, related.{ModelProperty.NAME}
    """
    return query, {"name": model_name, "depth": depth}


def get_database_overview() -> tuple[str, Dict]:
    """
    Get overview statistics of the database.

    Returns:
        Tuple of (query, parameters)
    """
    query = f"""
        MATCH (module:{NodeLabel.MODULE})
        WITH count(module) as module_count
        MATCH (model:{NodeLabel.MODEL})
        WITH module_count, count(model) as model_count
        MATCH (field:{NodeLabel.FIELD})
        WITH module_count, model_count, count(field) as field_count
        MATCH ()-[dep:{RelationType.DEPENDS_ON}]->()
        WITH module_count, model_count, field_count, count(dep) as dependency_count
        MATCH ()-[inh:{RelationType.INHERITS_FROM}]->()
        RETURN module_count, model_count, field_count, dependency_count, count(inh) as inheritance_count
    """
    return query, {}
