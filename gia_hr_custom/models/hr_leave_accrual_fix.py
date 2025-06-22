from odoo import models, api, fields, _
from odoo.exceptions import ValidationError

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.constrains('date_from', 'date_to', 'holiday_status_id', 'holiday_type')
    def _check_validity(self):
        """
        Override to properly handle open-ended allocations (no date_to)
        and accept them regardless of remaining_leaves.
        """
        for leave in self:
            leave_start = fields.Datetime.to_datetime(leave.date_from)
            leave_end = fields.Datetime.to_datetime(leave.date_to)

            # Fetch validated allocations for employee and leave type
            allocations = self.env['hr.leave.allocation'].search([
                ('employee_id', '=', leave.employee_id.id),
                ('holiday_status_id', '=', leave.holiday_status_id.id),
                ('state', '=', 'validate'),
            ])

            # Filter allocations: date range covers leave, and either positive balance or open-ended
            valid_allocs = allocations.filtered(lambda a: (
                (not a.date_from or fields.Datetime.to_datetime(a.date_from) <= leave_start) and
                (not a.date_to or fields.Datetime.to_datetime(a.date_to) >= leave_end) and
                (a.remaining_leaves > 0 or not a.date_to)
            ))

            if not valid_allocs:
                raise ValidationError(_(
                    "There is no valid allocation to cover that request."
                ))