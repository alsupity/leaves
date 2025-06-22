{
    'name': 'Gia HR Custom',
    'version': '1.0',
    'summary': 'Customize and enhance HR',
    'author': 'Gia',
    'category': 'Human Resources',
    'depends': ['hr_contract', 'hr_payroll_account', 'hr_payroll', 'account_accountant', 'hr_holidays','hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_salary_component_type_data.xml',
        'views/hr_contract_views.xml',
        'views/hr_grade_group_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/hr_salary_component_type_views.xml',
        'views/hr_payslip_run_views.xml',
        'views/hr_leave_balance_report_views.xml',

    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
