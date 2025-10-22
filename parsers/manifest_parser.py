"""
Manifest parser for Odoo modules.

This module provides functions to discover Odoo modules and parse
their __manifest__.py or __openerp__.py files using AST.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

logger = logging.getLogger(__name__)

# Possible manifest file names (in order of preference)
MANIFEST_FILES = ["__manifest__.py", "__openerp__.py"]


def find_modules(
    directory: Path,
    max_depth: int = 3,
) -> Generator[Path, None, None]:
    """
    Discover Odoo modules in a directory tree.

    A directory is considered an Odoo module if it contains
    a __manifest__.py or __openerp__.py file.

    Args:
        directory: Root directory to search
        max_depth: Maximum depth to search (default: 3)

    Yields:
        Path objects pointing to module directories

    Example:
        >>> for module_path in find_modules(Path("/odoo/addons")):
        ...     print(module_path.name)
    """
    if not directory.exists():
        logger.error(f"Directory does not exist: {directory}")
        return

    if not directory.is_dir():
        logger.error(f"Path is not a directory: {directory}")
        return

    try:
        yield from _find_modules_recursive(directory, current_depth=0, max_depth=max_depth)
    except PermissionError as e:
        logger.warning(f"Permission denied accessing directory {directory}: {e}")


def _find_modules_recursive(
    directory: Path,
    current_depth: int,
    max_depth: int,
) -> Generator[Path, None, None]:
    """
    Recursive helper for find_modules.

    Args:
        directory: Current directory to search
        current_depth: Current recursion depth
        max_depth: Maximum depth to search

    Yields:
        Path objects pointing to module directories
    """
    if current_depth > max_depth:
        return

    try:
        # Check if current directory is a module
        for manifest_file in MANIFEST_FILES:
            manifest_path = directory / manifest_file
            if manifest_path.exists() and manifest_path.is_file():
                logger.debug(f"Found module: {directory}")
                yield directory
                # Don't recurse into modules (they might contain submodules)
                return

        # Recurse into subdirectories
        for item in directory.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                yield from _find_modules_recursive(
                    item,
                    current_depth + 1,
                    max_depth,
                )

    except PermissionError as e:
        logger.warning(f"Permission denied accessing {directory}: {e}")
    except OSError as e:
        logger.warning(f"OS error accessing {directory}: {e}")


def parse_manifest(module_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse Odoo module manifest file.

    Reads __manifest__.py or __openerp__.py and extracts module metadata
    using AST parsing (no code execution).

    Args:
        module_path: Path to module directory

    Returns:
        Dictionary with module metadata, or None if parsing failed

    Example:
        >>> manifest = parse_manifest(Path("/odoo/addons/sale"))
        >>> print(manifest["name"])
        'Sales'
        >>> print(manifest["depends"])
        ['base', 'product']
    """
    if not module_path.is_dir():
        logger.error(f"Not a directory: {module_path}")
        return None

    # Find manifest file
    manifest_file = None
    for filename in MANIFEST_FILES:
        candidate = module_path / filename
        if candidate.exists():
            manifest_file = candidate
            break

    if not manifest_file:
        logger.warning(f"No manifest file found in {module_path}")
        return None

    # Parse manifest file
    try:
        manifest_data = _parse_manifest_file(manifest_file)
        if manifest_data is None:
            return None

        # Add module path to metadata
        manifest_data["module_path"] = str(module_path)
        manifest_data["module_name"] = module_path.name

        return manifest_data

    except Exception as e:
        logger.error(f"Unexpected error parsing {manifest_file}: {e}", exc_info=True)
        return None


def _parse_manifest_file(manifest_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse a single manifest file using AST.

    Args:
        manifest_path: Path to __manifest__.py or __openerp__.py

    Returns:
        Dictionary with manifest data, or None if parsing failed
    """
    # Try different encodings
    encodings = ["utf-8", "latin-1", "iso-8859-1"]

    for encoding in encodings:
        try:
            content = manifest_path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Error reading {manifest_path}: {e}")
            return None
    else:
        logger.error(f"Could not decode {manifest_path} with any encoding")
        return None

    # Parse with AST
    try:
        tree = ast.parse(content, filename=str(manifest_path))
    except SyntaxError as e:
        logger.warning(f"Syntax error in {manifest_path}: {e}")
        return None

    # Extract the manifest dictionary
    # Odoo manifests are typically: { 'key': 'value', ... }
    # We need to find the dictionary assignment or expression
    manifest_dict = _extract_manifest_dict(tree)

    if manifest_dict is None:
        logger.warning(f"Could not extract manifest dict from {manifest_path}")
        return None

    return manifest_dict


def _extract_manifest_dict(tree: ast.Module) -> Optional[Dict[str, Any]]:
    """
    Extract the manifest dictionary from AST.

    The manifest can be:
    1. A direct dict expression: { 'name': 'My Module', ... }
    2. An assignment: manifest = { ... }

    Args:
        tree: Parsed AST tree

    Returns:
        Dictionary with manifest data, or None if not found
    """
    for node in tree.body:
        # Case 1: Direct expression (just a dict)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Dict):
            return _ast_dict_to_python(node.value)

        # Case 2: Assignment like: manifest = {...} or __manifest__ = {...}
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if isinstance(node.value, ast.Dict):
                        return _ast_dict_to_python(node.value)

    return None


def _ast_dict_to_python(node: ast.Dict) -> Dict[str, Any]:
    """
    Convert AST Dict node to Python dictionary.

    Args:
        node: AST Dict node

    Returns:
        Python dictionary with converted values
    """
    result = {}

    for key_node, value_node in zip(node.keys, node.values):
        # Extract key (usually a string)
        if key_node is None:
            continue

        key = _ast_node_to_python(key_node)
        if not isinstance(key, str):
            continue

        # Extract value
        value = _ast_node_to_python(value_node)
        result[key] = value

    return result


def _ast_node_to_python(node: ast.AST) -> Any:
    """
    Convert an AST node to a Python value.

    Handles: strings, numbers, booleans, None, lists, dicts.

    Args:
        node: AST node to convert

    Returns:
        Python value, or None if conversion not supported
    """
    # String (Constant in Python 3.8+, Str in older versions)
    if isinstance(node, ast.Constant):
        return node.value

    # For Python < 3.8 compatibility (deprecated but still supported)
    # These checks will be removed in future versions
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
        return _ast_dict_to_python(node)

    # Boolean and None (NameConstant in older Python)
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        elif node.id == "False":
            return False
        elif node.id == "None":
            return None

    # Unsupported node type
    logger.debug(f"Unsupported AST node type: {type(node).__name__}")
    return None


def get_manifest_dependencies(manifest_data: Dict[str, Any]) -> List[str]:
    """
    Extract dependencies from manifest data.

    Args:
        manifest_data: Parsed manifest dictionary

    Returns:
        List of module dependencies (empty list if none)
    """
    depends = manifest_data.get("depends", [])

    if not isinstance(depends, list):
        logger.warning(f"'depends' is not a list: {depends}")
        return []

    # Filter out non-string dependencies
    return [dep for dep in depends if isinstance(dep, str)]


def is_module_installable(manifest_data: Dict[str, Any]) -> bool:
    """
    Check if a module is marked as installable.

    Args:
        manifest_data: Parsed manifest dictionary

    Returns:
        True if installable (default), False otherwise
    """
    installable = manifest_data.get("installable", True)
    return bool(installable)
