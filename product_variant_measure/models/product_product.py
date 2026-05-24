from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import sql


def _normalize_value_name(raw_name, uom, splitter):
    if not raw_name or not uom:
        return raw_name
    magnitude, unit_label = splitter(raw_name)
    if magnitude is None:
        stripped = raw_name.strip()
        try:
            magnitude = float(stripped.replace(",", "."))
        except ValueError:
            return raw_name
        unit_label = ""
    if unit_label:
        return raw_name
    magnitude_str = "{:g}".format(magnitude)
    return f"{magnitude_str} {uom.name}"


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    uom_category_id = fields.Many2one(
        "uom.category",
        string="Unit Category",
        help="Restrict attribute values to units from this category.",
    )

    def write(self, vals):
        res = super().write(vals)
        if "uom_category_id" in vals:
            self.mapped("value_ids")._check_value_matches_uom()
        return res


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Standard unit represented by this attribute value.",
    )

    @api.model
    def _auto_init(self):
        super()._auto_init()
        sql.drop_constraint(self._cr, self._table, "product_attribute_value_attribute_uom_unique")
        self.env.cr.execute(
            "DELETE FROM ir_model_constraint WHERE name = %s",
            ("product_attribute_value_attribute_uom_unique",),
        )

    @staticmethod
    def _split_quantity_unit(value_name):
        """Return (magnitude, unit_label) if the name looks like "1.2 m"."""
        if not value_name:
            return None, None
        parts = value_name.strip().split()
        if len(parts) < 2:
            return None, None
        try:
            magnitude = float(parts[0].replace(",", "."))
        except ValueError:
            return None, None
        unit_label = " ".join(parts[1:]).strip()
        return magnitude, unit_label

    def _check_value_matches_uom(self):
        if (not self.env.registry.ready
                or self.env.context.get("install_mode")
                or self.env.context.get("skip_variant_measure_validation")):
            return
        for value in self:
            attribute = value.attribute_id
            if not attribute.uom_category_id:
                continue
            if not value.uom_id:
                raise ValidationError(
                    _("Select a unit of measure for attribute '%s'.")
                    % attribute.display_name
                )
            if value.uom_id.category_id != attribute.uom_category_id:
                raise ValidationError(
                    _(
                        "Unit '%(uom)s' does not belong to the category of attribute '%(attribute)s'."
                    )
                    % {
                        "uom": value.uom_id.display_name,
                        "attribute": attribute.display_name,
                    }
                )
            magnitude, unit_label = self._split_quantity_unit(value.name)
            if magnitude is None:
                raise ValidationError(
                    _(
                        "Value '%(value)s' must start with a numeric magnitude followed by the unit name."
                    )
                    % {"value": value.display_name}
                )
            if magnitude <= 0:
                raise ValidationError(
                    _("Numeric magnitude must be greater than zero for attribute '%s'.")
                    % attribute.display_name
                )
            if unit_label.lower() != value.uom_id.name.lower():
                raise ValidationError(
                    _(
                        "Unit '%(unit)s' in value '%(value)s' must match the selected unit '%(expected)s'."
                    )
                    % {
                        "unit": unit_label,
                        "value": value.display_name,
                        "expected": value.uom_id.name,
                    }
                )
            rounding = value.uom_id.rounding or 0.0
            if rounding:
                quotient = magnitude / rounding
                if abs(quotient - round(quotient)) > 1e-9:
                    raise ValidationError(
                        _(
                            "Numeric magnitude must align with the rounding ('%(rounding)s') of unit '%(unit)s'."
                        )
                        % {
                            "rounding": value.uom_id.rounding,
                            "unit": value.uom_id.display_name,
                        }
                    )

    @api.model_create_multi
    def create(self, vals_list):
        ctx_attribute_id = self.env.context.get("default_attribute_id")
        for vals in vals_list:
            attribute_id = vals.get("attribute_id") or ctx_attribute_id
            uom_id = vals.get("uom_id")
            if attribute_id and uom_id:
                attribute = self.env["product.attribute"].browse(attribute_id)
                if attribute.uom_category_id:
                    uom = self.env["uom.uom"].browse(uom_id)
                    vals["name"] = _normalize_value_name(vals.get("name"), uom, self._split_quantity_unit)
        records = super().create(vals_list)
        records._check_value_matches_uom()
        return records

    def write(self, vals):
        relevant = {"name", "uom_id", "attribute_id"}.intersection(vals.keys())
        if relevant:
            for record in self:
                new_vals = vals.copy()
                attribute = record.attribute_id
                if "attribute_id" in new_vals:
                    attribute = self.env["product.attribute"].browse(new_vals["attribute_id"])
                uom = record.uom_id
                if "uom_id" in new_vals:
                    uom = self.env["uom.uom"].browse(new_vals["uom_id"])
                if attribute.uom_category_id and uom:
                    raw_name = new_vals.get("name", record.name)
                    new_vals["name"] = _normalize_value_name(raw_name, uom, self._split_quantity_unit)
                super(ProductAttributeValue, record).write(new_vals)
            self._check_value_matches_uom()
            return True
        res = super().write(vals)
        if relevant:
            self._check_value_matches_uom()
        return res
