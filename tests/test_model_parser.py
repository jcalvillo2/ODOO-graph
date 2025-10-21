"""
Tests para ModelParser.
"""

import pytest
import tempfile
import os
from src.parser import ModelParser


def test_parse_simple_model():
    """Test parsing de un modelo simple."""
    model_content = """
from odoo import models, fields

class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['mail.thread']

    partner_id = fields.Many2one('res.partner', string='Customer')
    amount_total = fields.Monetary(string='Total')
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(model_content)
        f.flush()

        models = ModelParser.parse_file(f.name)

        assert len(models) == 1
        model = models[0]

        assert model.name == 'sale.order'
        assert 'mail.thread' in model.inherits_from
        assert 'partner_id' in model.fields
        assert model.fields['partner_id']['type'] == 'Many2one'
        assert model.fields['partner_id']['relation'] == 'res.partner'

        os.unlink(f.name)


def test_parse_model_without_name():
    """Test parsing de modelo sin _name (solo _inherit)."""
    model_content = """
from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    custom_field = fields.Char(string='Custom Field')
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(model_content)
        f.flush()

        models = ModelParser.parse_file(f.name)

        assert len(models) == 1
        model = models[0]

        # Debe usar el primer _inherit como nombre
        assert model.name == 'sale.order'
        assert 'custom_field' in model.fields

        os.unlink(f.name)


def test_parse_model_with_inherits():
    """Test parsing de modelo con _inherits (delegación)."""
    model_content = """
from odoo import models, fields

class User(models.Model):
    _name = 'res.users'
    _inherits = {'res.partner': 'partner_id'}

    login = fields.Char(string='Login')
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(model_content)
        f.flush()

        models = ModelParser.parse_file(f.name)

        assert len(models) == 1
        model = models[0]

        assert model.name == 'res.users'
        assert 'res.partner' in model.delegates_to
        assert model.delegates_to['res.partner'] == 'partner_id'

        os.unlink(f.name)


def test_parse_nonexistent_file():
    """Test parsing de archivo que no existe."""
    models = ModelParser.parse_file('/nonexistent/path/model.py')
    assert models == []


def test_parse_non_odoo_class():
    """Test parsing de clase que no es un modelo Odoo."""
    content = """
class RegularClass:
    def __init__(self):
        self.value = 42
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(content)
        f.flush()

        models = ModelParser.parse_file(f.name)

        # No debe encontrar modelos
        assert models == []

        os.unlink(f.name)
