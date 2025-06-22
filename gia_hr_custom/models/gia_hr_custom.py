from odoo import models, fields

class JobGrade(models.Model):
    _name = 'hr.job.grade'
    _description = 'Employee Grade'

    name = fields.Char(string="Job Grade", required=True)

class EmployeeGroup(models.Model):
    _name = 'hr.employee.group'
    _description = 'Employee Group'

    name = fields.Char(string="Group Name", required=True)

class HrContract(models.Model):
    _inherit = 'hr.contract'

    job_grade_id = fields.Many2one('hr.job.grade', string="Employee Grade")
    employee_group_id = fields.Many2one('hr.employee.group', string="Employee Group")
    hiring_date = fields.Date(string='Hiring Date', required=False, help="The date when the employee was hired.")
