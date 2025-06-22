# -*- coding: utf-8 -*-

from odoo import fields, models, tools


class HrLeaveBalanceReport(models.Model):
    _name = 'hr.leave.balance.report'
    _description = 'Leave Balance Report'
    _auto = False
    _order = 'employee_id, holiday_status_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    holiday_status_id = fields.Many2one('hr.leave.type', string='Time Off Type', readonly=True)
    allocated_days = fields.Float(string='Allocated', readonly=True)
    taken_days = fields.Float(string='Taken', readonly=True)
    remaining_days = fields.Float(string='Remaining', readonly=True)
    date_from = fields.Datetime(string='Start Date', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'hr_leave_balance_report')
        self._cr.execute("""
            CREATE OR REPLACE VIEW hr_leave_balance_report AS (
                SELECT
                    row_number() OVER(ORDER BY lr.employee_id, lr.holiday_status_id) AS id,
                    lr.employee_id AS employee_id,
                    lr.holiday_status_id AS holiday_status_id,
                    lr.company_id AS company_id,
                    MIN(lr.date_from) AS date_from,
                    SUM(CASE WHEN lr.leave_type = 'allocation' THEN lr.number_of_days ELSE 0 END) AS allocated_days,
                    SUM(CASE WHEN lr.leave_type = 'request' THEN -lr.number_of_days ELSE 0 END) AS taken_days,
                    SUM(lr.number_of_days) AS remaining_days
                FROM hr_leave_report lr
                JOIN hr_leave_type lt ON lt.id = lr.holiday_status_id
                WHERE lr.state = 'validate'
                  AND lt.requires_allocation = 'yes'
                GROUP BY lr.employee_id, lr.holiday_status_id, lr.company_id
            )
        """)

