"""
Odoo View Extraction and Indexing

This module provides functionality to parse XML files and extract Odoo view
definitions, including their metadata, inheritance relationships, and model
associations.

Author: ETL Pipeline Generator
Created: 2025-10-22
"""

import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ViewMetadata:
    """
    Metadata for an Odoo view extracted from XML.

    Attributes:
        xml_id: Full XML ID (module.view_id)
        name: View name
        model: Associated model name
        view_type: View type (form, tree, kanban, etc.)
        module: Parent Odoo module
        inherit_id: Parent view XML ID for inheritance
        priority: View priority
        mode: View mode (primary or extension)
        file_path: Source XML file path
        line_number: Line number in XML
        errors: Validation errors
    """

    xml_id: str
    name: str
    model: str
    view_type: str
    module: str
    inherit_id: Optional[str] = None
    priority: int = 16
    mode: str = "primary"
    file_path: str = ""
    line_number: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert ViewMetadata to dictionary."""
        return {
            "xml_id": self.xml_id,
            "name": self.name,
            "model": self.model,
            "view_type": self.view_type,
            "module": self.module,
            "inherit_id": self.inherit_id,
            "priority": self.priority,
            "mode": self.mode,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "errors": self.errors,
        }


class ViewIndexerError(Exception):
    """Raised when view indexing encounters a fatal error."""

    pass


class ViewIndexer:
    """
    Odoo view extraction and indexing engine.

    Parses XML files to extract view definitions and metadata.
    """

    VIEW_TYPES = {"form", "tree", "kanban", "search", "calendar", "graph", "pivot", "qweb"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self, module_name: str):
        """
        Initialize ViewIndexer.

        Args:
            module_name: Name of the Odoo module
        """
        self.module_name = module_name
        self._stats = {"total_views": 0, "errors": 0, "skipped": 0}

    def index_views(self, module_path: str) -> List[ViewMetadata]:
        """
        Index all views in the module.

        Args:
            module_path: Path to Odoo module directory

        Returns:
            List of ViewMetadata objects

        Raises:
            ViewIndexerError: If module_path is invalid
        """
        if not os.path.exists(module_path):
            raise ViewIndexerError(f"Module path does not exist: {module_path}")

        logger.info(f"Indexing views in module: {self.module_name}")

        self._stats = {"total_views": 0, "errors": 0, "skipped": 0}
        views = []

        xml_files = self._find_xml_files(module_path)
        logger.info(f"Found {len(xml_files)} XML files")

        for file_path in xml_files:
            try:
                file_views = self._parse_xml_file(file_path)
                views.extend(file_views)
                self._stats["total_views"] += len(file_views)
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"Failed to parse {file_path}: {e}")

        logger.info(
            f"Found {self._stats['total_views']} views, "
            f"{self._stats['errors']} errors"
        )

        return views

    def _find_xml_files(self, module_path: str) -> List[str]:
        """Find XML files that may contain view definitions."""
        xml_files = []

        # Search views/ directory
        views_dir = os.path.join(module_path, "views")
        if os.path.isdir(views_dir):
            for root, dirs, files in os.walk(views_dir):
                for filename in files:
                    if filename.endswith(".xml"):
                        xml_files.append(os.path.join(root, filename))

        # Search data/ directory
        data_dir = os.path.join(module_path, "data")
        if os.path.isdir(data_dir):
            for root, dirs, files in os.walk(data_dir):
                for filename in files:
                    if filename.endswith(".xml"):
                        xml_files.append(os.path.join(root, filename))

        return xml_files

    def _parse_xml_file(self, file_path: str) -> List[ViewMetadata]:
        """Parse XML file and extract view records."""
        if os.path.getsize(file_path) > self.MAX_FILE_SIZE:
            logger.warning(f"Skipping large file: {file_path}")
            return []

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            logger.error(f"XML parse error in {file_path}: {e}")
            return []

        views = []

        # Find all <record> elements with model="ir.ui.view"
        for record in root.findall(".//record[@model='ir.ui.view']"):
            try:
                view = self._extract_view(record, file_path)
                views.append(view)
            except Exception as e:
                logger.error(f"Failed to extract view from {file_path}: {e}")

        return views

    def _extract_view(self, record_elem: ET.Element, file_path: str) -> ViewMetadata:
        """Extract view metadata from <record> element."""
        errors = []

        # Extract XML ID
        xml_id = record_elem.get("id", "")
        if not xml_id:
            errors.append("Missing XML ID")

        # Build full XML ID with module prefix
        if "." not in xml_id:
            full_xml_id = f"{self.module_name}.{xml_id}"
        else:
            full_xml_id = xml_id

        # Extract fields
        fields = {}
        for field_elem in record_elem.findall("field"):
            field_name = field_elem.get("name", "")
            field_value = self._extract_field_value(field_elem)
            if field_name:
                fields[field_name] = field_value

        # Get required fields
        name = fields.get("name", "")
        model = fields.get("model", "")
        inherit_id = fields.get("inherit_id", None)

        # Detect view type from arch
        arch = fields.get("arch", "")
        view_type = self._detect_view_type(arch)

        # Determine mode
        mode = "extension" if inherit_id else "primary"

        # Validate
        if not model and not inherit_id:
            errors.append("View has neither model nor inherit_id")

        return ViewMetadata(
            xml_id=full_xml_id,
            name=name,
            model=model,
            view_type=view_type,
            module=self.module_name,
            inherit_id=inherit_id,
            priority=int(fields.get("priority", 16)),
            mode=mode,
            file_path=file_path,
            line_number=getattr(record_elem, "sourceline", 0),
            errors=errors,
        )

    def _extract_field_value(self, field_elem: ET.Element) -> str:
        """Extract field value from <field> element."""
        # Check for ref attribute
        ref = field_elem.get("ref")
        if ref:
            return ref

        # Get text content
        return field_elem.text or ""

    def _detect_view_type(self, arch: str) -> str:
        """Detect view type from architecture string."""
        arch_lower = arch.lower()

        for view_type in self.VIEW_TYPES:
            if f"<{view_type}" in arch_lower or f"<{view_type}>" in arch_lower:
                return view_type

        return "unknown"

    def get_stats(self) -> Dict[str, int]:
        """Get indexing statistics."""
        return self._stats.copy()


def index_views(module_name: str, module_path: str) -> List[ViewMetadata]:
    """
    Index all Odoo views in a module.

    Args:
        module_name: Name of the Odoo module
        module_path: Path to module directory

    Returns:
        List of ViewMetadata objects

    Example:
        >>> views = index_views("sale", "/odoo/addons/sale")
        >>> for view in views:
        ...     print(f"{view.name} ({view.view_type})")
    """
    indexer = ViewIndexer(module_name)
    return indexer.index_views(module_path)


if __name__ == "__main__":
    import sys
    import json

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 3:
        print("Usage: python index_views.py <module_name> <module_path>")
        sys.exit(1)

    module_name = sys.argv[1]
    module_path = sys.argv[2]

    try:
        views = index_views(module_name, module_path)
        output = [view.to_dict() for view in views]
        print(json.dumps(output, indent=2))
    except ViewIndexerError as e:
        logger.error(f"Failed: {e}")
        sys.exit(1)
