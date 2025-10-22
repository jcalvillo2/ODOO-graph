"""
Odoo ETL Pipeline

This package provides Extract-Transform-Load functionality for indexing Odoo
source code and loading it into a Neo4j graph database for dependency analysis.

Modules:
    extractor: Extract metadata from Odoo modules, models, and views
    transformer: Transform and prepare data for loading
    loader: Load data into Neo4j graph database
    query: Query the dependency graph
"""

__version__ = "1.0.0"
__author__ = "ETL Pipeline Generator"
