"""
Odoo Module Discovery and Metadata Extraction

This module provides functionality to discover and parse Odoo modules from a given
source directory. It identifies module boundaries via __manifest__.py files and
extracts structured metadata for downstream ETL processing.

Author: ETL Pipeline Generator
Created: 2025-10-22
"""

import ast
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ModuleMetadata:
    """
    Structured representation of an Odoo module's metadata.

    Attributes:
        name: Technical module name (from manifest or directory)
        path: Absolute path to the module directory
        version: Module version string
        depends: List of dependent module names
        summary: Short module description
        description: Full module description
        category: Module category
        installable: Whether the module can be installed
        auto_install: Whether the module auto-installs
        manifest_file: Name of the manifest file (__manifest__.py or __openerp__.py)
        author: Module author(s)
        license: Module license
        data: List of data files (XML, CSV)
        errors: List of parsing/validation errors encountered
    """

    name: str
    path: str
    version: str = "1.0.0"
    depends: List[str] = field(default_factory=list)
    summary: str = ""
    description: str = ""
    category: str = "Uncategorized"
    installable: bool = True
    auto_install: bool = False
    manifest_file: str = "__manifest__.py"
    author: str = ""
    license: str = ""
    data: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert ModuleMetadata to dictionary for serialization."""
        return {
            "name": self.name,
            "path": self.path,
            "version": self.version,
            "depends": self.depends,
            "summary": self.summary,
            "description": self.description,
            "category": self.category,
            "installable": self.installable,
            "auto_install": self.auto_install,
            "manifest_file": self.manifest_file,
            "author": self.author,
            "license": self.license,
            "data": self.data,
            "errors": self.errors,
        }


class ModuleDiscoveryError(Exception):
    """Raised when module discovery encounters a fatal error."""

    pass


class ModuleParser:
    """
    Odoo module discovery and metadata extraction engine.

    This class provides methods to recursively scan Odoo source directories,
    identify modules, and extract their metadata from manifest files.
    """

    # Supported manifest file names (in order of preference)
    MANIFEST_FILES = ["__manifest__.py", "__openerp__.py"]

    # Maximum manifest file size (1MB)
    MAX_MANIFEST_SIZE = 1024 * 1024

    def __init__(self, max_depth: Optional[int] = None):
        """
        Initialize the ModuleParser.

        Args:
            max_depth: Maximum directory depth for traversal (None = unlimited)
        """
        self.max_depth = max_depth
        self._stats = {"total_modules": 0, "errors": 0, "skipped": 0}

    def discover_modules(self, odoo_path: str) -> List[ModuleMetadata]:
        """
        Discover all Odoo modules in the given path.

        Args:
            odoo_path: Root directory containing Odoo modules

        Returns:
            List of ModuleMetadata objects for discovered modules

        Raises:
            ModuleDiscoveryError: If odoo_path is invalid or inaccessible
        """
        # Validate input path
        odoo_path = os.path.abspath(odoo_path)
        if not os.path.exists(odoo_path):
            raise ModuleDiscoveryError(f"Path does not exist: {odoo_path}")
        if not os.path.isdir(odoo_path):
            raise ModuleDiscoveryError(f"Path is not a directory: {odoo_path}")

        logger.info(f"Starting module discovery in: {odoo_path}")

        # Reset statistics
        self._stats = {"total_modules": 0, "errors": 0, "skipped": 0}

        modules = []

        # Walk directory tree and find manifest files
        for module_path, manifest_file in self._walk_modules(odoo_path):
            try:
                metadata = self._parse_module(module_path, manifest_file)
                modules.append(metadata)
                self._stats["total_modules"] += 1

                if metadata.errors:
                    self._stats["errors"] += len(metadata.errors)
                    logger.warning(
                        f"Module '{metadata.name}' has {len(metadata.errors)} errors"
                    )

            except Exception as e:
                self._stats["skipped"] += 1
                logger.error(f"Failed to parse module at {module_path}: {e}")
                # Continue processing other modules
                continue

        logger.info(
            f"Discovery complete. Found {self._stats['total_modules']} modules, "
            f"{self._stats['errors']} errors, {self._stats['skipped']} skipped"
        )

        return modules

    def _walk_modules(self, root_path: str) -> List[Tuple[str, str]]:
        """
        Walk directory tree and yield module paths with their manifest files.

        Args:
            root_path: Root directory to search

        Yields:
            Tuples of (module_path, manifest_file_name)
        """
        for dirpath, dirnames, filenames in os.walk(root_path, followlinks=False):
            # Check depth limit
            if self.max_depth is not None:
                depth = dirpath[len(root_path) :].count(os.sep)
                if depth >= self.max_depth:
                    dirnames.clear()  # Don't recurse deeper
                    continue

            # Check for manifest file
            manifest_file = self._find_manifest(filenames)
            if manifest_file:
                yield (dirpath, manifest_file)

                # Don't recurse into module subdirectories
                # (Odoo modules are flat, not nested)
                dirnames.clear()

    def _find_manifest(self, filenames: List[str]) -> Optional[str]:
        """
        Find the manifest file in a list of filenames.

        Args:
            filenames: List of filenames in a directory

        Returns:
            Manifest filename if found, None otherwise
        """
        for manifest_name in self.MANIFEST_FILES:
            if manifest_name in filenames:
                return manifest_name
        return None

    def _parse_module(self, module_path: str, manifest_file: str) -> ModuleMetadata:
        """
        Parse a single Odoo module and extract its metadata.

        Args:
            module_path: Absolute path to the module directory
            manifest_file: Name of the manifest file

        Returns:
            ModuleMetadata object

        Raises:
            Exception: If parsing fails critically
        """
        manifest_path = os.path.join(module_path, manifest_file)
        errors = []

        # Extract module name from directory
        module_name = os.path.basename(module_path)

        # Check manifest file size
        file_size = os.path.getsize(manifest_path)
        if file_size > self.MAX_MANIFEST_SIZE:
            errors.append(
                f"Manifest file too large: {file_size} bytes (max {self.MAX_MANIFEST_SIZE})"
            )
            logger.warning(f"Skipping oversized manifest: {manifest_path}")

        # Parse manifest file
        manifest_data = {}
        if not errors:  # Only parse if no size errors
            try:
                manifest_data = self._parse_manifest_file(manifest_path)
            except (SyntaxError, ValueError) as e:
                errors.append(f"Failed to parse manifest: {e}")
                logger.error(f"Error parsing {manifest_path}: {e}")

        # Normalize and validate metadata
        metadata = self._normalize_metadata(
            module_path, module_name, manifest_file, manifest_data, errors
        )

        return metadata

    def _parse_manifest_file(self, manifest_path: str) -> Dict:
        """
        Safely parse a manifest file using ast.literal_eval.

        Args:
            manifest_path: Path to the manifest file

        Returns:
            Dictionary of manifest data

        Raises:
            SyntaxError: If manifest has invalid Python syntax
            ValueError: If manifest doesn't evaluate to a dictionary
        """
        # Read manifest file
        with open(manifest_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse using ast.literal_eval for security
        # This prevents arbitrary code execution
        try:
            manifest_data = ast.literal_eval(content)
        except (SyntaxError, ValueError) as e:
            logger.error(f"Failed to parse manifest {manifest_path}: {e}")
            raise

        # Validate that result is a dictionary
        if not isinstance(manifest_data, dict):
            raise ValueError(f"Manifest is not a dictionary: {type(manifest_data)}")

        return manifest_data

    def _normalize_metadata(
        self,
        module_path: str,
        module_name: str,
        manifest_file: str,
        manifest_data: Dict,
        errors: List[str],
    ) -> ModuleMetadata:
        """
        Normalize raw manifest data into ModuleMetadata structure.

        Args:
            module_path: Absolute path to module directory
            module_name: Module name derived from directory
            manifest_file: Name of manifest file
            manifest_data: Raw manifest dictionary
            errors: List of errors encountered during parsing

        Returns:
            ModuleMetadata object with normalized data
        """
        # Extract name from manifest, fallback to directory name
        name = manifest_data.get("name", module_name)

        # Validate name matches directory (warn if mismatch)
        if name != module_name and manifest_data.get("name"):
            errors.append(
                f"Module name '{name}' doesn't match directory '{module_name}'"
            )
            logger.warning(
                f"Name mismatch: manifest says '{name}', directory is '{module_name}'"
            )

        # Extract and validate depends field
        depends = manifest_data.get("depends", [])
        if not isinstance(depends, list):
            errors.append(f"Invalid 'depends' field type: {type(depends)}")
            depends = []
        else:
            # Ensure all dependencies are strings
            if not all(isinstance(d, str) for d in depends):
                errors.append("Some dependencies are not strings")
                depends = [str(d) for d in depends if d]

        # Extract data files
        data_files = manifest_data.get("data", [])
        if not isinstance(data_files, list):
            errors.append(f"Invalid 'data' field type: {type(data_files)}")
            data_files = []

        # Build ModuleMetadata object
        return ModuleMetadata(
            name=name,
            path=os.path.abspath(module_path),
            version=str(manifest_data.get("version", "1.0.0")),
            depends=depends,
            summary=str(manifest_data.get("summary", "")),
            description=str(manifest_data.get("description", "")),
            category=str(manifest_data.get("category", "Uncategorized")),
            installable=bool(manifest_data.get("installable", True)),
            auto_install=bool(manifest_data.get("auto_install", False)),
            manifest_file=manifest_file,
            author=str(manifest_data.get("author", "")),
            license=str(manifest_data.get("license", "")),
            data=data_files,
            errors=errors,
        )

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics from the last discovery run.

        Returns:
            Dictionary with statistics
        """
        return self._stats.copy()


# Convenience function for simple use cases
def discover_modules(odoo_path: str, max_depth: Optional[int] = None) -> List[ModuleMetadata]:
    """
    Discover all Odoo modules in the given path.

    Convenience wrapper around ModuleParser.discover_modules().

    Args:
        odoo_path: Root directory containing Odoo modules
        max_depth: Maximum directory depth for traversal (None = unlimited)

    Returns:
        List of ModuleMetadata objects

    Raises:
        ModuleDiscoveryError: If odoo_path is invalid

    Example:
        >>> modules = discover_modules("/odoo/addons")
        >>> for module in modules:
        ...     print(f"{module.name}: {module.summary}")
    """
    parser = ModuleParser(max_depth=max_depth)
    return parser.discover_modules(odoo_path)


# CLI entry point for testing
if __name__ == "__main__":
    import sys
    import json

    # Configure logging for CLI usage
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if len(sys.argv) < 2:
        print("Usage: python parse_modules.py <odoo_path>")
        sys.exit(1)

    odoo_path = sys.argv[1]

    try:
        modules = discover_modules(odoo_path)

        # Output as JSON
        output = [module.to_dict() for module in modules]
        print(json.dumps(output, indent=2))

    except ModuleDiscoveryError as e:
        logger.error(f"Discovery failed: {e}")
        sys.exit(1)
