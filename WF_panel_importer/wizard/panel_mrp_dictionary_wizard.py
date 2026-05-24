"""Wizard to build a cut-list dictionary and MRP BOM for a wf.panel.section.

Cut-type logic
--------------
Each component from the SVG carries three dimension attributes:
  - data_length  : the cut length (always meaningful)
  - data_width   : the narrow profile dimension for lumber (1.5" for 2x lumber)
                   OR the sheet width for panel goods (48" for 4x8 sheet)
  - data_depth   : the deeper profile dimension for lumber (5.5" for 2x6)
                   OR the thickness for sheet goods (0.4375" for 7/16 OSB)

Rule:
  * If data_depth >= data_width  →  lumber  →  LENGTH-ONLY cut
      (width is the profile, not a cut dimension)
  * Otherwise                   →  sheet / panel  →  LENGTH × WIDTH cut

Products created for BOM lines
-------------------------------
Temporary (consu) products are found-or-created using a name that encodes
the cut dimensions.  No new product attributes are created.

  length-only   : "<lumber_type> - <length>in [TEMP]"
  length×width  : "<lumber_type> - <length>x<width>in [TEMP]"

If the user selects a Base Product on a line, its name replaces <lumber_type>.
"""
from __future__ import annotations

import re
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────
_LABEL_PREFIX_RE = re.compile(r'^[A-Za-z]_')
_SEQ_SUFFIX_RE = re.compile(r'_\d+$')

# Patterns to extract a stock length from a product name (tried in order):
#   144in  /  144 in
#   12ft   /  12 ft  /  12'  /  12 feet   → multiply by 12
#   trailing bare number                   → assume inches
_LEN_INCHES_RE = re.compile(r'(\d+(?:\.\d+)?)\s*in\b', re.IGNORECASE)
_LEN_FEET_RE   = re.compile(r'(\d+(?:\.\d+)?)\s*(?:ft|feet|\')\b', re.IGNORECASE)
_LEN_BARE_RE   = re.compile(r'(\d+(?:\.\d+)?)\s*$')


def _parse_stock_length_inches(name: str) -> float | None:
    """Extract a stock length in inches from a product name, or None."""
    m = _LEN_INCHES_RE.search(name)
    if m:
        return float(m.group(1))
    m = _LEN_FEET_RE.search(name)
    if m:
        return round(float(m.group(1)) * 12, 4)
    m = _LEN_BARE_RE.search(name)
    if m:
        return float(m.group(1))
    return None

# Words that describe the structural role of a piece, not the material type.
# These are stripped before searching for a matching product.
_ROLE_WORDS = {
    'stud', 'plate', 'jack', 'king', 'top', 'bottom', 'vtp',
    'cripple', 'header', 'flat', 'corner', 'trimmer', 'double',
    'triple', 'single', 'full', 'half', 'filler',
}


def _parse_lumber_type(data_id: str | None) -> str | None:
    """Extract the human-readable lumber type from a component data_id.

    'D_King_Stud_2x6_SPF_No_2_1' → 'King Stud 2x6 SPF No 2'
    """
    if not data_id:
        return None
    name = _LABEL_PREFIX_RE.sub('', data_id.strip())
    name = _SEQ_SUFFIX_RE.sub('', name)
    return name.replace('_', ' ')


def _cut_type(data_length: float, data_width: float, data_depth: float) -> str:
    """Return 'length_only' or 'length_width'.

    Lumber has a non-zero depth (the profile, e.g. 5.5" for 2x6).
    If depth is present → the piece is lumber → length-only cut.

    Sheet goods have no depth but do have a width (e.g. 48" for a 4x8 sheet).
    If depth is absent/zero and width is present → length × width cut.
    """
    if data_depth > 0:
        return 'length_only'
    if data_width > 0 and data_length > 0:
        return 'length_width'
    return 'length_only'


# ── Wizard ───────────────────────────────────────────────────────────────────

class PanelMrpDictionaryWizard(models.TransientModel):
    _name = 'panel.mrp.dictionary.wizard'
    _description = 'Panel MRP Cut Dictionary'

    section_id = fields.Many2one(
        'wf.panel.section',
        string='Section',
        readonly=True,
    )
    line_ids = fields.One2many(
        'panel.mrp.dictionary.line',
        'wizard_id',
        string='Cut Lines',
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        ctx = self.env.context
        if ctx.get('active_model') == 'wf.panel.section' and ctx.get('active_id'):
            records.section_id = ctx['active_id']
        return records

    def action_panel_mrp_dictionary_wizard(self):
        """Populate the cut-list dictionary from the section components."""
        self.ensure_one()
        if not self.section_id:
            return
        self._build_cut_lines()

    def _build_cut_lines(self):
        self.line_ids.unlink()

        # key → qty counter
        groups: dict[tuple, dict] = {}

        for comp in self.section_id.component_ids:
            lumber_type = _parse_lumber_type(comp.data_id)
            if not lumber_type:
                continue

            length = round(comp.data_length or 0.0, 4)
            width = round(comp.data_width or 0.0, 4)
            depth = round(comp.data_depth or 0.0, 4)
            ctype = _cut_type(length, width, depth)

            # For length-only cuts the width is a profile dimension, not a cut axis
            cut_width = width if ctype == 'length_width' else 0.0

            key = (lumber_type, ctype, length, cut_width)
            if key in groups:
                groups[key]['qty'] += 1
            else:
                groups[key] = {
                    'lumber_type': lumber_type,
                    'cut_type': ctype,
                    'length': length,
                    'width': cut_width,
                    'qty': 1,
                }

        Line = self.env['panel.mrp.dictionary.line']
        for _key, vals in sorted(
            groups.items(),
            key=lambda kv: (kv[1]['lumber_type'], kv[1]['cut_type'], kv[1]['length']),
        ):
            Line.create({
                'wizard_id': self.id,
                'lumber_type': vals['lumber_type'],
                'cut_type': vals['cut_type'],
                'length': vals['length'],
                'width': vals['width'],
                'qty': vals['qty'],
            })

    def action_create_bom(self):
        """Create (or refresh) a BOM for the section using temporary cut products."""
        self.ensure_one()
        section = self.section_id
        if not section:
            return {'type': 'ir.actions.act_window_close'}

        panel = section.project_id
        finished_product = panel._ensure_manufactured_product(section)
        if not finished_product:
            _logger.warning(
                'action_create_bom: no finished product for section %s', section.name
            )
            return {'type': 'ir.actions.act_window_close'}

        BomModel = self.env['mrp.bom']
        BomLine = self.env['mrp.bom.line']
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)

        # Find or create the BOM header
        bom = BomModel.search(
            [('product_tmpl_id', '=', finished_product.product_tmpl_id.id)],
            limit=1,
        )
        if bom:
            bom.bom_line_ids.unlink()
            bom.write({'code': section.name})
        else:
            bom = BomModel.create({
                'product_tmpl_id': finished_product.product_tmpl_id.id,
                'product_qty': 1.0,
                'type': 'normal',
                'code': section.name,
            })

        # Create BOM lines only for lines where the base product to cut exists
        skipped = 0
        for line in self.line_ids:
            base_product = line._get_base_product()
            if not base_product:
                skipped += 1
                _logger.info(
                    'action_create_bom: skipping %s — base product not found',
                    line.lumber_type,
                )
                continue
            cut_product = line._find_or_create_cut_product(base_product)
            BomLine.create({
                'bom_id': bom.id,
                'product_id': cut_product.id,
                'product_qty': float(line.qty),
                'product_uom_id': (cut_product.uom_id or uom_unit).id,
            })
        if skipped:
            _logger.warning(
                'action_create_bom: %d line(s) skipped — base product not found', skipped
            )

        # Link the BOM back to the section's parent panel
        if not panel.bom_id:
            panel.bom_id = bom.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'BOM',
            'res_model': 'mrp.bom',
            'res_id': bom.id,
            'view_mode': 'form',
            'target': 'current',
        }


# ── Wizard lines ─────────────────────────────────────────────────────────────

class PanelMrpDictionaryLine(models.TransientModel):
    _name = 'panel.mrp.dictionary.line'
    _description = 'Panel MRP Cut Dictionary Line'
    _order = 'lumber_type, cut_type, length, width'

    wizard_id = fields.Many2one(
        'panel.mrp.dictionary.wizard',
        required=True,
        ondelete='cascade',
    )
    lumber_type = fields.Char('Lumber Type', readonly=True)
    cut_type = fields.Selection(
        [
            ('length_only', 'Length Only'),
            ('length_width', 'Length × Width'),
        ],
        string='Cut Type',
        readonly=True,
    )
    length = fields.Float('Length (in)', digits=(16, 4), readonly=True)
    width = fields.Float('Width (in)', digits=(16, 4), readonly=True)
    qty = fields.Integer('Qty', readonly=True)
    base_product_id = fields.Many2one(
        'product.product',
        string='Base Product',
        domain=[('type', '=', 'consu')],
        help=(
            'Select the existing product that will be cut. '
            'If left empty the module searches by lumber type name. '
            'Lines without a matching product are excluded from the BOM.'
        ),
    )
    base_product_exists = fields.Boolean(
        string='Product Found',
        compute='_compute_base_product_exists',
        store=False,
    )
    cut_product_name = fields.Char(
        'Cut Product Name',
        compute='_compute_cut_product_name',
        store=False,
    )

    @api.depends('base_product_id', 'lumber_type')
    def _compute_base_product_exists(self):
        for line in self:
            line.base_product_exists = bool(line._get_base_product())

    @api.depends('base_product_id', 'lumber_type', 'cut_type', 'length', 'width')
    def _compute_cut_product_name(self):
        for line in self:
            base_product = line._get_base_product()
            if not base_product:
                line.cut_product_name = '— no matching product —'
                continue
            base = base_product.name
            if line.cut_type == 'length_width':
                line.cut_product_name = (
                    f"{base} - {line.length:.4g}x{line.width:.4g}in [TEMP]"
                )
            else:
                line.cut_product_name = f"{base} - {line.length:.4g}in [TEMP]"

    def _get_base_product(self):
        """Return the existing product that will be cut, or False if not found.

        1. Explicit base_product_id → use it directly.
        2. Fuzzy token search: strips role words (King, Stud, Flat, Plate, …)
           and keeps material tokens (2x6, SPF, No, 2).
           Among all candidates, picks the shortest stock whose length in the
           product name is >= the required cut length.
           If none is long enough, returns False so the line is skipped.
        """
        self.ensure_one()
        if self.base_product_id:
            return self.base_product_id
        if not self.lumber_type:
            return self.env['product.product']

        tokens = [
            t for t in self.lumber_type.split()
            if t.lower() not in _ROLE_WORDS
            and len(t) > 2
            and not t.isdigit()
        ]
        if not tokens:
            return self.env['product.product']

        domain = [('type', '=', 'consu')]
        for token in tokens:
            domain.append(('name', 'ilike', token))

        candidates = self.env['product.product'].search(domain)
        if not candidates:
            return self.env['product.product']

        # Pick shortest stock length that is still >= the required cut length
        cut_length = self.length or 0.0
        parsed = []
        for p in candidates:
            stock_len = _parse_stock_length_inches(p.name)
            parsed.append((stock_len, p))
            _logger.debug('_get_base_product: candidate "%s" → stock_len=%s', p.name, stock_len)

        # candidates with a parseable length >= cut
        viable = sorted(
            [(l, p) for l, p in parsed if l is not None and l >= cut_length],
            key=lambda x: x[0],
        )
        if viable:
            return viable[0][1]   # shortest stock that fits

        # no stock long enough found
        return self.env['product.product']

    def _find_or_create_cut_product(self, base_product=None):
        """Return a (temp) product.product matching this cut line's dimensions.

        ``base_product`` must be an existing product.product that this cut
        comes from.  Its name is used as the prefix of the temp product name.
        """
        self.ensure_one()
        if base_product is None:
            base_product = self._get_base_product()
        base = base_product.name if base_product else (self.lumber_type or 'Unknown')
        if self.cut_type == 'length_width':
            cut_name = f"{base} - {self.length:.4g}x{self.width:.4g}in [TEMP]"
        else:
            cut_name = f"{base} - {self.length:.4g}in [TEMP]"

        Product = self.env['product.product'].sudo()
        product = Product.search([('name', '=', cut_name)], limit=1)
        if not product:
            product = Product.create({
                'name': cut_name,
                'type': 'consu',
            })
            _logger.info('Created temporary cut product: %s', cut_name)
        return product
