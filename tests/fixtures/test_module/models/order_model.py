from odoo import models, fields, api


class TestOrder(models.Model):
    _name = 'test.order'
    _description = 'Test Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Order Reference', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    order_line_ids = fields.One2many('test.order.line', 'order_id', string='Order Lines')
    amount_total = fields.Monetary(string='Total', compute='_compute_amount_total')
    currency_id = fields.Many2one('res.currency', string='Currency')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], default='draft', string='Status')

    @api.depends('order_line_ids.price_subtotal')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = sum(record.order_line_ids.mapped('price_subtotal'))


class TestOrderLine(models.Model):
    _name = 'test.order.line'
    _description = 'Test Order Line'

    order_id = fields.Many2one('test.order', string='Order Reference', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    price_unit = fields.Float(string='Unit Price')
    price_subtotal = fields.Monetary(string='Subtotal', compute='_compute_price_subtotal')
    currency_id = fields.Many2one('res.currency', related='order_id.currency_id', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
