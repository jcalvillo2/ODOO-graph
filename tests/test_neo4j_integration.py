"""
Integration tests for Neo4j graph operations.

These tests require a running Neo4j instance.
Set TEST_NEO4J_URI, TEST_NEO4J_USER, and TEST_NEO4J_PASSWORD
environment variables or use defaults from .env
"""

import pytest
from pathlib import Path
import os

from graph.connection import Neo4jConnection
from graph.schema import (
    initialize_schema,
    verify_schema,
    get_database_stats,
    NodeLabel,
    RelationType
)
from graph.batch_operations import (
    create_modules_batch,
    create_module_dependencies_batch,
    create_models_batch,
    create_model_module_relationships_batch,
    create_model_inheritance_batch,
    create_fields_batch,
    create_field_model_relationships_batch,
    create_field_references_batch
)
from graph.indexer import OdooIndexer
from config.settings import get_settings


@pytest.fixture(scope="module")
def neo4j_connection():
    """
    Create a Neo4j connection for tests.
    Uses test database or falls back to default settings.
    """
    settings = get_settings()

    # Override with test settings if available
    uri = os.getenv("TEST_NEO4J_URI", settings.neo4j_uri)
    user = os.getenv("TEST_NEO4J_USER", settings.neo4j_user)
    password = os.getenv("TEST_NEO4J_PASSWORD", settings.neo4j_password)

    connection = Neo4jConnection(uri=uri, user=user, password=password)

    if not connection.connect():
        pytest.skip("Neo4j is not available for testing")

    # Clear test database before tests
    connection.clear_database()

    yield connection

    # Cleanup: Clear database after tests
    connection.clear_database()
    connection.close()


@pytest.fixture
def clean_database(neo4j_connection):
    """Ensure database is clean before each test."""
    neo4j_connection.clear_database()
    yield neo4j_connection


class TestNeo4jConnection:
    """Test Neo4j connection functionality."""

    def test_connection_success(self, neo4j_connection):
        """Test successful connection to Neo4j."""
        assert neo4j_connection._connected is True
        assert neo4j_connection.driver is not None

    def test_execute_query(self, neo4j_connection):
        """Test executing a read query."""
        query = "RETURN 1 as number"
        result = neo4j_connection.execute_query(query, {})
        assert len(result) == 1
        assert result[0]["number"] == 1

    def test_execute_write(self, clean_database):
        """Test executing a write query."""
        query = f"CREATE (m:{NodeLabel.MODULE} {{name: 'test_module'}}) RETURN m"
        result = clean_database.execute_write(query, {})
        assert result is not None

    def test_clear_database(self, neo4j_connection):
        """Test clearing the database."""
        # Create some test data
        query = f"CREATE (m:{NodeLabel.MODULE} {{name: 'test'}})"
        neo4j_connection.execute_write(query, {})

        # Clear database
        result = neo4j_connection.clear_database()
        assert result["nodes_deleted"] >= 1

        # Verify empty
        stats = neo4j_connection.get_statistics()
        assert stats["nodes"] == 0
        assert stats["relationships"] == 0


class TestSchema:
    """Test schema initialization and verification."""

    def test_initialize_schema(self, clean_database):
        """Test schema initialization."""
        result = initialize_schema(clean_database)

        assert result["constraints_created"] >= 3
        assert result["indexes_created"] >= 8
        assert len(result["errors"]) == 0

    def test_verify_schema(self, clean_database):
        """Test schema verification."""
        initialize_schema(clean_database)
        result = verify_schema(clean_database)

        assert result["valid"] is True
        assert result["total_indexes"] > 0

    def test_get_database_stats_empty(self, clean_database):
        """Test getting stats from empty database."""
        stats = get_database_stats(clean_database)

        assert stats["module_count"] == 0
        assert stats["model_count"] == 0
        assert stats["field_count"] == 0


class TestBatchOperations:
    """Test batch operations for nodes and relationships."""

    @pytest.fixture(autouse=True)
    def setup_schema(self, clean_database):
        """Initialize schema before each test."""
        initialize_schema(clean_database)
        self.connection = clean_database

    def test_create_modules_batch(self):
        """Test creating module nodes in batch."""
        modules = [
            {
                "name": "base",
                "version": "18.0.1.0",
                "category": "Hidden",
                "summary": "Base Module",
                "description": "The kernel of Odoo",
                "author": "Odoo S.A.",
                "website": "https://www.odoo.com",
                "license": "LGPL-3",
                "installable": True,
                "auto_install": True,
                "application": False,
                "file_path": "/path/to/base/__manifest__.py",
                "file_hash": "abc123"
            },
            {
                "name": "sale",
                "version": "18.0.1.0",
                "category": "Sales",
                "summary": "Sales Management",
                "description": "Manage sales",
                "author": "Odoo S.A.",
                "website": "https://www.odoo.com",
                "license": "LGPL-3",
                "installable": True,
                "auto_install": False,
                "application": True,
                "file_path": "/path/to/sale/__manifest__.py",
                "file_hash": "def456"
            }
        ]

        result = create_modules_batch(self.connection, modules)
        assert result["created"] == 2
        assert result["errors"] == 0

        # Verify in database
        stats = get_database_stats(self.connection)
        assert stats["module_count"] == 2

    def test_create_module_dependencies(self):
        """Test creating module dependency relationships."""
        # First create modules
        modules = [
            {"name": "base", "version": "18.0", "category": "Hidden", "summary": "",
             "description": "", "author": "", "website": "", "license": "",
             "installable": True, "auto_install": False, "application": False,
             "file_path": "", "file_hash": ""},
            {"name": "sale", "version": "18.0", "category": "Sales", "summary": "",
             "description": "", "author": "", "website": "", "license": "",
             "installable": True, "auto_install": False, "application": False,
             "file_path": "", "file_hash": ""}
        ]
        create_modules_batch(self.connection, modules)

        # Create dependency
        dependencies = [{"from": "sale", "to": "base"}]
        result = create_module_dependencies_batch(self.connection, dependencies)

        assert result["created"] == 1
        assert result["errors"] == 0

    def test_create_models_batch(self):
        """Test creating model nodes in batch."""
        models = [
            {
                "name": "res.partner",
                "description": "Partner",
                "module": "base",
                "file_path": "/path/to/partner.py",
                "line_number": 10,
                "class_name": "Partner",
                "file_hash": "hash1"
            },
            {
                "name": "sale.order",
                "description": "Sales Order",
                "module": "sale",
                "file_path": "/path/to/sale_order.py",
                "line_number": 15,
                "class_name": "SaleOrder",
                "file_hash": "hash2"
            }
        ]

        result = create_models_batch(self.connection, models)
        assert result["created"] == 2
        assert result["errors"] == 0

        # Verify in database
        stats = get_database_stats(self.connection)
        assert stats["model_count"] == 2

    def test_create_model_inheritance(self):
        """Test creating model inheritance relationships."""
        # Create models first
        models = [
            {"name": "res.partner", "description": "", "module": "base",
             "file_path": "", "line_number": 0, "class_name": "", "file_hash": ""},
            {"name": "res.partner.custom", "description": "", "module": "custom",
             "file_path": "", "line_number": 0, "class_name": "", "file_hash": ""}
        ]
        create_models_batch(self.connection, models)

        # Create inheritance
        inheritances = [{"from": "res.partner.custom", "to": "res.partner"}]
        result = create_model_inheritance_batch(self.connection, inheritances)

        assert result["created"] == 1
        assert result["errors"] == 0

    def test_create_fields_batch(self):
        """Test creating field nodes in batch."""
        fields = [
            {
                "name": "name",
                "model_name": "res.partner",
                "field_type": "Char",
                "string": "Name",
                "required": True,
                "readonly": False,
                "help": None,
                "default": None,
                "compute": None,
                "store": None,
                "related": None,
                "depends": None,
                "inverse_name": None,
                "comodel_name": None,
                "domain": None,
                "selection": None,
                "states": None,
                "copy": None,
                "index": None,
                "translate": None,
                "digits": None,
                "sanitize": None,
                "strip_style": None
            },
            {
                "name": "email",
                "model_name": "res.partner",
                "field_type": "Char",
                "string": "Email",
                "required": False,
                "readonly": False,
                "help": "Email address",
                "default": None,
                "compute": None,
                "store": None,
                "related": None,
                "depends": None,
                "inverse_name": None,
                "comodel_name": None,
                "domain": None,
                "selection": None,
                "states": None,
                "copy": None,
                "index": True,
                "translate": None,
                "digits": None,
                "sanitize": None,
                "strip_style": None
            }
        ]

        result = create_fields_batch(self.connection, fields)
        assert result["created"] == 2
        assert result["errors"] == 0

        # Verify in database
        stats = get_database_stats(self.connection)
        assert stats["field_count"] == 2

    def test_create_field_model_relationships(self):
        """Test creating field-model relationships."""
        # Create model and fields first
        models = [{"name": "res.partner", "description": "", "module": "base",
                  "file_path": "", "line_number": 0, "class_name": "", "file_hash": ""}]
        create_models_batch(self.connection, models)

        fields = [
            {"name": "name", "model_name": "res.partner", "field_type": "Char",
             "string": None, "required": None, "readonly": None, "help": None,
             "default": None, "compute": None, "store": None, "related": None,
             "depends": None, "inverse_name": None, "comodel_name": None,
             "domain": None, "selection": None, "states": None, "copy": None,
             "index": None, "translate": None, "digits": None, "sanitize": None,
             "strip_style": None}
        ]
        create_fields_batch(self.connection, fields)

        # Create relationships
        relationships = [{"field_name": "name", "model_name": "res.partner"}]
        result = create_field_model_relationships_batch(self.connection, relationships)

        assert result["created"] == 1
        assert result["errors"] == 0

    def test_create_field_references(self):
        """Test creating field reference relationships."""
        # Create models first
        models = [
            {"name": "res.partner", "description": "", "module": "base",
             "file_path": "", "line_number": 0, "class_name": "", "file_hash": ""},
            {"name": "sale.order", "description": "", "module": "sale",
             "file_path": "", "line_number": 0, "class_name": "", "file_hash": ""}
        ]
        create_models_batch(self.connection, models)

        # Create field
        fields = [
            {"name": "partner_id", "model_name": "sale.order", "field_type": "Many2one",
             "string": "Partner", "required": None, "readonly": None, "help": None,
             "default": None, "compute": None, "store": None, "related": None,
             "depends": None, "inverse_name": None, "comodel_name": "res.partner",
             "domain": None, "selection": None, "states": None, "copy": None,
             "index": None, "translate": None, "digits": None, "sanitize": None,
             "strip_style": None}
        ]
        create_fields_batch(self.connection, fields)

        # Create reference
        references = [
            {"field_name": "partner_id", "model_name": "sale.order", "comodel": "res.partner"}
        ]
        result = create_field_references_batch(self.connection, references)

        assert result["created"] == 1
        assert result["errors"] == 0


class TestIndexer:
    """Test the complete indexing workflow."""

    @pytest.fixture
    def test_odoo_path(self, tmp_path):
        """Create a minimal test Odoo module structure."""
        # Create base module
        base_module = tmp_path / "base"
        base_module.mkdir()

        manifest = base_module / "__manifest__.py"
        manifest.write_text("""
{
    'name': 'Base',
    'version': '18.0.1.0',
    'category': 'Hidden',
    'summary': 'Base Module',
    'depends': [],
    'installable': True,
    'application': False,
}
""")

        models_dir = base_module / "models"
        models_dir.mkdir()

        partner_model = models_dir / "partner.py"
        partner_model.write_text("""
from odoo import models, fields

class Partner(models.Model):
    _name = 'res.partner'
    _description = 'Partner'

    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email')
""")

        return tmp_path

    def test_full_indexing_workflow(self, clean_database, test_odoo_path):
        """Test complete indexing workflow."""
        indexer = OdooIndexer(
            odoo_path=test_odoo_path,
            connection=clean_database,
            batch_size=100
        )

        stats = indexer.index_all(clear_existing=True, incremental=False)

        # Verify statistics
        assert stats["modules_found"] == 1
        assert stats["modules_indexed"] == 1
        assert stats["models_indexed"] == 1
        assert stats["fields_indexed"] == 2
        assert stats["errors"] == 0
        assert stats["duration_seconds"] > 0

        # Verify database contents
        db_stats = get_database_stats(clean_database)
        assert db_stats["module_count"] == 1
        assert db_stats["model_count"] == 1
        assert db_stats["field_count"] == 2
        assert db_stats["defined_in_count"] == 1
        assert db_stats["belongs_to_count"] == 2
