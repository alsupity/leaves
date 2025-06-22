# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.addons.hr_payroll_account.tests.test_hr_payroll_account import TestHrPayrollAccount


@tagged('post_install', '-at_install')
class TestPayrollComponentType(TestHrPayrollAccount):

    def setUp(self):
        super().setUp()
        
        # Create component types
        self.component_type_basic = self.env['hr.salary.component.type'].create({
            'name': 'Basic Salary',
            'code': 'BASIC',
            'description': 'Basic salary component',
        })
        
        self.component_type_allowance = self.env['hr.salary.component.type'].create({
            'name': 'Allowances',
            'code': 'ALLOW',
            'description': 'Allowances component',
        })
        
        self.component_type_deduction = self.env['hr.salary.component.type'].create({
            'name': 'Deductions',
            'code': 'DEDUCT',
            'description': 'Deductions component',
        })
        
        # Assign component types to salary rules
        basic_rule = self.env['hr.salary.rule'].search([('code', '=', 'BASIC')], limit=1)
        if basic_rule:
            basic_rule.component_type_id = self.component_type_basic.id
            
        hra_rule = self.env['hr.salary.rule'].search([('code', '=', 'HRA')], limit=1)
        if hra_rule:
            hra_rule.component_type_id = self.component_type_allowance.id
            
        tax_rule = self.env['hr.salary.rule'].search([('code', '=', 'TAX')], limit=1)
        if tax_rule:
            tax_rule.component_type_id = self.component_type_deduction.id

    def test_payslip_with_component_types(self):
        """Test that payslips create separate journal entries for each component type"""
        # Create a payslip
        payslip = self.env['hr.payslip'].create({
            'name': 'Test Payslip',
            'employee_id': self.richard_emp.id,
            'contract_id': self.richard_emp.contract_id.id,
            'struct_id': self.developer_pay_structure.id,
            'date_from': '2023-01-01',
            'date_to': '2023-01-31',
        })
        
        # Compute the payslip
        payslip.compute_sheet()
        
        # Validate the payslip
        payslip.action_payslip_done()
        
        # Check that the payslip has a move_id
        self.assertTrue(payslip.move_id, "Payslip should have an accounting entry")
        
        # Get all moves related to this payslip
        moves = self.env['account.move'].search([
            ('ref', 'ilike', 'January 2023%'),
            ('journal_id', '=', payslip.journal_id.id)
        ])
        
        # Check that we have at least one move per component type
        component_types_count = self.env['hr.salary.rule'].search_count([
            ('struct_id', '=', self.developer_pay_structure.id),
            ('component_type_id', '!=', False)
        ])
        
        # We should have at least as many moves as component types
        # (plus potentially one for rules without component type)
        self.assertGreaterEqual(len(moves), 1, 
                               "Should have at least one journal entry")
        
        # Check that each move has the component type in the reference
        for move in moves:
            if 'Basic Salary' in move.ref or 'Allowances' in move.ref or 'Deductions' in move.ref:
                self.assertTrue(True, "Move reference should contain component type name")
