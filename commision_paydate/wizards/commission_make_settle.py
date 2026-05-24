# Copyright 2022 Quartile
# Copyright 2014-2022 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class CommissionMakeSettle(models.TransientModel):
    _inherit = "commission.make.settle"

    settlement_type = fields.Selection(
        default='sale_invoice'
    )

    payment_date_type = fields.Selection([
            ('payment_date', 'Payment Date'),
            ('invoice_date', 'Invoice Date')
        ], default='payment_date')
    _order = "payment_date asc"



    def action_settle(self):
        self.ensure_one()
        settlement_obj = self.env["commission.settlement"]
        settlement_line_obj = self.env["commission.settlement.line"]
        settlement_ids = []
        if self.agent_ids:
            agents = self.agent_ids
        else:
            agents = self.env["res.partner"].search([("agent", "=", True)])
        date_to = self.date_to
        for agent in agents:
            date_to_agent = self._get_period_start(agent, date_to)
            # Get non settled elements
            agent_lines = self._get_agent_lines(agent, date_to_agent)
            for company in agent_lines.mapped("company_id"):
                agent_lines_company = agent_lines.filtered(
                    lambda r: r.object_id.company_id == company
                )
                pos = 0
                sett_to = date(year=1900, month=1, day=1)
                while pos < len(agent_lines_company):
                    line = agent_lines_company[pos]
                    pos += 1
                    if line._skip_settlement():
                        continue
                    if self.payment_date_type == 'payment_date':
                        if not isinstance(line.payment_date, bool):
                            if line.payment_date > sett_to:
                                sett_from = self._get_period_start(agent, line.payment_date)
                                sett_to = self._get_next_period_date(agent, sett_from)
                                sett_to -= timedelta(days=1)
                                settlement = self._get_settlement(
                                    agent, company, sett_from, sett_to
                                )
                                if not settlement:
                                    settlement = settlement_obj.create(
                                        self._prepare_settlement_vals(
                                            agent, company, sett_from, sett_to
                                        )
                                    )
                                settlement_ids.append(settlement.id)
                    else:
                        if line.invoice_date > sett_to:
                            sett_from = self._get_period_start(agent, line.invoice_date)
                            sett_to = self._get_next_period_date(agent, sett_from)
                            sett_to -= timedelta(days=1)
                            settlement = self._get_settlement(
                                agent, company, sett_from, sett_to
                            )
                            if not settlement:
                                settlement = settlement_obj.create(
                                    self._prepare_settlement_vals(
                                        agent, company, sett_from, sett_to
                                    )
                                )
                            settlement_ids.append(settlement.id)
                    # TODO: Do creates in batch
                    settlement_line_obj.create(
                        self._prepare_settlement_line_vals(settlement, line)
                    )
        # go to results
        if len(settlement_ids):
            return {
                "name": _("Created Settlements"),
                "type": "ir.actions.act_window",
                "views": [[False, "list"], [False, "form"]],
                "res_model": "commission.settlement",
                "domain": [["id", "in", settlement_ids]],
            }

    def _prepare_settlement_line_vals(self, settlement, line):
        """Prepare extra settlement values when the source is a sales invoice agent
        line.
        """
        res = super()._prepare_settlement_line_vals(settlement, line)
        if self.settlement_type == "sale_invoice":
            if self.payment_date_type == 'payment_date':
                if not isinstance(line.payment_date, bool):
                    res.update(
                        {
                            "invoice_agent_line_id": line.id,
                            "date": line.invoice_date,
                            "commission_id": line.commission_id.id,
                            "settled_amount": line.amount,
                            "payment_date": line.payment_date,
                        }
                    )
            else:
                if self.settlement_type == "sale_invoice":
                    res.update(
                        {
                            "invoice_agent_line_id": line.id,
                            "date": line.invoice_date,
                            "commission_id": line.commission_id.id,
                            "settled_amount": line.amount,
                        }
                    )
        return res

    def _get_agent_lines(self, agent, date_to_agent):
        """Filter sales invoice agent lines for this type of settlement."""
        if self.settlement_type != "sale_invoice":
            return super()._get_agent_lines(agent, date_to_agent)
        if self.payment_date_type == 'payment_date':
            return self.env["account.invoice.line.agent"].search(
                [
                    ("payment_date", "<", date_to_agent),
                    ("agent_id", "=", agent.id),
                    ("settled", "=", False),
                ],
                order="invoice_date",
            )
        else:
            return self.env["account.invoice.line.agent"].search(
                [
                    ("invoice_date", "<", date_to_agent),
                    ("agent_id", "=", agent.id),
                    ("settled", "=", False),
                ],
                order="invoice_date",
            )
