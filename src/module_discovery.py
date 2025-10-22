"""
Module Discovery Service for Odoo ETL Pipeline.

This module provides high-level functions to discover and parse Odoo modules
from a given source path, extracting metadata and dependencies as required
by the ETL pipeline.

Example:
    >>> from parsers.module_discovery import discover_modules
    >>> modules = discover_modules("/odoo/addons")
    >>> for module in modules:
    ...     print(f"{module['name']}: {module['depends']}")
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .manifest_parser import (
    find_modules,
    parse_manifest,
    get_manifest_dependencies,
    is_module_installable,
)

logger = logging.getLogger(__name__)


class ModuleDiscovery:
    """
    Service for discovering and parsing Odoo modules.

    This class provides a high-level interface for module discovery,
    handling the traversal of directory trees, manifest parsing, and
    building structured representations of modules and their dependencies.

    Attributes:
        root_path: Root directory containing Odoo modules
        max_depth: Maximum depth for directory traversal
        include_uninstallable: Whether to include uninstallable modules

    Example:
        >>> discovery = ModuleDiscovery("/odoo/addons")
        >>> modules = discovery.discover_all()
        >>> print(f"Found {len(modules)} modules")
    """

    def __init__(
        self,
        root_path: str | Path,
        max_depth: int = 3,
        include_uninstallable: bool = False,
    ):
        """
        Initialize the module discovery service.

        Args:
            root_path: Root directory to search for Odoo modules
            max_depth: Maximum directory depth to search (default: 3)
            include_uninstallable: Include modules marked as not installable (default: False)

        Raises:
            ValueError: If root_path does not exist or is not a directory
        """
        self.root_path = Path(root_path)
        self.max_depth = max_depth
        self.include_uninstallable = include_uninstallable

        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {root_path}")

        if not self.root_path.is_dir():
            raise ValueError(f"Path is not a directory: {root_path}")

    def discover_all(self) -> List[Dict[str, Any]]:
        """
        Discover all Odoo modules in the configured root path.

        This method traverses the directory tree, identifies modules by their
        __manifest__.py files, parses metadata, and returns a structured list
        of module information.

        Returns:
            List of dictionaries containing module metadata. Each dictionary includes:
            - module_name: Technical name (directory name)
            - name: Human-readable name from manifest
            - version: Module version
            - depends: List of dependency module names
            - summary: Short description
            - description: Full description
            - author: Module author(s)
            - category: Module category
            - installable: Whether module is installable
            - module_path: Absolute path to module directory
            - And other fields from __manifest__.py

        Example:
            >>> discovery = ModuleDiscovery("/odoo/addons")
            >>> modules = discovery.discover_all()
            >>> sale_module = next(m for m in modules if m['module_name'] == 'sale')
            >>> print(sale_module['depends'])
            ['base', 'product']
        """
        modules = []

        logger.info(f"Starting module discovery in: {self.root_path}")

        # Find all module directories
        module_paths = find_modules(self.root_path, max_depth=self.max_depth)

        for module_path in module_paths:
            try:
                module_info = self._parse_module(module_path)

                if module_info is None:
                    continue

                # Filter based on installable flag
                if not self.include_uninstallable and not module_info.get("installable", True):
                    logger.debug(f"Skipping uninstallable module: {module_path.name}")
                    continue

                modules.append(module_info)
                logger.debug(f"Discovered module: {module_info['module_name']}")

            except Exception as e:
                logger.error(f"Error processing module {module_path}: {e}", exc_info=True)
                continue

        logger.info(f"Discovery complete. Found {len(modules)} modules")
        return modules

    def _parse_module(self, module_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse a single module and extract metadata.

        Args:
            module_path: Path to module directory

        Returns:
            Dictionary with module metadata, or None if parsing failed
        """
        manifest_data = parse_manifest(module_path)

        if manifest_data is None:
            logger.warning(f"Could not parse manifest for: {module_path}")
            return None

        # Ensure required fields are present
        if "module_name" not in manifest_data:
            manifest_data["module_name"] = module_path.name

        # Normalize dependencies
        manifest_data["depends"] = get_manifest_dependencies(manifest_data)

        # Add installable flag
        manifest_data["installable"] = is_module_installable(manifest_data)

        # Ensure path is absolute
        manifest_data["module_path"] = str(module_path.resolve())

        return manifest_data

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """
        Build a dependency graph of all discovered modules.

        Returns:
            Dictionary mapping module names to their dependencies.

        Example:
            >>> discovery = ModuleDiscovery("/odoo/addons")
            >>> graph = discovery.get_dependency_graph()
            >>> print(graph["sale"])
            ['base', 'product']
        """
        modules = self.discover_all()

        graph = {}
        for module in modules:
            module_name = module.get("module_name", module.get("name"))
            depends = module.get("depends", [])
            graph[module_name] = depends

        return graph

    def find_module_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find a specific module by its technical name.

        Args:
            name: Technical module name (directory name)

        Returns:
            Module metadata dictionary, or None if not found

        Example:
            >>> discovery = ModuleDiscovery("/odoo/addons")
            >>> sale = discovery.find_module_by_name("sale")
            >>> print(sale["name"])
            'Sales'
        """
        modules = self.discover_all()

        for module in modules:
            if module.get("module_name") == name:
                return module

        return None


def discover_modules(
    path: str | Path,
    max_depth: int = 3,
    include_uninstallable: bool = False,
) -> List[Dict[str, Any]]:
    """
    Convenience function to discover Odoo modules.

    This is the primary entry point for the module discovery functionality
    as described in Story 001.

    Args:
        path: Root directory containing Odoo modules (e.g., "/odoo/addons")
        max_depth: Maximum directory depth to search (default: 3)
        include_uninstallable: Include modules marked as not installable (default: False)

    Returns:
        List of dictionaries with module metadata. Each dictionary includes:
        - module_name: Technical name
        - name: Display name
        - depends: List of dependencies
        - version: Module version
        - And other manifest fields

    Example:
        >>> modules = discover_modules("/odoo/addons")
        >>> for module in modules:
        ...     print(f"{module['module_name']}: {module['depends']}")
        sale: ['base', 'product']
        crm: ['base']

    Raises:
        ValueError: If path does not exist or is not a directory
    """
    discovery = ModuleDiscovery(
        root_path=path,
        max_depth=max_depth,
        include_uninstallable=include_uninstallable,
    )

    return discovery.discover_all()


def build_dependency_graph(
    path: str | Path,
    max_depth: int = 3,
) -> Dict[str, List[str]]:
    """
    Build a dependency graph from discovered modules.

    Args:
        path: Root directory containing Odoo modules
        max_depth: Maximum directory depth to search (default: 3)

    Returns:
        Dictionary mapping module names to their dependencies

    Example:
        >>> graph = build_dependency_graph("/odoo/addons")
        >>> print(graph["sale"])
        ['base', 'product']
    """
    discovery = ModuleDiscovery(root_path=path, max_depth=max_depth)
    return discovery.get_dependency_graph()
