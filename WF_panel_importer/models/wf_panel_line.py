from odoo import models, fields

class WFPanelLine(models.Model):
    _name = 'wf.panel.line'
    _description = 'WF Panel Line'
    _order = 'sequence, id'

    panel_id = fields.Many2one('wf.panel', string='Panel', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    label = fields.Char('Label')
    member = fields.Char('Member')
    description = fields.Char('Description')
    qty = fields.Float('Quantity')
    length = fields.Char('Length')
    width = fields.Char('Width')
