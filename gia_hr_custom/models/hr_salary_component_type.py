# -*- coding: utf-8 -*-

from odoo import fields, models


class HrSalaryComponentType(models.Model):
    _name = 'hr.salary.component.type'
    _description = 'Salary Component Type'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The code must be unique!')
    ]
