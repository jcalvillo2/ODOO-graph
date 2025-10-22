"""
Tests for manifest parser module.

This module tests the parsing of Odoo __manifest__.py files
using various scenarios including edge cases.
"""

import ast
import tempfile
from pathlib import Path

import pytest

from parsers.manifest_parser import (
    find_modules,
    parse_manifest,
    get_manifest_dependencies,
    is_module_installable,
    _ast_dict_to_python,
    _ast_node_to_python,
)


# Test Fixtures

@pytest.fixture
def temp_odoo_structure(tmp_path):
    """
    Create a temporary Odoo-like directory structure.

    Structure:
        addons/
            module_a/
                __manifest__.py
            module_b/
                __openerp__.py
            module_c/
                (no manifest)
            nested/
                module_d/
                    __manifest__.py
    """
    addons = tmp_path / "addons"
    addons.mkdir()

    # Module A - valid manifest
    module_a = addons / "module_a"
    module_a.mkdir()
    (module_a / "__manifest__.py").write_text("""
{
    'name': 'Module A',
    'version': '1.0',
    'depends': ['base'],
    'category': 'Test',
    'installable': True,
}
""")

    # Module B - old style manifest
    module_b = addons / "module_b"
    module_b.mkdir()
    (module_b / "__openerp__.py").write_text("""
{
    'name': 'Module B',
    'version': '2.0',
    'depends': ['base', 'module_a'],
}
""")

    # Module C - no manifest
    module_c = addons / "module_c"
    module_c.mkdir()
    (module_c / "README.md").write_text("Not a module")

    # Nested module D
    nested = addons / "nested"
    nested.mkdir()
    module_d = nested / "module_d"
    module_d.mkdir()
    (module_d / "__manifest__.py").write_text("""
{
    'name': 'Module D',
    'version': '3.0',
    'depends': [],
}
""")

    return addons


@pytest.fixture
def manifest_with_complex_data(tmp_path):
    """Create a module with complex manifest data."""
    module = tmp_path / "complex_module"
    module.mkdir()

    manifest_content = """
{
    'name': 'Complex Module',
    'version': '16.0.1.0.0',
    'depends': ['base', 'sale', 'stock'],
    'author': 'John Doe, Jane Smith',
    'category': 'Sales/CRM',
    'summary': 'A complex test module',
    'description': '''
        This is a multiline description
        with multiple lines
    ''',
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
    'data': [
        'views/view1.xml',
        'views/view2.xml',
    ],
    'demo': [],
    'external_dependencies': {
        'python': ['requests', 'lxml'],
    },
}
"""
    (module / "__manifest__.py").write_text(manifest_content)
    return module


@pytest.fixture
def manifest_with_syntax_error(tmp_path):
    """Create a module with syntax error in manifest."""
    module = tmp_path / "broken_module"
    module.mkdir()

    manifest_content = """
{
    'name': 'Broken Module',
    'version': '1.0',
    'depends': ['base',  # Missing closing bracket
}
"""
    (module / "__manifest__.py").write_text(manifest_content)
    return module


# Tests for find_modules

def test_find_modules_discovers_all_modules(temp_odoo_structure):
    """Test that find_modules discovers all valid modules."""
    modules = list(find_modules(temp_odoo_structure))
    module_names = [m.name for m in modules]

    assert len(modules) == 3
    assert "module_a" in module_names
    assert "module_b" in module_names
    assert "module_d" in module_names
    assert "module_c" not in module_names  # No manifest


def test_find_modules_handles_nonexistent_directory():
    """Test that find_modules handles non-existent directories gracefully."""
    modules = list(find_modules(Path("/nonexistent/path")))
    assert len(modules) == 0


def test_find_modules_respects_max_depth(temp_odoo_structure):
    """Test that find_modules respects max_depth parameter."""
    # With depth 1, should not find nested module_d
    modules = list(find_modules(temp_odoo_structure, max_depth=1))
    module_names = [m.name for m in modules]

    assert "module_a" in module_names
    assert "module_b" in module_names
    assert "module_d" not in module_names  # Too deep


def test_find_modules_uses_generator():
    """Test that find_modules returns a generator."""
    result = find_modules(Path("."))
    assert hasattr(result, "__iter__")
    assert hasattr(result, "__next__")


# Tests for parse_manifest

def test_parse_manifest_basic(temp_odoo_structure):
    """Test parsing a basic manifest file."""
    module_a = temp_odoo_structure / "module_a"
    manifest = parse_manifest(module_a)

    assert manifest is not None
    assert manifest["name"] == "Module A"
    assert manifest["version"] == "1.0"
    assert manifest["depends"] == ["base"]
    assert manifest["category"] == "Test"
    assert manifest["installable"] is True
    assert manifest["module_name"] == "module_a"


def test_parse_manifest_old_style(temp_odoo_structure):
    """Test parsing old-style __openerp__.py manifest."""
    module_b = temp_odoo_structure / "module_b"
    manifest = parse_manifest(module_b)

    assert manifest is not None
    assert manifest["name"] == "Module B"
    assert manifest["version"] == "2.0"
    assert manifest["depends"] == ["base", "module_a"]


def test_parse_manifest_complex_data(manifest_with_complex_data):
    """Test parsing manifest with complex data types."""
    manifest = parse_manifest(manifest_with_complex_data)

    assert manifest is not None
    assert manifest["name"] == "Complex Module"
    assert manifest["version"] == "16.0.1.0.0"
    assert len(manifest["depends"]) == 3
    assert "sale" in manifest["depends"]
    assert manifest["author"] == "John Doe, Jane Smith"
    assert manifest["installable"] is True
    assert manifest["auto_install"] is False
    assert manifest["application"] is True
    assert manifest["license"] == "LGPL-3"
    assert isinstance(manifest["data"], list)
    assert len(manifest["data"]) == 2


def test_parse_manifest_handles_syntax_error(manifest_with_syntax_error):
    """Test that syntax errors are handled gracefully."""
    manifest = parse_manifest(manifest_with_syntax_error)
    assert manifest is None  # Should return None, not crash


def test_parse_manifest_no_manifest_file(tmp_path):
    """Test parsing directory without manifest file."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    manifest = parse_manifest(empty_dir)
    assert manifest is None


def test_parse_manifest_not_a_directory(tmp_path):
    """Test parsing a file instead of directory."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("not a directory")

    manifest = parse_manifest(file_path)
    assert manifest is None


# Tests for helper functions

def test_get_manifest_dependencies():
    """Test extracting dependencies from manifest."""
    manifest = {
        "name": "Test",
        "depends": ["base", "sale", "stock"],
    }

    deps = get_manifest_dependencies(manifest)
    assert deps == ["base", "sale", "stock"]


def test_get_manifest_dependencies_empty():
    """Test extracting dependencies when none specified."""
    manifest = {"name": "Test"}

    deps = get_manifest_dependencies(manifest)
    assert deps == []


def test_get_manifest_dependencies_invalid():
    """Test handling invalid depends value."""
    manifest = {"name": "Test", "depends": "not a list"}

    deps = get_manifest_dependencies(manifest)
    assert deps == []


def test_is_module_installable_true():
    """Test checking installable = True."""
    manifest = {"installable": True}
    assert is_module_installable(manifest) is True


def test_is_module_installable_false():
    """Test checking installable = False."""
    manifest = {"installable": False}
    assert is_module_installable(manifest) is False


def test_is_module_installable_default():
    """Test default installable value (should be True)."""
    manifest = {}
    assert is_module_installable(manifest) is True


# Tests for AST conversion functions

def test_ast_node_to_python_string():
    """Test converting AST string node to Python string."""
    node = ast.parse("'hello'", mode="eval").body
    result = _ast_node_to_python(node)
    assert result == "hello"


def test_ast_node_to_python_number():
    """Test converting AST number node to Python number."""
    node = ast.parse("42", mode="eval").body
    result = _ast_node_to_python(node)
    assert result == 42


def test_ast_node_to_python_boolean():
    """Test converting AST boolean nodes."""
    true_node = ast.parse("True", mode="eval").body
    false_node = ast.parse("False", mode="eval").body

    assert _ast_node_to_python(true_node) is True
    assert _ast_node_to_python(false_node) is False


def test_ast_node_to_python_list():
    """Test converting AST list node."""
    node = ast.parse("['a', 'b', 'c']", mode="eval").body
    result = _ast_node_to_python(node)
    assert result == ["a", "b", "c"]


def test_ast_node_to_python_dict():
    """Test converting AST dict node."""
    node = ast.parse("{'key': 'value'}", mode="eval").body
    result = _ast_node_to_python(node)
    assert result == {"key": "value"}


def test_ast_dict_to_python_nested():
    """Test converting nested dict."""
    code = "{'outer': {'inner': 'value'}}"
    node = ast.parse(code, mode="eval").body
    result = _ast_dict_to_python(node)

    assert "outer" in result
    assert isinstance(result["outer"], dict)
    assert result["outer"]["inner"] == "value"


# Integration tests

def test_full_workflow_multiple_modules(temp_odoo_structure):
    """Test complete workflow: find modules and parse all manifests."""
    modules = list(find_modules(temp_odoo_structure))
    manifests = []

    for module_path in modules:
        manifest = parse_manifest(module_path)
        if manifest:
            manifests.append(manifest)

    assert len(manifests) == 3
    assert all("name" in m for m in manifests)
    assert all("version" in m for m in manifests)


def test_encoding_handling(tmp_path):
    """Test handling different file encodings."""
    module = tmp_path / "encoded_module"
    module.mkdir()

    # Create manifest with UTF-8 encoding and special characters
    manifest_content = """
{
    'name': 'Módulo con ñ y acentos',
    'version': '1.0',
    'author': 'José García',
}
"""
    (module / "__manifest__.py").write_text(manifest_content, encoding="utf-8")

    manifest = parse_manifest(module)
    assert manifest is not None
    assert "ñ" in manifest["name"]
    assert "José" in manifest["author"]
