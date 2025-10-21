"""
Tests para ManifestParser.
"""

import pytest
import tempfile
import os
from pathlib import Path
from src.parser import ManifestParser


def test_parse_valid_manifest():
    """Test parsing de un __manifest__.py válido."""
    manifest_content = """
{
    'name': 'Test Module',
    'version': '16.0.1.0',
    'depends': ['base', 'sale'],
    'category': 'Test',
    'installable': True,
}
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(manifest_content)
        f.flush()

        result = ManifestParser.parse(f.name)

        assert result is not None
        assert result['name'] == 'Test Module'
        assert result['version'] == '16.0.1.0'
        assert result['depends'] == ['base', 'sale']
        assert result['category'] == 'Test'
        assert result['installable'] is True

        os.unlink(f.name)


def test_parse_nonexistent_file():
    """Test parsing de archivo que no existe."""
    result = ManifestParser.parse('/nonexistent/path/__manifest__.py')
    assert result is None


def test_parse_invalid_manifest():
    """Test parsing de archivo con sintaxis inválida."""
    manifest_content = """
{
    'name': 'Test Module'
    'version': '16.0.1.0',  # Falta coma
}
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(manifest_content)
        f.flush()

        result = ManifestParser.parse(f.name)

        # Debe retornar None en caso de error
        assert result is None

        os.unlink(f.name)
