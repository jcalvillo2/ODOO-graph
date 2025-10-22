"""
Tests for model parser module.

This module tests the parsing of Odoo Python model files
using various scenarios including edge cases.
"""

import ast
import tempfile
from pathlib import Path

import pytest

from parsers.model_parser import (
    find_model_files,
    parse_model_file,
    is_odoo_model,
    _is_field_definition,
    _extract_field_info,
    _ast_node_to_python,
)


# Test Fixtures

@pytest.fixture
def temp_module_with_models(tmp_path):
    """
    Create a temporary module with model files.

    Structure:
        test_module/
            models/
                model_a.py
                model_b.py
            __init__.py
    """
    module = tmp_path / "test_module"
    module.mkdir()

    models_dir = module / "models"
    models_dir.mkdir()

    # Model A - Simple model
    (models_dir / "model_a.py").write_text("""
from odoo import models, fields

class ModelA(models.Model):
    _name = 'test.model.a'
    _description = 'Test Model A'

    name = fields.Char(string='Name', required=True)
    value = fields.Integer(string='Value')
""")

    # Model B - Model with inheritance
    (models_dir / "model_b.py").write_text("""
from odoo import models, fields

class ModelB(models.Model):
    _name = 'test.model.b'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Test Model B'

    partner_id = fields.Many2one('res.partner', string='Partner')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')
""")

    # __init__.py
    (module / "__init__.py").write_text("")

    return module


@pytest.fixture
def temp_model_without_name(tmp_path):
    """Create a model that only has _inherit (no _name)."""
    module = tmp_path / "test_module"
    module.mkdir()

    models_dir = module / "models"
    models_dir.mkdir()

    (models_dir / "inherit_only.py").write_text("""
from odoo import models, fields

class SaleOrderExtension(models.Model):
    _inherit = 'sale.order'

    custom_field = fields.Char(string='Custom Field')
""")

    return module


@pytest.fixture
def temp_model_with_complex_fields(tmp_path):
    """Create a model with various field types."""
    module = tmp_path / "test_module"
    module.mkdir()

    models_dir = module / "models"
    models_dir.mkdir()

    (models_dir / "complex.py").write_text("""
from odoo import models, fields

class ComplexModel(models.Model):
    _name = 'test.complex'
    _description = 'Complex Model'

    # Different field types
    char_field = fields.Char('Char Field', size=50)
    text_field = fields.Text('Text Field')
    integer_field = fields.Integer('Integer')
    float_field = fields.Float('Float', digits=(10, 2))
    boolean_field = fields.Boolean('Boolean', default=True)
    date_field = fields.Date('Date')
    datetime_field = fields.Datetime('Datetime')

    # Relational fields
    many2one_field = fields.Many2one('res.partner', 'Partner')
    one2many_field = fields.One2many('test.line', 'parent_id', 'Lines')
    many2many_field = fields.Many2many('res.users', string='Users')

    # Selection
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Done')
    ], string='State', default='draft')

    # Computed field
    computed = fields.Char(compute='_compute_something')
""")

    return module


@pytest.fixture
def temp_model_with_syntax_error(tmp_path):
    """Create a model file with syntax error."""
    module = tmp_path / "test_module"
    module.mkdir()

    models_dir = module / "models"
    models_dir.mkdir()

    (models_dir / "broken.py").write_text("""
from odoo import models, fields

class BrokenModel(models.Model):
    _name = 'test.broken'

    # Missing closing parenthesis
    name = fields.Char('Name'
""")

    return module


# Tests for find_model_files

def test_find_model_files_in_models_dir(temp_module_with_models):
    """Test finding model files in models/ directory."""
    model_files = list(find_model_files(temp_module_with_models))

    assert len(model_files) == 2
    filenames = [f.name for f in model_files]
    assert "model_a.py" in filenames
    assert "model_b.py" in filenames


def test_find_model_files_skips_init(temp_module_with_models):
    """Test that __init__.py is skipped."""
    models_dir = temp_module_with_models / "models"
    (models_dir / "__init__.py").write_text("")

    model_files = list(find_model_files(temp_module_with_models))
    filenames = [f.name for f in model_files]

    assert "__init__.py" not in filenames


def test_find_model_files_empty_module(tmp_path):
    """Test with module that has no models directory."""
    module = tmp_path / "empty_module"
    module.mkdir()

    model_files = list(find_model_files(module))
    assert len(model_files) == 0


def test_find_model_files_uses_generator():
    """Test that find_model_files returns a generator."""
    result = find_model_files(Path("."))
    assert hasattr(result, "__iter__")
    assert hasattr(result, "__next__")


# Tests for parse_model_file

def test_parse_simple_model(temp_module_with_models):
    """Test parsing a simple model file."""
    model_file = temp_module_with_models / "models" / "model_a.py"
    models = parse_model_file(model_file, "test_module")

    assert len(models) == 1
    model = models[0]

    assert model["name"] == "test.model.a"
    assert model["class_name"] == "ModelA"
    assert model["description"] == "Test Model A"
    assert model["module_name"] == "test_module"
    assert len(model["fields"]) == 2
    assert "name" in model["fields"]
    assert "value" in model["fields"]


def test_parse_model_with_inheritance(temp_module_with_models):
    """Test parsing a model with multiple inheritance."""
    model_file = temp_module_with_models / "models" / "model_b.py"
    models = parse_model_file(model_file, "test_module")

    assert len(models) == 1
    model = models[0]

    assert model["name"] == "test.model.b"
    assert model["inherit"] == ["mail.thread", "mail.activity.mixin"]
    assert len(model["fields"]) == 2


def test_parse_model_without_name(temp_model_without_name):
    """Test parsing model with only _inherit (no _name)."""
    model_file = temp_model_without_name / "models" / "inherit_only.py"
    models = parse_model_file(model_file, "test_module")

    assert len(models) == 1
    model = models[0]

    # Should use first _inherit as name
    assert model["name"] == "sale.order"
    assert model["inherit"] == ["sale.order"]
    assert "custom_field" in model["fields"]


def test_parse_complex_fields(temp_model_with_complex_fields):
    """Test parsing various field types."""
    model_file = temp_model_with_complex_fields / "models" / "complex.py"
    models = parse_model_file(model_file, "test_module")

    assert len(models) == 1
    model = models[0]
    fields = model["fields"]

    # Check field types
    assert fields["char_field"]["type"] == "Char"
    assert fields["integer_field"]["type"] == "Integer"
    assert fields["boolean_field"]["type"] == "Boolean"
    assert fields["many2one_field"]["type"] == "Many2one"
    assert fields["one2many_field"]["type"] == "One2many"
    assert fields["state"]["type"] == "Selection"

    # Check field parameters
    assert fields["char_field"]["string"] == "Char Field"
    assert fields["boolean_field"]["default"] is True
    assert fields["computed"]["compute"] == "_compute_something"


def test_parse_file_with_syntax_error(temp_model_with_syntax_error):
    """Test that syntax errors are handled gracefully."""
    model_file = temp_model_with_syntax_error / "models" / "broken.py"
    models = parse_model_file(model_file, "test_module")

    # Should return empty list, not crash
    assert models == []


def test_parse_nonexistent_file():
    """Test parsing nonexistent file."""
    models = parse_model_file(Path("/nonexistent/file.py"), "test")
    assert models == []


# Tests for is_odoo_model

def test_is_odoo_model_with_models_model():
    """Test detecting models.Model class."""
    code = """
class MyModel(models.Model):
    _name = 'my.model'
"""
    tree = ast.parse(code)
    class_node = tree.body[0]

    assert is_odoo_model(class_node) is True


def test_is_odoo_model_with_transient_model():
    """Test detecting models.TransientModel."""
    code = """
class MyWizard(models.TransientModel):
    _name = 'my.wizard'
"""
    tree = ast.parse(code)
    class_node = tree.body[0]

    assert is_odoo_model(class_node) is True


def test_is_odoo_model_with_abstract_model():
    """Test detecting models.AbstractModel."""
    code = """
class MyAbstract(models.AbstractModel):
    _name = 'my.abstract'
"""
    tree = ast.parse(code)
    class_node = tree.body[0]

    assert is_odoo_model(class_node) is True


def test_is_odoo_model_with_regular_class():
    """Test that regular classes are not detected."""
    code = """
class RegularClass:
    pass
"""
    tree = ast.parse(code)
    class_node = tree.body[0]

    assert is_odoo_model(class_node) is False


def test_is_odoo_model_with_other_inheritance():
    """Test class inheriting from other base."""
    code = """
class MyClass(BaseClass):
    pass
"""
    tree = ast.parse(code)
    class_node = tree.body[0]

    assert is_odoo_model(class_node) is False


# Tests for helper functions

def test_is_field_definition_char():
    """Test detecting Char field definition."""
    code = "name = fields.Char('Name')"
    tree = ast.parse(code)
    assign_node = tree.body[0]

    assert _is_field_definition(assign_node.value) is True


def test_is_field_definition_many2one():
    """Test detecting Many2one field definition."""
    code = "partner_id = fields.Many2one('res.partner')"
    tree = ast.parse(code)
    assign_node = tree.body[0]

    assert _is_field_definition(assign_node.value) is True


def test_is_field_definition_not_field():
    """Test that non-field assignments are not detected."""
    code = "value = 42"
    tree = ast.parse(code)
    assign_node = tree.body[0]

    assert _is_field_definition(assign_node.value) is False


def test_extract_field_info_with_string():
    """Test extracting field info with string parameter."""
    code = "fields.Char('Name', required=True, size=50)"
    tree = ast.parse(code, mode='eval')

    field_info = _extract_field_info(tree.body)

    assert field_info["type"] == "Char"
    assert field_info["string"] == "Name"
    assert field_info["required"] is True
    assert field_info["size"] == 50


def test_extract_field_info_selection():
    """Test extracting Selection field info."""
    code = "fields.Selection([('draft', 'Draft'), ('done', 'Done')])"
    tree = ast.parse(code, mode='eval')

    field_info = _extract_field_info(tree.body)

    assert field_info["type"] == "Selection"
    assert field_info["selection"] == [("draft", "Draft"), ("done", "Done")]


def test_ast_node_to_python_string():
    """Test converting AST string to Python."""
    node = ast.parse("'hello'", mode='eval').body
    assert _ast_node_to_python(node) == "hello"


def test_ast_node_to_python_number():
    """Test converting AST number to Python."""
    node = ast.parse("42", mode='eval').body
    assert _ast_node_to_python(node) == 42


def test_ast_node_to_python_boolean():
    """Test converting AST boolean to Python."""
    true_node = ast.parse("True", mode='eval').body
    false_node = ast.parse("False", mode='eval').body

    assert _ast_node_to_python(true_node) is True
    assert _ast_node_to_python(false_node) is False


def test_ast_node_to_python_list():
    """Test converting AST list to Python."""
    node = ast.parse("[1, 2, 3]", mode='eval').body
    assert _ast_node_to_python(node) == [1, 2, 3]


def test_ast_node_to_python_dict():
    """Test converting AST dict to Python."""
    node = ast.parse("{'key': 'value'}", mode='eval').body
    assert _ast_node_to_python(node) == {"key": "value"}


# Integration tests

def test_full_workflow(temp_module_with_models):
    """Test complete workflow: find files and parse all models."""
    model_files = list(find_model_files(temp_module_with_models))
    all_models = []

    for model_file in model_files:
        models = parse_model_file(model_file, "test_module")
        all_models.extend(models)

    assert len(all_models) == 2
    model_names = [m["name"] for m in all_models]
    assert "test.model.a" in model_names
    assert "test.model.b" in model_names

    # Check total fields
    total_fields = sum(len(m["fields"]) for m in all_models)
    assert total_fields == 4  # 2 fields in model_a + 2 in model_b


def test_encoding_handling(tmp_path):
    """Test handling different file encodings."""
    module = tmp_path / "test_module"
    module.mkdir()
    models_dir = module / "models"
    models_dir.mkdir()

    # Create model with UTF-8 special characters
    model_content = """
from odoo import models, fields

class TestModel(models.Model):
    _name = 'test.model'
    _description = 'Modelo de Prueba con ñ y acentos'

    nombre = fields.Char('Nombre del Cliente')
"""
    (models_dir / "test.py").write_text(model_content, encoding='utf-8')

    models = parse_model_file(models_dir / "test.py", "test_module")

    assert len(models) == 1
    assert "ñ" in models[0]["description"]
