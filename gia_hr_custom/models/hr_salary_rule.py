from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    bank_journal_id = fields.Many2one('account.journal', string='Bank Journal', company_dependent=True)
    component_type_id = fields.Many2one('hr.salary.component.type', string='Component Type')

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    bank_journal_id = fields.Many2one(
        'account.journal',
        string='Bank Journal',
        domain=[('type', '=', 'bank')]
    )

    component_type_id = fields.Many2one('hr.salary.component.type', string='Component Type')

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        if not self.company_id.batch_payroll_move_lines and line.code == "NET":
            partner = self.employee_id.work_contact_id
        else:
            partner = line.partner_id

        vals = {
            'name': line.name,
            'partner_id': partner.id,
            'account_id': account_id,
            'journal_id': line.slip_id.struct_id.journal_id.id,
            'date': date,
            'debit': debit,
            'credit': credit,
            'analytic_distribution': (line.salary_rule_id.analytic_account_id and {
                line.salary_rule_id.analytic_account_id.id: 100}) or
                                     (line.slip_id.contract_id.analytic_account_id.id and {
                                         line.slip_id.contract_id.analytic_account_id.id: 100}),
            'bank_journal_id': line.salary_rule_id.bank_journal_id.id if line.salary_rule_id.bank_journal_id else False,
        }

        # Add component type ID if available and we're using the grouped by component type functionality
        if line.salary_rule_id.component_type_id and self.env.context.get('group_by_component_type', False):
            vals['component_type_id'] = line.salary_rule_id.component_type_id.id
        return vals
