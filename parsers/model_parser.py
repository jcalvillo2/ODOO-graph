"""
Model parser for Odoo Python files.

This module provides functions to discover and parse Odoo model files,
extracting model definitions, fields, and inheritance information using AST.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# Odoo field types to detect
ODOO_FIELD_TYPES = {
    'Char', 'Text', 'Integer', 'Float', 'Boolean', 'Date', 'Datetime',
    'Binary', 'Selection', 'Html', 'Monetary',
    'Many2one', 'One2many', 'Many2many',
    'Reference', 'Json', 'Properties',
}


def find_model_files(module_path: Path) -> Generator[Path, None, None]:
    """
    Find Python files in a module's models/ directory.

    Args:
        module_path: Path to Odoo module directory

    Yields:
        Path objects to Python model files

    Example:
        >>> for file_path in find_model_files(Path("/odoo/addons/sale")):
        ...     print(file_path.name)
        sale_order.py
        sale_order_line.py
    """
    if not module_path.is_dir():
        logger.debug(f"Not a directory: {module_path}")
        return

    # Look for models in common locations
    model_dirs = [
        module_path / "models",
        module_path,  # Some modules have models in root
    ]

    for models_dir in model_dirs:
        if not models_dir.exists() or not models_dir.is_dir():
            continue

        try:
            for py_file in models_dir.glob("*.py"):
                # Skip __init__.py and __manifest__.py
                if py_file.name.startswith("__"):
                    continue

                logger.debug(f"Found model file: {py_file}")
                yield py_file

        except PermissionError as e:
            logger.warning(f"Permission denied accessing {models_dir}: {e}")
        except OSError as e:
            logger.warning(f"OS error accessing {models_dir}: {e}")


def parse_model_file(file_path: Path, module_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parse a Python file and extract all Odoo model definitions.

    Args:
        file_path: Path to Python file
        module_name: Optional module name (inferred from path if not provided)

    Returns:
        List of dictionaries with model metadata

    Example:
        >>> models = parse_model_file(Path("/odoo/addons/sale/models/sale_order.py"))
        >>> print(models[0]["name"])
        sale.order
    """
    if not file_path.is_file():
        logger.error(f"Not a file: {file_path}")
        return []

    # Infer module name from path if not provided
    if module_name is None:
        # Path structure: .../module_name/models/file.py
        parts = file_path.parts
        if "models" in parts:
            idx = parts.index("models")
            module_name = parts[idx - 1] if idx > 0 else "unknown"
        else:
            module_name = file_path.parent.name

    # Try different encodings
    encodings = ["utf-8", "latin-1", "iso-8859-1"]
    content = None

    for encoding in encodings:
        try:
            content = file_path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return []

    if content is None:
        logger.error(f"Could not decode {file_path} with any encoding")
        return []

    # Parse with AST
    try:
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        logger.warning(f"Syntax error in {file_path}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing {file_path}: {e}")
        return []

    # Extract models from AST
    models = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if is_odoo_model(node):
                model_data = extract_model_from_class(node, file_path, module_name)
                if model_data:
                    models.append(model_data)

    return models


def is_odoo_model(class_node: ast.ClassDef) -> bool:
    """
    Check if a class is an Odoo model.

    An Odoo model inherits from models.Model, models.TransientModel,
    or models.AbstractModel.

    Args:
        class_node: AST ClassDef node

    Returns:
        True if this is an Odoo model class
    """
    for base in class_node.bases:
        # Check for models.Model, models.TransientModel, etc.
        if isinstance(base, ast.Attribute):
            if isinstance(base.value, ast.Name):
                # models.Model pattern
                if base.value.id == "models" and base.attr in ["Model", "TransientModel", "AbstractModel"]:
                    return True

        # Check for direct class names (less common)
        if isinstance(base, ast.Name):
            if base.id in ["Model", "TransientModel", "AbstractModel"]:
                return True

    return False


def extract_model_from_class(
    class_node: ast.ClassDef,
    file_path: Path,
    module_name: str
) -> Optional[Dict[str, Any]]:
    """
    Extract model metadata from a class AST node.

    Args:
        class_node: AST ClassDef node
        file_path: Path to source file
        module_name: Name of Odoo module

    Returns:
        Dictionary with model metadata, or None if extraction failed
    """
    model_data = {
        "class_name": class_node.name,
        "name": None,
        "description": None,
        "inherit": [],
        "inherits": {},
        "fields": {},
        "file_path": str(file_path),
        "module_name": module_name,
        "line_number": class_node.lineno,
    }

    # Extract model attributes and fields
    for item in class_node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id

                    # Extract _name
                    if var_name == "_name":
                        model_data["name"] = _get_string_value(item.value)

                    # Extract _description
                    elif var_name == "_description":
                        model_data["description"] = _get_string_value(item.value)

                    # Extract _inherit
                    elif var_name == "_inherit":
                        inherit_value = _ast_node_to_python(item.value)
                        if isinstance(inherit_value, str):
                            model_data["inherit"] = [inherit_value]
                        elif isinstance(inherit_value, list):
                            model_data["inherit"] = [
                                v for v in inherit_value if isinstance(v, str)
                            ]

                    # Extract _inherits
                    elif var_name == "_inherits":
                        inherits_value = _ast_node_to_python(item.value)
                        if isinstance(inherits_value, dict):
                            model_data["inherits"] = inherits_value

                    # Extract field definitions
                    elif _is_field_definition(item.value):
                        field_info = _extract_field_info(item.value)
                        if field_info:
                            model_data["fields"][var_name] = field_info

    # IMPORTANT: Only process classes that DEFINE a model with _name
    # Classes with only _inherit are extensions, not definitions
    # Extensions should not create separate Model nodes
    if not model_data["name"]:
        logger.debug(f"Class {class_node.name} has only _inherit (extension) - skipping Model node creation")
        return None

    # Special case: If _name and _inherit include the same model name, it's an extension
    # Example: _name = 'sale.order' and _inherit = ['sale.order', 'other.mixin']
    # This is functionally equivalent to just _inherit
    if model_data["name"] in model_data["inherit"]:
        logger.debug(f"Class {class_node.name} has _name=_inherit (extension) - skipping Model node creation")
        return None

    # Mark if this is an extension (has both _name and _inherit with different models)
    model_data["is_extension"] = len(model_data["inherit"]) > 0

    # Convert fields dict to list format with field names
    fields_list = []
    for field_name, field_info in model_data["fields"].items():
        if isinstance(field_info, dict):
            field_data = {"name": field_name}
            field_data.update(field_info)
            fields_list.append(field_data)
    model_data["fields"] = fields_list

    return model_data


def _is_field_definition(node: ast.AST) -> bool:
    """
    Check if an AST node is an Odoo field definition.

    Args:
        node: AST node to check

    Returns:
        True if this is a field definition (e.g., fields.Char(...))
    """
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            # fields.Char(...) pattern
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == "fields" and node.func.attr in ODOO_FIELD_TYPES:
                    return True

    return False


def _extract_field_info(node: ast.Call) -> Optional[Dict[str, Any]]:
    """
    Extract field information from a field definition call.

    Args:
        node: AST Call node representing a field definition

    Returns:
        Dictionary with field metadata
    """
    if not isinstance(node.func, ast.Attribute):
        return None

    field_type = node.func.attr
    field_info = {"type": field_type}

    # Extract positional arguments
    if node.args:
        # First arg is usually 'string' for relational fields or selection for Selection
        first_arg = _ast_node_to_python(node.args[0])
        if field_type == "Selection" and isinstance(first_arg, list):
            field_info["selection"] = first_arg
        elif isinstance(first_arg, str):
            field_info["string"] = first_arg

    # Extract keyword arguments
    for keyword in node.keywords:
        if keyword.arg:
            value = _ast_node_to_python(keyword.value)
            field_info[keyword.arg] = value

    return field_info


def _get_string_value(node: ast.AST) -> Optional[str]:
    """
    Get string value from an AST node.

    Args:
        node: AST node

    Returns:
        String value or None
    """
    value = _ast_node_to_python(node)
    return value if isinstance(value, str) else None


def _ast_node_to_python(node: ast.AST) -> Any:
    """
    Convert an AST node to a Python value.

    Handles: strings, numbers, booleans, None, lists, dicts, tuples.

    Args:
        node: AST node to convert

    Returns:
        Python value, or None if conversion not supported
    """
    # Constant (Python 3.8+)
    if isinstance(node, ast.Constant):
        return node.value

    # For Python < 3.8 compatibility
    if hasattr(ast, "Str") and isinstance(node, ast.Str):
        return node.s
    if hasattr(ast, "Num") and isinstance(node, ast.Num):
        return node.n
    if hasattr(ast, "NameConstant") and isinstance(node, ast.NameConstant):
        return node.value

    # List
    if isinstance(node, ast.List):
        return [_ast_node_to_python(elem) for elem in node.elts]

    # Tuple
    if isinstance(node, ast.Tuple):
        return tuple(_ast_node_to_python(elem) for elem in node.elts)

    # Dict
    if isinstance(node, ast.Dict):
        result = {}
        for key_node, value_node in zip(node.keys, node.values):
            if key_node is None:
                continue
            key = _ast_node_to_python(key_node)
            if isinstance(key, str):
                result[key] = _ast_node_to_python(value_node)
        return result

    # Boolean and None
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        elif node.id == "False":
            return False
        elif node.id == "None":
            return None

    # Unsupported
    logger.debug(f"Unsupported AST node type: {type(node).__name__}")
    return None
