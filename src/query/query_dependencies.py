"""
Odoo Dependency Query Interface

This module provides a Python API for querying the Odoo dependency graph stored
in Neo4j. Includes common query patterns and support for custom Cypher queries.

Author: ETL Pipeline Generator
Created: 2025-10-22
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase, Driver
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False


class QueryInterfaceError(Exception):
    """Raised when query execution fails."""

    pass


class QueryInterface:
    """
    Interface for querying Odoo dependency graph.

    Provides common query patterns and custom Cypher execution.
    """

    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        """
        Initialize QueryInterface.

        Args:
            uri: Neo4j connection URI
            username: Neo4j username
            password: Neo4j password
            database: Neo4j database name
        """
        if not NEO4J_AVAILABLE:
            raise QueryInterfaceError("neo4j package not installed")

        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver: Optional[Driver] = None

    def connect(self):
        """Establish connection to Neo4j."""
        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        logger.info("Connected to Neo4j")

    def close(self):
        """Close connection."""
        if self.driver:
            self.driver.close()

    def find_model_children(self, parent_name: str, depth: int = 10) -> List[Dict]:
        """
        Find all models inheriting from a parent model.

        Args:
            parent_name: Name of parent model
            depth: Maximum inheritance depth to traverse

        Returns:
            List of model dictionaries
        """
        query = f"""
        MATCH (m:Model)-[:INHERITS*1..{depth}]->(p:Model {{name: $parent_name}})
        RETURN m.name AS name, m.module AS module, m.description AS description
        """

        return self.execute_cypher(query, {"parent_name": parent_name})

    def find_view_extensions(self, parent_view_id: str, depth: int = 10) -> List[Dict]:
        """
        Find all views extending a parent view.

        Args:
            parent_view_id: XML ID of parent view
            depth: Maximum extension depth

        Returns:
            List of view dictionaries
        """
        query = f"""
        MATCH (v:View)-[:EXTENDS*1..{depth}]->(parent:View {{xml_id: $parent_view_id}})
        RETURN v.xml_id AS xml_id, v.name AS name, v.view_type AS view_type
        """

        return self.execute_cypher(query, {"parent_view_id": parent_view_id})

    def find_views_for_model(self, model_name: str) -> List[Dict]:
        """
        Find all views displaying a specific model.

        Args:
            model_name: Name of the model

        Returns:
            List of view dictionaries
        """
        query = """
        MATCH (v:View)-[:DISPLAYS]->(m:Model {name: $model_name})
        RETURN v.xml_id AS xml_id, v.name AS name, v.view_type AS view_type
        """

        return self.execute_cypher(query, {"model_name": model_name})

    def find_module_dependencies(self, module_name: str) -> List[str]:
        """
        Find all modules that the given module depends on.

        Args:
            module_name: Name of the module

        Returns:
            List of dependency module names
        """
        query = """
        MATCH (m:Module)-[:CONTAINS]->(model:Model)-[:INHERITS]->(parent:Model)<-[:CONTAINS]-(dep:Module)
        WHERE m.name = $module_name AND m <> dep
        RETURN DISTINCT dep.name AS name
        """

        results = self.execute_cypher(query, {"module_name": module_name})
        return [r["name"] for r in results]

    def execute_cypher(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Execute a custom Cypher query.

        Args:
            query: Cypher query string
            params: Query parameters

        Returns:
            List of result dictionaries
        """
        if not self.driver:
            raise QueryInterfaceError("Not connected. Call connect() first.")

        params = params or {}
        results = []

        with self.driver.session(database=self.database) as session:
            result = session.run(query, params)
            for record in result:
                results.append(dict(record))

        return results


if __name__ == "__main__":
    import sys
    import json

    logging.basicConfig(level=logging.INFO)

    print("Odoo Dependency Query Interface")
    print("Example: Find models inheriting from 'mail.thread'")
    print("Requires: Neo4j running with loaded data")
