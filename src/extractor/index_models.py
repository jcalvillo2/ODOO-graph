"""
Odoo Model Extraction and Indexing

This module provides functionality to parse Python source files and extract Odoo
model definitions, including their metadata, inheritance relationships, and field
definitions. Uses AST-based parsing for accuracy and safety.

Author: ETL Pipeline Generator
Created: 2025-10-22
"""

import ast
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class FieldMetadata:
    """
    Metadata for a single Odoo model field.

    Attributes:
        name: Field name (Python attribute name)
        field_type: Odoo field type (Char, Integer, Many2one, etc.)
        string: Human-readable label
        required: Whether field is required
        readonly: Whether field is readonly
        comodel_name: Related model name (for relational fields)
        relation: Intermediate table (for Many2many)
    """

    name: str
    field_type: str
    string: str = ""
    required: bool = False
    readonly: bool = False
    comodel_name: Optional[str] = None
    relation: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert FieldMetadata to dictionary."""
        return {
            "name": self.name,
            "field_type": self.field_type,
            "string": self.string,
            "required": self.required,
            "readonly": self.readonly,
            "comodel_name": self.comodel_name,
            "relation": self.relation,
        }


@dataclass
class ModelMetadata:
    """
    Metadata for an Odoo model extracted from Python source.

    Attributes:
        name: Technical model name (_name attribute)
        module: Parent Odoo module name
        class_name: Python class name
        model_type: Classification (parent, child, redefined, mixin)
        inherits: List of inherited model names (_inherit)
        inherits_delegation: Delegation inheritance (_inherits)
        description: Model description (_description)
        fields: Dictionary of field definitions
        file_path: Path to source file
        line_number: Line number where class is defined
        rec_name: Field used for record name
        order: Default sort order
        table: Custom database table name
        errors: List of validation errors
    """

    name: str
    module: str
    class_name: str
    model_type: str  # parent, child, redefined, mixin
    inherits: List[str] = field(default_factory=list)
    inherits_delegation: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    fields: Dict[str, FieldMetadata] = field(default_factory=dict)
    file_path: str = ""
    line_number: int = 0
    rec_name: str = ""
    order: str = ""
    table: str = ""
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert ModelMetadata to dictionary."""
        return {
            "name": self.name,
            "module": self.module,
            "class_name": self.class_name,
            "model_type": self.model_type,
            "inherits": self.inherits,
            "inherits_delegation": self.inherits_delegation,
            "description": self.description,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "file_path": self.file_path,
            "line_number": self.line_number,
            "rec_name": self.rec_name,
            "order": self.order,
            "table": self.table,
            "errors": self.errors,
        }


class ModelIndexerError(Exception):
    """Raised when model indexing encounters a fatal error."""

    pass


class ModelIndexer:
    """
    Odoo model extraction and indexing engine.

    This class provides methods to analyze Python source files and extract
    Odoo model definitions using AST-based static analysis.
    """

    # Odoo model base classes to detect
    MODEL_BASE_CLASSES = {"Model", "TransientModel", "AbstractModel"}

    # Odoo field types
    FIELD_TYPES = {
        "Char",
        "Text",
        "Integer",
        "Float",
        "Boolean",
        "Date",
        "Datetime",
        "Selection",
        "Many2one",
        "One2many",
        "Many2many",
        "Binary",
        "Html",
        "Monetary",
        "Reference",
    }

    # Maximum Python file size (1MB)
    MAX_FILE_SIZE = 1024 * 1024

    def __init__(self, module_name: str):
        """
        Initialize the ModelIndexer.

        Args:
            module_name: Name of the Odoo module being indexed
        """
        self.module_name = module_name
        self._stats = {"total_models": 0, "total_fields": 0, "errors": 0}

    def index_models(self, module_path: str) -> List[ModelMetadata]:
        """
        Index all models in the given module path.

        Args:
            module_path: Path to Odoo module directory

        Returns:
            List of ModelMetadata objects

        Raises:
            ModelIndexerError: If module_path is invalid
        """
        # Validate module path
        if not os.path.exists(module_path):
            raise ModelIndexerError(f"Module path does not exist: {module_path}")
        if not os.path.isdir(module_path):
            raise ModelIndexerError(f"Module path is not a directory: {module_path}")

        logger.info(f"Indexing models in module: {self.module_name}")

        # Reset statistics
        self._stats = {"total_models": 0, "total_fields": 0, "errors": 0}

        models = []

        # Find Python files
        python_files = self._find_python_files(module_path)
        logger.info(f"Found {len(python_files)} Python files to analyze")

        # Parse each file
        for file_path in python_files:
            try:
                file_models = self._parse_file(file_path)
                models.extend(file_models)
                self._stats["total_models"] += len(file_models)
                for model in file_models:
                    self._stats["total_fields"] += len(model.fields)

            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"Failed to parse file {file_path}: {e}")
                continue

        logger.info(
            f"Indexing complete. Found {self._stats['total_models']} models, "
            f"{self._stats['total_fields']} fields, {self._stats['errors']} errors"
        )

        return models

    def _find_python_files(self, module_path: str) -> List[str]:
        """
        Find all Python files in the module that may contain models.

        Args:
            module_path: Path to module directory

        Returns:
            List of absolute file paths
        """
        python_files = []

        # Priority 1: models/ directory
        models_dir = os.path.join(module_path, "models")
        if os.path.isdir(models_dir):
            for root, dirs, files in os.walk(models_dir):
                for filename in files:
                    if filename.endswith(".py") and not filename.startswith("test_"):
                        python_files.append(os.path.join(root, filename))

        # Priority 2: Root directory Python files (legacy modules)
        for filename in os.listdir(module_path):
            file_path = os.path.join(module_path, filename)
            if (
                os.path.isfile(file_path)
                and filename.endswith(".py")
                and not filename.startswith("test_")
                and filename not in ["__init__.py", "__manifest__.py", "__openerp__.py"]
            ):
                python_files.append(file_path)

        return python_files

    def _parse_file(self, file_path: str) -> List[ModelMetadata]:
        """
        Parse a Python file and extract model definitions.

        Args:
            file_path: Path to Python file

        Returns:
            List of ModelMetadata objects found in file
        """
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > self.MAX_FILE_SIZE:
            logger.warning(f"Skipping large file: {file_path} ({file_size} bytes)")
            return []

        # Read file content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
        except UnicodeDecodeError as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return []

        # Parse to AST
        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            return []

        # Extract models from AST
        models = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if self._is_model_class(node):
                    try:
                        model = self._extract_model(node, file_path)
                        models.append(model)
                    except Exception as e:
                        logger.error(f"Failed to extract model {node.name} from {file_path}: {e}")
                        continue

        return models

    def _is_model_class(self, class_node: ast.ClassDef) -> bool:
        """
        Check if a class definition is an Odoo model.

        Args:
            class_node: AST ClassDef node

        Returns:
            True if class inherits from Odoo model base class
        """
        for base in class_node.bases:
            # Handle models.Model pattern
            if isinstance(base, ast.Attribute):
                if base.attr in self.MODEL_BASE_CLASSES:
                    return True
            # Handle direct Model inheritance (rare)
            elif isinstance(base, ast.Name):
                if base.id in self.MODEL_BASE_CLASSES:
                    return True

        return False

    def _extract_model(self, class_node: ast.ClassDef, file_path: str) -> ModelMetadata:
        """
        Extract model metadata from a class definition.

        Args:
            class_node: AST ClassDef node
            file_path: Path to source file

        Returns:
            ModelMetadata object
        """
        errors = []

        # Extract model attributes
        attributes = self._extract_attributes(class_node)

        # Get _name and _inherit
        model_name = attributes.get("_name", "")
        inherit = attributes.get("_inherit", [])

        # Normalize _inherit to list
        if isinstance(inherit, str):
            inherit = [inherit]
        elif not isinstance(inherit, list):
            inherit = []

        # Classify model type
        model_type = self._classify_model(model_name, inherit)

        # Validate model
        if model_type == "parent" and not model_name:
            errors.append("Parent model missing _name attribute")
        if model_type == "child" and not inherit:
            errors.append("Child model missing _inherit attribute")

        # Extract fields
        fields = self._extract_fields(class_node)

        # Build ModelMetadata
        model = ModelMetadata(
            name=model_name or class_node.name,
            module=self.module_name,
            class_name=class_node.name,
            model_type=model_type,
            inherits=inherit,
            inherits_delegation=attributes.get("_inherits", {}),
            description=attributes.get("_description", ""),
            fields=fields,
            file_path=file_path,
            line_number=getattr(class_node, "lineno", 0),
            rec_name=attributes.get("_rec_name", ""),
            order=attributes.get("_order", ""),
            table=attributes.get("_table", ""),
            errors=errors,
        )

        return model

    def _extract_attributes(self, class_node: ast.ClassDef) -> Dict:
        """
        Extract model attributes (_name, _inherit, etc.) from class body.

        Args:
            class_node: AST ClassDef node

        Returns:
            Dictionary of attribute name -> value
        """
        attributes = {}

        for stmt in class_node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id

                        # Only extract Odoo model attributes
                        if attr_name.startswith("_"):
                            value = self._extract_value(stmt.value)
                            if value is not None:
                                attributes[attr_name] = value

        return attributes

    def _extract_value(self, node: ast.AST) -> Optional[Union[str, List, Dict]]:
        """
        Extract value from AST node (for string literals, lists, dicts).

        Args:
            node: AST node

        Returns:
            Extracted value or None if not extractable
        """
        # String literal
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value

        # List
        if isinstance(node, ast.List):
            return [self._extract_value(elt) for elt in node.elts if self._extract_value(elt)]

        # Dict
        if isinstance(node, ast.Dict):
            result = {}
            for key, value in zip(node.keys, node.values):
                k = self._extract_value(key)
                v = self._extract_value(value)
                if k and v:
                    result[k] = v
            return result

        # Legacy string (Python 2 compatibility)
        if isinstance(node, ast.Str):
            return node.s

        return None

    def _classify_model(self, name: str, inherit: List[str]) -> str:
        """
        Classify model based on _name and _inherit attributes.

        Args:
            name: _name attribute value
            inherit: _inherit attribute value(s)

        Returns:
            Model type: "parent", "child", "redefined", or "mixin"
        """
        has_name = bool(name)
        has_inherit = bool(inherit)

        if has_name and not has_inherit:
            return "parent"
        elif not has_name and has_inherit:
            return "child"
        elif has_name and has_inherit:
            return "redefined"
        else:
            return "mixin"

    def _extract_fields(self, class_node: ast.ClassDef) -> Dict[str, FieldMetadata]:
        """
        Extract field definitions from class body.

        Args:
            class_node: AST ClassDef node

        Returns:
            Dictionary of field_name -> FieldMetadata
        """
        fields = {}

        for stmt in class_node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        # Check if assignment is a field definition
                        if isinstance(stmt.value, ast.Call):
                            field_type = self._extract_field_type(stmt.value)
                            if field_type:
                                # Create FieldMetadata
                                fields[field_name] = FieldMetadata(
                                    name=field_name, field_type=field_type
                                )

        return fields

    def _extract_field_type(self, call_node: ast.Call) -> Optional[str]:
        """
        Extract Odoo field type from a call node (e.g., fields.Char(...)).

        Args:
            call_node: AST Call node

        Returns:
            Field type string or None if not a field
        """
        # Pattern: fields.FieldType(...)
        if isinstance(call_node.func, ast.Attribute):
            field_type = call_node.func.attr
            if field_type in self.FIELD_TYPES:
                return field_type

        return None

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics from the last indexing run.

        Returns:
            Dictionary with statistics
        """
        return self._stats.copy()


# Convenience function
def index_models(module_name: str, module_path: str) -> List[ModelMetadata]:
    """
    Index all Odoo models in a module.

    Args:
        module_name: Name of the Odoo module
        module_path: Path to module directory

    Returns:
        List of ModelMetadata objects

    Raises:
        ModelIndexerError: If indexing fails

    Example:
        >>> models = index_models("sale", "/odoo/addons/sale")
        >>> for model in models:
        ...     print(f"{model.name} ({model.model_type}): {len(model.fields)} fields")
    """
    indexer = ModelIndexer(module_name)
    return indexer.index_models(module_path)


# CLI entry point
if __name__ == "__main__":
    import sys
    import json

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if len(sys.argv) < 3:
        print("Usage: python index_models.py <module_name> <module_path>")
        sys.exit(1)

    module_name = sys.argv[1]
    module_path = sys.argv[2]

    try:
        models = index_models(module_name, module_path)

        # Output as JSON
        output = [model.to_dict() for model in models]
        print(json.dumps(output, indent=2))

    except ModelIndexerError as e:
        logger.error(f"Indexing failed: {e}")
        sys.exit(1)
