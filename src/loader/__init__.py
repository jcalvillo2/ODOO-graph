"""
Loader module for Odoo ETL pipeline.

Provides functionality to load extracted metadata into Neo4j graph database.
"""

from .load_graph import GraphLoader, GraphLoaderConfig, load_graph, NEO4J_AVAILABLE

__all__ = ["GraphLoader", "GraphLoaderConfig", "load_graph", "NEO4J_AVAILABLE"]
