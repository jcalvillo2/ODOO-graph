"""
Neo4j Graph Loading for Odoo Metadata

This module provides functionality to load extracted Odoo metadata (modules, models,
views) into a Neo4j graph database, creating nodes and relationships for dependency
analysis.

Author: ETL Pipeline Generator
Created: 2025-10-22
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Note: neo4j driver is an optional dependency
try:
    from neo4j import GraphDatabase, Driver
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j package not installed. Graph loading will not work.")


@dataclass
class GraphLoaderConfig:
    """Configuration for Neo4j graph loader."""

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"
    batch_size: int = 100


class GraphLoaderError(Exception):
    """Raised when graph loading encounters an error."""

    pass


class GraphLoader:
    """
    Neo4j graph loader for Odoo metadata.

    Loads modules, models, views, and their relationships into Neo4j.
    """

    def __init__(self, config: GraphLoaderConfig):
        """
        Initialize GraphLoader.

        Args:
            config: GraphLoaderConfig with connection parameters

        Raises:
            GraphLoaderError: If neo4j package is not available
        """
        if not NEO4J_AVAILABLE:
            raise GraphLoaderError(
                "neo4j package not installed. Install with: pip install neo4j"
            )

        self.config = config
        self.driver: Optional[Driver] = None
        self._stats = {
            "modules_created": 0,
            "models_created": 0,
            "views_created": 0,
            "relationships_created": 0,
        }

    def connect(self):
        """Establish connection to Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.username, self.config.password),
            )
            # Test connection
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.config.uri}")
        except Exception as e:
            raise GraphLoaderError(f"Failed to connect to Neo4j: {e}")

    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def load_modules(self, modules: List[Dict]):
        """
        Load module nodes into Neo4j.

        Args:
            modules: List of module metadata dictionaries
        """
        if not self.driver:
            raise GraphLoaderError("Not connected to Neo4j. Call connect() first.")

        query = """
        UNWIND $modules AS mod
        MERGE (m:Module {name: mod.name})
        SET m.version = mod.version,
            m.summary = mod.summary,
            m.path = mod.path,
            m.category = mod.category
        """

        with self.driver.session(database=self.config.database) as session:
            result = session.run(query, modules=modules)
            summary = result.consume()
            self._stats["modules_created"] += summary.counters.nodes_created

        logger.info(f"Loaded {len(modules)} module nodes")

    def load_models(self, models: List[Dict]):
        """
        Load model nodes into Neo4j.

        Args:
            models: List of model metadata dictionaries
        """
        if not self.driver:
            raise GraphLoaderError("Not connected to Neo4j")

        # Create model nodes
        query = """
        UNWIND $models AS model
        MERGE (m:Model {name: model.name, module: model.module})
        SET m.class_name = model.class_name,
            m.model_type = model.model_type,
            m.description = model.description
        """

        with self.driver.session(database=self.config.database) as session:
            result = session.run(query, models=models)
            summary = result.consume()
            self._stats["models_created"] += summary.counters.nodes_created

        # Create Module->Model relationships
        self._create_module_model_relationships(models)

        # Create Model->Model inheritance relationships
        self._create_model_inheritance_relationships(models)

        logger.info(f"Loaded {len(models)} model nodes")

    def _create_module_model_relationships(self, models: List[Dict]):
        """Create CONTAINS relationships from Module to Model."""
        query = """
        UNWIND $models AS model
        MATCH (mod:Module {name: model.module})
        MATCH (m:Model {name: model.name, module: model.module})
        MERGE (mod)-[:CONTAINS]->(m)
        """

        with self.driver.session(database=self.config.database) as session:
            result = session.run(query, models=models)
            summary = result.consume()
            self._stats["relationships_created"] += summary.counters.relationships_created

    def _create_model_inheritance_relationships(self, models: List[Dict]):
        """Create INHERITS relationships between models."""
        # Build inheritance pairs
        pairs = []
        for model in models:
            for parent in model.get("inherits", []):
                pairs.append({"child": model["name"], "parent": parent})

        if not pairs:
            return

        query = """
        UNWIND $pairs AS pair
        MATCH (child:Model {name: pair.child})
        MATCH (parent:Model {name: pair.parent})
        MERGE (child)-[:INHERITS]->(parent)
        """

        with self.driver.session(database=self.config.database) as session:
            result = session.run(query, pairs=pairs)
            summary = result.consume()
            self._stats["relationships_created"] += summary.counters.relationships_created

    def load_views(self, views: List[Dict]):
        """
        Load view nodes into Neo4j.

        Args:
            views: List of view metadata dictionaries
        """
        if not self.driver:
            raise GraphLoaderError("Not connected to Neo4j")

        # Create view nodes
        query = """
        UNWIND $views AS view
        MERGE (v:View {xml_id: view.xml_id})
        SET v.name = view.name,
            v.model = view.model,
            v.view_type = view.view_type,
            v.module = view.module,
            v.mode = view.mode
        """

        with self.driver.session(database=self.config.database) as session:
            result = session.run(query, views=views)
            summary = result.consume()
            self._stats["views_created"] += summary.counters.nodes_created

        # Create relationships
        self._create_module_view_relationships(views)
        self._create_view_model_relationships(views)
        self._create_view_inheritance_relationships(views)

        logger.info(f"Loaded {len(views)} view nodes")

    def _create_module_view_relationships(self, views: List[Dict]):
        """Create CONTAINS relationships from Module to View."""
        query = """
        UNWIND $views AS view
        MATCH (mod:Module {name: view.module})
        MATCH (v:View {xml_id: view.xml_id})
        MERGE (mod)-[:CONTAINS]->(v)
        """

        with self.driver.session(database=self.config.database) as session:
            result = session.run(query, views=views)
            summary = result.consume()
            self._stats["relationships_created"] += summary.counters.relationships_created

    def _create_view_model_relationships(self, views: List[Dict]):
        """Create DISPLAYS relationships from View to Model."""
        # Only create for views with a model
        views_with_model = [v for v in views if v.get("model")]

        query = """
        UNWIND $views AS view
        MATCH (v:View {xml_id: view.xml_id})
        MATCH (m:Model {name: view.model})
        MERGE (v)-[:DISPLAYS]->(m)
        """

        with self.driver.session(database=self.config.database) as session:
            result = session.run(query, views=views_with_model)
            summary = result.consume()
            self._stats["relationships_created"] += summary.counters.relationships_created

    def _create_view_inheritance_relationships(self, views: List[Dict]):
        """Create EXTENDS relationships between views."""
        # Build inheritance pairs
        pairs = []
        for view in views:
            inherit_id = view.get("inherit_id")
            if inherit_id:
                pairs.append({"child": view["xml_id"], "parent": inherit_id})

        if not pairs:
            return

        query = """
        UNWIND $pairs AS pair
        MATCH (child:View {xml_id: pair.child})
        MATCH (parent:View {xml_id: pair.parent})
        MERGE (child)-[:EXTENDS]->(parent)
        """

        with self.driver.session(database=self.config.database) as session:
            result = session.run(query, pairs=pairs)
            summary = result.consume()
            self._stats["relationships_created"] += summary.counters.relationships_created

    def clear_database(self):
        """Clear all nodes and relationships (use with caution!)."""
        query = "MATCH (n) DETACH DELETE n"

        with self.driver.session(database=self.config.database) as session:
            session.run(query)

        logger.warning("Database cleared")

    def get_stats(self) -> Dict[str, int]:
        """Get loading statistics."""
        return self._stats.copy()


def load_graph(
    modules: List[Dict],
    models: List[Dict],
    views: List[Dict],
    config: GraphLoaderConfig,
) -> Dict[str, int]:
    """
    Load Odoo metadata into Neo4j graph database.

    Args:
        modules: List of module metadata dictionaries
        models: List of model metadata dictionaries
        views: List of view metadata dictionaries
        config: GraphLoaderConfig

    Returns:
        Statistics dictionary

    Example:
        >>> config = GraphLoaderConfig(uri="bolt://localhost:7687")
        >>> stats = load_graph(modules, models, views, config)
        >>> print(f"Created {stats['models_created']} model nodes")
    """
    loader = GraphLoader(config)

    try:
        loader.connect()
        loader.load_modules(modules)
        loader.load_models(models)
        loader.load_views(views)
        return loader.get_stats()
    finally:
        loader.close()


if __name__ == "__main__":
    import sys
    import json

    logging.basicConfig(level=logging.INFO)

    # Example usage
    print("Neo4j Graph Loader")
    print("Usage: python load_graph.py <modules.json> <models.json> <views.json>")
    print("Requires neo4j package: pip install neo4j")
