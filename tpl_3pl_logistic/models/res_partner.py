import uuid
from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # --- Products owned by this client ---
    tpl_product_ids = fields.One2many(
        'product.template', 'owner_id', string='3PL Products',
    )
    tpl_product_count = fields.Integer(
        string='Products', compute='_compute_tpl_product_count',
    )

    @api.depends('tpl_product_ids')
    def _compute_tpl_product_count(self):
        for partner in self:
            partner.tpl_product_count = len(partner.tpl_product_ids)

    def action_tpl_view_products(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Products - ' + self.name,
            'res_model': 'product.template',
            'view_mode': 'list,form',
            'domain': [('owner_id', '=', self.id)],
        }

    # --- Client contacts: which 3PL client does this contact belong to? ---
    tpl_client_owner_id = fields.Many2one(
        'res.partner',
        string='3PL Client',
        domain=[('tpl_is_client', '=', True)],
        index=True,
        help='The 3PL client this contact belongs to (delivery addresses, end customers, etc.).',
    )
    tpl_is_client = fields.Boolean(
        string='Is 3PL Client',
        help='Mark this partner as a 3PL client to group contacts under them.',
    )
    tpl_contact_ids = fields.One2many(
        'res.partner', 'tpl_client_owner_id', string='Client Contacts',
    )
    tpl_contact_count = fields.Integer(
        string='Contacts', compute='_compute_tpl_contact_count',
    )

    @api.depends('tpl_contact_ids')
    def _compute_tpl_contact_count(self):
        for partner in self:
            partner.tpl_contact_count = len(partner.tpl_contact_ids)

    def action_tpl_view_contacts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contacts - ' + self.name,
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('tpl_client_owner_id', '=', self.id)],
            'context': {'default_tpl_client_owner_id': self.id},
        }

    # --- Driver / GPS tracking ---
    tpl_is_driver = fields.Boolean(
        string='Is Driver / Truck',
        help='Check this to enable GPS tracking for this contact.',
    )
    tpl_gps_lat = fields.Float(
        string='Latitude', digits=(10, 7),
        help='GPS latitude for truck tracking map.',
    )
    tpl_gps_lng = fields.Float(
        string='Longitude', digits=(10, 7),
        help='GPS longitude for truck tracking map.',
    )
    tpl_gps_updated = fields.Datetime(
        string='GPS Updated',
        help='Last time GPS position was updated.',
    )
    tpl_tracking_token = fields.Char(
        string='Tracking Token', copy=False, readonly=True,
        help='Unique token for mobile GPS tracking page.',
    )
    tpl_tracking_url = fields.Char(
        string='Tracking URL', compute='_compute_tracking_url',
        help='Share this URL with the driver to enable GPS tracking.',
    )

    @api.depends('tpl_tracking_token')
    def _compute_tracking_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for rec in self:
            if rec.tpl_tracking_token:
                rec.tpl_tracking_url = f"{base}/tpl/driver/track/{rec.tpl_tracking_token}"
            else:
                rec.tpl_tracking_url = False

    def action_generate_tracking_token(self):
        for rec in self:
            if not rec.tpl_tracking_token:
                rec.tpl_tracking_token = uuid.uuid4().hex
        return True
