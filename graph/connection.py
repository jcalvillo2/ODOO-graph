"""
Neo4j connection manager for Odoo Tracker.

This module provides a connection manager for Neo4j with
automatic retry, error handling, and context manager support.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase, Session
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """
    Neo4j connection manager with retry and error handling.

    This class provides a robust connection to Neo4j with:
    - Automatic retry on connection failures
    - Context manager support for safe resource handling
    - Transaction management
    - Connection verification

    Example:
        >>> with Neo4jConnection(uri, user, password) as conn:
        ...     result = conn.execute_query("MATCH (n) RETURN count(n)")
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize Neo4j connection.

        Args:
            uri: Neo4j connection URI (e.g., 'bolt://localhost:7687')
            user: Username for authentication
            password: Password for authentication
            max_retries: Maximum number of connection retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.driver = None
        self._connected = False

    def connect(self) -> bool:
        """
        Establish connection to Neo4j with retry logic.

        Returns:
            True if connection successful, False otherwise

        Raises:
            AuthError: If authentication fails
            ServiceUnavailable: If Neo4j is not reachable after retries
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Connecting to Neo4j at {self.uri} (attempt {attempt + 1}/{self.max_retries})")

                self.driver = GraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self.password),
                )

                # Verify connectivity
                self.driver.verify_connectivity()

                self._connected = True
                logger.info("Successfully connected to Neo4j")
                return True

            except AuthError as e:
                logger.error(f"Authentication failed: {e}")
                raise

            except ServiceUnavailable as e:
                logger.warning(f"Neo4j unavailable (attempt {attempt + 1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error("Max retries reached. Neo4j is not available.")
                    raise

            except Exception as e:
                logger.error(f"Unexpected error connecting to Neo4j: {e}")
                raise

        return False

    def close(self):
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()
            self._connected = False
            logger.info("Neo4j connection closed")

    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self._connected and self.driver is not None

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: str = "neo4j",
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters
            database: Database name (default: 'neo4j')

        Returns:
            List of result records as dictionaries

        Raises:
            RuntimeError: If not connected to Neo4j
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")

        parameters = parameters or {}

        with self.driver.session(database=database) as session:
            result = session.run(query, parameters)
            return [dict(record) for record in result]

    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: str = "neo4j",
    ) -> Dict[str, Any]:
        """
        Execute a write query in a transaction.

        Args:
            query: Cypher query string
            parameters: Query parameters
            database: Database name (default: 'neo4j')

        Returns:
            Query summary statistics

        Raises:
            RuntimeError: If not connected to Neo4j
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")

        parameters = parameters or {}

        def transaction_function(tx):
            result = tx.run(query, parameters)
            summary = result.consume()
            return {
                "nodes_created": summary.counters.nodes_created,
                "relationships_created": summary.counters.relationships_created,
                "properties_set": summary.counters.properties_set,
                "nodes_deleted": summary.counters.nodes_deleted,
                "relationships_deleted": summary.counters.relationships_deleted,
            }

        with self.driver.session(database=database) as session:
            return session.execute_write(transaction_function)

    def execute_batch(
        self,
        query: str,
        batch: List[Dict[str, Any]],
        database: str = "neo4j",
    ) -> Dict[str, Any]:
        """
        Execute a query with a batch of data.

        Args:
            query: Cypher query (should use UNWIND $batch)
            batch: List of parameter dictionaries
            database: Database name (default: 'neo4j')

        Returns:
            Query summary statistics
        """
        return self.execute_write(query, {"batch": batch}, database)

    def clear_database(self, database: str = "neo4j") -> Dict[str, Any]:
        """
        Clear all nodes and relationships from the database.

        Args:
            database: Database name (default: 'neo4j')

        Returns:
            Deletion statistics

        Warning:
            This will delete ALL data in the database!
        """
        logger.warning("Clearing all data from Neo4j database")

        query = """
        MATCH (n)
        DETACH DELETE n
        """

        return self.execute_write(query, database=database)

    def get_statistics(self, database: str = "neo4j") -> Dict[str, Any]:
        """
        Get database statistics.

        Args:
            database: Database name (default: 'neo4j')

        Returns:
            Dictionary with node and relationship counts
        """
        stats = {}

        # Count nodes by label
        query = """
        CALL db.labels() YIELD label
        CALL apoc.cypher.run('MATCH (n:' + label + ') RETURN count(n) as count', {})
        YIELD value
        RETURN label, value.count as count
        """

        # Fallback if APOC is not available
        simple_query = """
        MATCH (n)
        RETURN labels(n)[0] as label, count(n) as count
        ORDER BY label
        """

        try:
            results = self.execute_query(query, database=database)
        except:
            # APOC not available, use simple query
            results = self.execute_query(simple_query, database=database)

        stats["nodes"] = {r["label"]: r["count"] for r in results if r["label"]}

        # Count relationships by type
        rel_query = """
        MATCH ()-[r]->()
        RETURN type(r) as rel_type, count(r) as count
        ORDER BY rel_type
        """

        rel_results = self.execute_query(rel_query, database=database)
        stats["relationships"] = {r["rel_type"]: r["count"] for r in rel_results}

        # Total counts
        stats["total_nodes"] = sum(stats["nodes"].values())
        stats["total_relationships"] = sum(stats["relationships"].values())

        return stats

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
