from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    test_order_ids = fields.One2many('test.order', 'partner_id', string='Test Orders')
    test_order_count = fields.Integer(string='Test Order Count', compute='_compute_test_order_count')

    def _compute_test_order_count(self):
        for partner in self:
            partner.test_order_count = len(partner.test_order_ids)
