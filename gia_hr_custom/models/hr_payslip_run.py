# -*- coding: utf-8 -*-

from odoo import models, _


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_validate_grouped(self):
        """
        Create draft entries with payslip lines grouped by component type.
        This is a custom implementation that creates one journal entry per component type.
        """
        # Get all payslips that are not in draft or cancel state
        payslips_to_validate = self.mapped('slip_ids').filtered(lambda slip: slip.state not in ['draft', 'cancel'])

        # Call the custom method to create grouped accounting entries
        if payslips_to_validate:
            payslips_to_validate.with_context(group_by_component_type=True).action_payslip_done()

        # Close the batch
        self.action_close()

        return True
