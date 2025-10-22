"""
Main indexing orchestrator for Odoo dependency tracker.

This module coordinates the entire ETL process:
1. Extract: Parse Odoo modules, models, and fields
2. Transform: Prepare data for graph insertion
3. Load: Insert into Neo4j in batches
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
import time

from utils.logger import get_logger
from utils.monitoring import MemoryMonitor
from utils.hashing import compute_file_hash
from config.settings import get_settings

from parsers.manifest_parser import find_modules, parse_manifest, get_manifest_dependencies
from parsers.model_parser import find_model_files, parse_model_file

from graph.connection import Neo4jConnection
from graph.schema import initialize_schema, verify_schema, get_database_stats
from graph.batch_operations import (
    create_modules_batch,
    create_module_dependencies_batch,
    create_models_batch,
    create_model_module_relationships_batch,
    create_model_inheritance_batch,
    create_model_delegation_batch,
    create_fields_batch,
    create_field_model_relationships_batch,
    create_field_references_batch,
    process_in_batches
)

logger = get_logger(__name__)


class OdooIndexer:
    """
    Main orchestrator for indexing Odoo codebase into Neo4j.
    """

    def __init__(
        self,
        odoo_path: Path,
        connection: Neo4jConnection,
        batch_size: Optional[int] = None,
        max_memory_percent: Optional[float] = None
    ):
        """
        Initialize the indexer.

        Args:
            odoo_path: Path to Odoo addons directory
            connection: Neo4jConnection instance
            batch_size: Batch size for database operations (default from settings)
            max_memory_percent: Maximum memory usage percent (default from settings)
        """
        self.odoo_path = Path(odoo_path)
        self.connection = connection
        self.settings = get_settings()

        self.batch_size = batch_size or self.settings.batch_size
        self.max_memory_percent = max_memory_percent or self.settings.max_memory_percent

        self.memory_monitor = MemoryMonitor(
            max_percent=self.max_memory_percent
        )

        self.stats = {
            "modules_found": 0,
            "modules_indexed": 0,
            "models_found": 0,
            "models_indexed": 0,
            "fields_found": 0,
            "fields_indexed": 0,
            "relationships_created": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
            "duration_seconds": 0
        }

    def index_all(self, clear_existing: bool = False, incremental: bool = False) -> Dict[str, Any]:
        """
        Index all Odoo modules, models, and fields.

        Args:
            clear_existing: If True, clear database before indexing
            incremental: If True, only index changed files (based on hash)

        Returns:
            Dictionary with indexing statistics
        """
        logger.info("=" * 80)
        logger.info("Starting Odoo indexing process")
        logger.info(f"Path: {self.odoo_path}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Max memory: {self.max_memory_percent}%")
        logger.info(f"Clear existing: {clear_existing}")
        logger.info(f"Incremental: {incremental}")
        logger.info("=" * 80)

        self.stats["start_time"] = time.time()

        try:
            # Step 1: Clear database if requested
            if clear_existing:
                logger.info("Clearing existing database...")
                self.connection.clear_database()

            # Step 2: Initialize schema
            logger.info("Initializing schema...")
            schema_result = initialize_schema(self.connection)
            logger.info(f"Schema initialized: {schema_result}")

            # Step 3: Extract data
            logger.info("Extracting data from Odoo codebase...")
            extracted_data = self._extract_all_data(incremental)

            # Step 4: Load into Neo4j
            logger.info("Loading data into Neo4j...")
            self._load_all_data(extracted_data)

            # Step 5: Get final statistics
            self.stats["end_time"] = time.time()
            self.stats["duration_seconds"] = self.stats["end_time"] - self.stats["start_time"]

            db_stats = get_database_stats(self.connection)
            self.stats["db_stats"] = db_stats

            logger.info("=" * 80)
            logger.info("Indexing completed successfully!")
            logger.info(f"Duration: {self.stats['duration_seconds']:.2f} seconds")
            logger.info(f"Modules indexed: {self.stats['modules_indexed']}")
            logger.info(f"Models indexed: {self.stats['models_indexed']}")
            logger.info(f"Fields indexed: {self.stats['fields_indexed']}")
            logger.info(f"Relationships created: {self.stats['relationships_created']}")
            logger.info(f"Errors: {self.stats['errors']}")
            logger.info("=" * 80)

            return self.stats

        except Exception as e:
            logger.error(f"Indexing failed: {str(e)}", exc_info=True)
            self.stats["errors"] += 1
            raise

    def _extract_all_data(self, incremental: bool) -> Dict[str, Any]:
        """
        Extract all data from Odoo codebase.

        Args:
            incremental: If True, check file hashes to skip unchanged files

        Returns:
            Dictionary with extracted data
        """
        data = {
            "modules": [],
            "module_dependencies": [],
            "models": [],
            "model_module_rels": [],
            "model_inheritance": [],
            "model_delegation": [],
            "fields": [],
            "field_model_rels": [],
            "field_references": []
        }

        # Get existing hashes for incremental indexing
        existing_hashes = {}
        if incremental:
            existing_hashes = self._get_existing_file_hashes()
            logger.info(f"Found {len(existing_hashes)} existing file hashes")

        # Find all modules
        logger.info("Discovering modules...")
        module_paths = list(find_modules(self.odoo_path))
        self.stats["modules_found"] = len(module_paths)
        logger.info(f"Found {len(module_paths)} modules")

        # Process each module
        for idx, module_path in enumerate(module_paths, 1):
            try:
                self._check_memory()

                logger.debug(f"Processing module {idx}/{len(module_paths)}: {module_path.name}")

                # Extract module data
                module_data = self._extract_module_data(module_path, existing_hashes)

                if module_data:
                    data["modules"].append(module_data["module"])
                    data["module_dependencies"].extend(module_data["dependencies"])
                    data["models"].extend(module_data["models"])
                    data["model_module_rels"].extend(module_data["model_module_rels"])
                    data["model_inheritance"].extend(module_data["model_inheritance"])
                    data["model_delegation"].extend(module_data["model_delegation"])
                    data["fields"].extend(module_data["fields"])
                    data["field_model_rels"].extend(module_data["field_model_rels"])
                    data["field_references"].extend(module_data["field_references"])

                    self.stats["modules_indexed"] += 1

            except Exception as e:
                logger.error(f"Failed to process module {module_path}: {str(e)}")
                self.stats["errors"] += 1

        logger.info(f"Extraction complete: {self.stats['modules_indexed']} modules processed")
        logger.info(f"Extracted {len(data['models'])} models and {len(data['fields'])} fields")

        return data

    def _extract_module_data(
        self,
        module_path: Path,
        existing_hashes: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract all data from a single module.

        Args:
            module_path: Path to module directory
            existing_hashes: Dictionary of existing file hashes

        Returns:
            Dictionary with module data or None if skipped
        """
        data = {
            "module": None,
            "dependencies": [],
            "models": [],
            "model_module_rels": [],
            "model_inheritance": [],
            "model_delegation": [],
            "fields": [],
            "field_model_rels": [],
            "field_references": []
        }

        # Parse manifest
        manifest_path = module_path / "__manifest__.py"
        if not manifest_path.exists():
            logger.warning(f"No manifest found for {module_path.name}")
            return None

        # Check if manifest has changed
        manifest_hash = compute_file_hash(manifest_path)
        if existing_hashes.get(str(manifest_path)) == manifest_hash:
            logger.debug(f"Skipping unchanged module: {module_path.name}")
            return None

        manifest = parse_manifest(module_path)
        if not manifest:
            logger.warning(f"Failed to parse manifest for {module_path.name}")
            return None

        # Use technical module name (directory name) as unique identifier
        # Store display name separately
        technical_name = manifest.get("module_name", module_path.name)  # From manifest parser
        display_name = manifest.get("name", technical_name)  # Human-readable name

        data["module"] = {
            "name": technical_name,
            "display_name": display_name,
            "version": manifest.get("version", ""),
            "category": manifest.get("category", ""),
            "summary": manifest.get("summary", ""),
            "description": manifest.get("description", ""),
            "author": manifest.get("author", ""),
            "website": manifest.get("website", ""),
            "license": manifest.get("license", ""),
            "installable": manifest.get("installable", True),
            "auto_install": manifest.get("auto_install", False),
            "application": manifest.get("application", False),
            "file_path": str(manifest_path),
            "file_hash": manifest_hash
        }

        # Create dependency relationships (use technical names)
        dependencies = get_manifest_dependencies(manifest)
        for dep in dependencies:
            data["dependencies"].append({
                "from": technical_name,
                "to": dep
            })

        # Parse models
        model_files = list(find_model_files(module_path))
        logger.debug(f"Found {len(model_files)} model files in {technical_name}")

        for model_file in model_files:
            try:
                # Check if model file has changed
                model_hash = compute_file_hash(model_file)
                if existing_hashes.get(str(model_file)) == model_hash:
                    logger.debug(f"Skipping unchanged model file: {model_file.name}")
                    continue

                models = parse_model_file(model_file, technical_name)

                for model in models:
                    model_name = model.get("name")
                    if not model_name:
                        logger.warning(f"Model without name in {model_file}")
                        continue

                    # Create model node data
                    data["models"].append({
                        "name": model_name,
                        "description": model.get("description", ""),
                        "module": technical_name,
                        "file_path": str(model_file),
                        "line_number": model.get("line_number", 0),
                        "class_name": model.get("class_name", ""),
                        "file_hash": model_hash
                    })

                    self.stats["models_found"] += 1
                    self.stats["models_indexed"] += 1

                    # Create DEFINED_IN relationship
                    data["model_module_rels"].append({
                        "model": model_name,
                        "module": technical_name
                    })

                    # Create INHERITS_FROM relationships
                    inherit = model.get("inherit", [])
                    if inherit:
                        for parent in inherit:
                            data["model_inheritance"].append({
                                "from": model_name,
                                "to": parent
                            })

                    # Create DELEGATES_TO relationships
                    inherits = model.get("inherits", {})
                    if inherits:
                        for parent_model, field_name in inherits.items():
                            data["model_delegation"].append({
                                "from": model_name,
                                "to": parent_model,
                                "field": field_name
                            })

                    # Process fields
                    fields = model.get("fields", [])
                    for field in fields:
                        # Skip if field is not a dictionary
                        if not isinstance(field, dict):
                            logger.warning(f"Skipping invalid field in {model_name}: {field}")
                            continue

                        field_name = field.get("name")
                        if not field_name:
                            continue

                        # Create field node data with all parameters
                        field_data = {
                            "name": field_name,
                            "model_name": model_name,
                            "field_type": field.get("type", ""),
                            "string": field.get("string"),
                            "required": field.get("required"),
                            "readonly": field.get("readonly"),
                            "help": field.get("help"),
                            "default": field.get("default"),
                            "compute": field.get("compute"),
                            "store": field.get("store"),
                            "related": field.get("related"),
                            "depends": field.get("depends"),
                            "inverse_name": field.get("inverse_name"),
                            "comodel_name": field.get("comodel_name"),
                            "domain": field.get("domain"),
                            "selection": field.get("selection"),
                            "states": field.get("states"),
                            "copy": field.get("copy"),
                            "index": field.get("index"),
                            "translate": field.get("translate"),
                            "digits": field.get("digits"),
                            "sanitize": field.get("sanitize"),
                            "strip_style": field.get("strip_style")
                        }

                        data["fields"].append(field_data)
                        self.stats["fields_found"] += 1
                        self.stats["fields_indexed"] += 1

                        # Create BELONGS_TO relationship
                        data["field_model_rels"].append({
                            "field_name": field_name,
                            "model_name": model_name
                        })

                        # Create REFERENCES relationship for relational fields
                        comodel = field.get("comodel_name")
                        if comodel:
                            data["field_references"].append({
                                "field_name": field_name,
                                "model_name": model_name,
                                "comodel": comodel
                            })

            except Exception as e:
                logger.error(f"Failed to parse model file {model_file}: {str(e)}")
                self.stats["errors"] += 1

        return data

    def _load_all_data(self, data: Dict[str, Any]) -> None:
        """
        Load all extracted data into Neo4j.

        Args:
            data: Dictionary with extracted data
        """
        # Load modules
        logger.info(f"Loading {len(data['modules'])} modules...")
        result = process_in_batches(
            self.connection,
            data["modules"],
            self.batch_size,
            create_modules_batch,
            "modules"
        )
        self.stats["relationships_created"] += result["created"]

        # Load module dependencies
        logger.info(f"Loading {len(data['module_dependencies'])} module dependencies...")
        result = process_in_batches(
            self.connection,
            data["module_dependencies"],
            self.batch_size,
            create_module_dependencies_batch,
            "module dependencies"
        )
        self.stats["relationships_created"] += result["created"]

        # Load models
        logger.info(f"Loading {len(data['models'])} models...")
        result = process_in_batches(
            self.connection,
            data["models"],
            self.batch_size,
            create_models_batch,
            "models"
        )
        self.stats["relationships_created"] += result["created"]

        # Load model-module relationships
        logger.info(f"Loading {len(data['model_module_rels'])} model-module relationships...")
        result = process_in_batches(
            self.connection,
            data["model_module_rels"],
            self.batch_size,
            create_model_module_relationships_batch,
            "model-module relationships"
        )
        self.stats["relationships_created"] += result["created"]

        # Load model inheritance
        logger.info(f"Loading {len(data['model_inheritance'])} model inheritance relationships...")
        result = process_in_batches(
            self.connection,
            data["model_inheritance"],
            self.batch_size,
            create_model_inheritance_batch,
            "model inheritance"
        )
        self.stats["relationships_created"] += result["created"]

        # Load model delegation
        logger.info(f"Loading {len(data['model_delegation'])} model delegation relationships...")
        result = process_in_batches(
            self.connection,
            data["model_delegation"],
            self.batch_size,
            create_model_delegation_batch,
            "model delegation"
        )
        self.stats["relationships_created"] += result["created"]

        # Load fields
        logger.info(f"Loading {len(data['fields'])} fields...")
        result = process_in_batches(
            self.connection,
            data["fields"],
            self.batch_size,
            create_fields_batch,
            "fields"
        )
        self.stats["relationships_created"] += result["created"]

        # Load field-model relationships
        logger.info(f"Loading {len(data['field_model_rels'])} field-model relationships...")
        result = process_in_batches(
            self.connection,
            data["field_model_rels"],
            self.batch_size,
            create_field_model_relationships_batch,
            "field-model relationships"
        )
        self.stats["relationships_created"] += result["created"]

        # Load field references
        logger.info(f"Loading {len(data['field_references'])} field reference relationships...")
        result = process_in_batches(
            self.connection,
            data["field_references"],
            self.batch_size,
            create_field_references_batch,
            "field references"
        )
        self.stats["relationships_created"] += result["created"]

    def _get_existing_file_hashes(self) -> Dict[str, str]:
        """
        Get file hashes of already indexed files.

        Returns:
            Dictionary mapping file path to hash
        """
        # TODO: Implement query to get existing hashes from database
        # For now, return empty dict (no incremental support yet)
        return {}

    def _check_memory(self) -> None:
        """Check memory usage and warn if threshold exceeded."""
        usage = self.memory_monitor.get_current_usage()
        if usage["percent"] > self.max_memory_percent:
            logger.warning(
                f"Memory usage high: {usage['percent']:.1f}% "
                f"({usage['used_mb']:.0f}MB / {usage['total_mb']:.0f}MB)"
            )
