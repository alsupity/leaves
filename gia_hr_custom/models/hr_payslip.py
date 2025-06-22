# -*- coding: utf-8 -*-

from collections import defaultdict
from odoo import fields, models, _
from odoo.tools import float_is_zero, float_compare
from odoo.exceptions import UserError
from markupsafe import Markup


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _action_create_account_move(self):
        # Check if we should use the grouped by component type functionality
        if not self.env.context.get('group_by_component_type', False):
            return super()._action_create_account_move()

        # Add payslip without run
        payslips_to_post = self.filtered(lambda slip: not slip.payslip_run_id)

        # Adding pay slips from a batch and deleting pay slips with a batch that is not ready for validation.
        payslip_runs = (self - payslips_to_post).payslip_run_id
        for run in payslip_runs:
            if run._are_payslips_ready():
                payslips_to_post |= run.slip_ids

        # If no payslips to post, we return
        if not payslips_to_post:
            return super()._action_create_account_move()

        # Group all payslips by journal and month
        # This will allow us to create one move per component type for all payslips
        journal_month_payslips = defaultdict(lambda: defaultdict(lambda: self.env['hr.payslip']))
        for slip in payslips_to_post:
            journal_id = slip.struct_id.journal_id.id
            slip_date = slip.date or fields.Date().end_of(slip.date_to, 'month')
            journal_month_payslips[journal_id][slip_date] |= slip

        # Convert to the format expected by the rest of the code
        all_slip_mapped_data = [journal_month_payslips]

        for slip_mapped_data in all_slip_mapped_data:
            for journal_id in slip_mapped_data:  # For each journal_id.
                for slip_date in slip_mapped_data[journal_id]:  # For each month.
                    # Group lines by component type
                    component_type_lines = defaultdict(list)
                    default_lines = []

                    for slip in slip_mapped_data[journal_id][slip_date]:
                        date = slip_date
                        slip_lines = slip._prepare_slip_lines(date, [])

                        # Group lines by component type
                        for line_vals in slip_lines:
                            # Store the component type ID in a temporary variable
                            component_type_id = line_vals.get('component_type_id', False)
                            # Make a copy of line_vals without component_type_id to avoid modifying the original
                            clean_line_vals = {k: v for k, v in line_vals.items() if k != 'component_type_id'}

                            if component_type_id:
                                component_type_lines[component_type_id].append(clean_line_vals)
                            else:
                                default_lines.append(clean_line_vals)

                    # Create a move for each component type
                    for component_type_id, lines in component_type_lines.items():
                        component_type = self.env['hr.salary.component.type'].browse(component_type_id)
                        move_dict = {
                            'narration': '',
                            'ref': f"{fields.Date().end_of(slip_mapped_data[journal_id][slip_date][0].date_to, 'month').strftime('%B %Y')} - {component_type.name}",
                            'journal_id': journal_id,
                            'date': date,
                        }

                        # Add all payslips to the narration
                        for slip in slip_mapped_data[journal_id][slip_date]:
                            move_dict['narration'] += Markup(f"{slip.number or ''} - {slip.employee_id.name or ''}")
                            move_dict['narration'] += Markup('<br/>')

                        # Process lines exactly like the standard Odoo method
                        # but keep them grouped by component type
                        line_ids = []
                        debit_sum = 0.0
                        credit_sum = 0.0

                        # Group lines by account, name, and analytic distribution
                        # This is similar to how Odoo groups lines in the standard method
                        grouped_lines = {}
                        for line_vals in lines:
                            # Create a key based on account, name, partner, and analytic distribution
                            key = (
                                line_vals['account_id'],
                                line_vals.get('name', ''),
                                line_vals.get('partner_id', False),
                                str(line_vals.get('analytic_distribution', False))
                            )

                            if key in grouped_lines:
                                # Add to existing line
                                grouped_lines[key]['debit'] += line_vals['debit']
                                grouped_lines[key]['credit'] += line_vals['credit']
                            else:
                                # Create a new line
                                grouped_lines[key] = line_vals.copy()

                        # Add grouped lines to line_ids and calculate totals
                        for line_vals in grouped_lines.values():
                            line_ids.append(line_vals)
                            debit_sum += line_vals['debit']
                            credit_sum += line_vals['credit']

                        # The code below is called if there is an error in the balance between credit and debit sum
                        # This is the same logic as in the standard Odoo method
                        precision = self.env['decimal.precision'].precision_get('Payroll')
                        if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                            # We need to add a credit line to balance
                            acc_id = slip_mapped_data[journal_id][slip_date][0].sudo().journal_id.default_account_id.id
                            if not acc_id:
                                raise UserError(_('The Expense Journal "%s" has not properly configured the default Account!',
                                                slip_mapped_data[journal_id][slip_date][0].journal_id.name))

                            adjust_credit = {
                                'name': _('Adjustment Entry'),
                                'partner_id': False,
                                'account_id': acc_id,
                                'journal_id': journal_id,
                                'date': date,
                                'debit': 0.0,
                                'credit': debit_sum - credit_sum,
                            }
                            line_ids.append(adjust_credit)

                        elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                            # We need to add a debit line to balance
                            acc_id = slip_mapped_data[journal_id][slip_date][0].sudo().journal_id.default_account_id.id
                            if not acc_id:
                                raise UserError(_('The Expense Journal "%s" has not properly configured the default Account!',
                                                slip_mapped_data[journal_id][slip_date][0].journal_id.name))

                            adjust_debit = {
                                'name': _('Adjustment Entry'),
                                'partner_id': False,
                                'account_id': acc_id,
                                'journal_id': journal_id,
                                'date': date,
                                'debit': credit_sum - debit_sum,
                                'credit': 0.0,
                            }
                            line_ids.append(adjust_debit)

                        # Add accounting lines to the move
                        # Filter out any lines with zero amounts to avoid empty entries
                        valid_lines = [line for line in line_ids if line['debit'] > 0 or line['credit'] > 0]
                        move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in valid_lines]

                        # Create the move
                        move = self._create_account_move(move_dict)

                        # Link the move to all payslips
                        for slip in slip_mapped_data[journal_id][slip_date]:
                            if not slip.move_id:
                                slip.write({'move_id': move.id, 'date': date})

                    # Create a move for lines without component type
                    if default_lines:
                        move_dict = {
                            'narration': '',
                            'ref': f"{fields.Date().end_of(slip_mapped_data[journal_id][slip_date][0].date_to, 'month').strftime('%B %Y')} - Other",
                            'journal_id': journal_id,
                            'date': date,
                        }

                        for slip in slip_mapped_data[journal_id][slip_date]:
                            move_dict['narration'] += Markup(f"{slip.number or ''} - {slip.employee_id.name or ''}")
                            move_dict['narration'] += Markup('<br/>')

                        # Process lines exactly like the standard Odoo method
                        # but keep them grouped by component type
                        line_ids = []
                        debit_sum = 0.0
                        credit_sum = 0.0

                        # Group lines by account, name, and analytic distribution
                        # This is similar to how Odoo groups lines in the standard method
                        grouped_lines = {}
                        for line_vals in default_lines:
                            # Create a key based on account, name, partner, and analytic distribution
                            key = (
                                line_vals['account_id'],
                                line_vals.get('name', ''),
                                line_vals.get('partner_id', False),
                                str(line_vals.get('analytic_distribution', False))
                            )

                            if key in grouped_lines:
                                # Add to existing line
                                grouped_lines[key]['debit'] += line_vals['debit']
                                grouped_lines[key]['credit'] += line_vals['credit']
                            else:
                                # Create a new line
                                grouped_lines[key] = line_vals.copy()

                        # Add grouped lines to line_ids and calculate totals
                        for line_vals in grouped_lines.values():
                            line_ids.append(line_vals)
                            debit_sum += line_vals['debit']
                            credit_sum += line_vals['credit']

                        # The code below is called if there is an error in the balance between credit and debit sum
                        # This is the same logic as in the standard Odoo method
                        precision = self.env['decimal.precision'].precision_get('Payroll')
                        if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                            # We need to add a credit line to balance
                            acc_id = slip_mapped_data[journal_id][slip_date][0].sudo().journal_id.default_account_id.id
                            if not acc_id:
                                raise UserError(_('The Expense Journal "%s" has not properly configured the default Account!',
                                                slip_mapped_data[journal_id][slip_date][0].journal_id.name))

                            adjust_credit = {
                                'name': _('Adjustment Entry'),
                                'partner_id': False,
                                'account_id': acc_id,
                                'journal_id': journal_id,
                                'date': date,
                                'debit': 0.0,
                                'credit': debit_sum - credit_sum,
                            }
                            line_ids.append(adjust_credit)

                        elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                            # We need to add a debit line to balance
                            acc_id = slip_mapped_data[journal_id][slip_date][0].sudo().journal_id.default_account_id.id
                            if not acc_id:
                                raise UserError(_('The Expense Journal "%s" has not properly configured the default Account!',
                                                slip_mapped_data[journal_id][slip_date][0].journal_id.name))

                            adjust_debit = {
                                'name': _('Adjustment Entry'),
                                'partner_id': False,
                                'account_id': acc_id,
                                'journal_id': journal_id,
                                'date': date,
                                'debit': credit_sum - debit_sum,
                                'credit': 0.0,
                            }
                            line_ids.append(adjust_debit)

                        # Add accounting lines to the move
                        # Filter out any lines with zero amounts to avoid empty entries
                        valid_lines = [line for line in line_ids if line['debit'] > 0 or line['credit'] > 0]
                        move_dict['line_ids'] = [(0, 0, line_vals) for line_vals in valid_lines]

                        # Create the move
                        move = self._create_account_move(move_dict)

                        # Link the move to the payslips
                        for slip in slip_mapped_data[journal_id][slip_date]:
                            if not slip.move_id:
                                slip.write({'move_id': move.id, 'date': date})

        return True

    def _prepare_slip_lines(self, date, line_ids):
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Payroll')
        new_lines = []
        for line in self.line_ids.filtered(lambda line: line.category_id):
            amount = line.total
            if line.code == 'NET':  # Check if the line is the 'Net Salary'.
                for tmp_line in self.line_ids.filtered(lambda line: line.category_id):
                    if tmp_line.salary_rule_id.not_computed_in_net:  # Check if the rule must be computed in the 'Net Salary' or not.
                        if amount > 0:
                            amount -= abs(tmp_line.total)
                        elif amount < 0:
                            amount += abs(tmp_line.total)
            if float_is_zero(amount, precision_digits=precision):
                continue
            debit_account_id = line.salary_rule_id.account_debit.id
            credit_account_id = line.salary_rule_id.account_credit.id

            if debit_account_id:  # If the rule has a debit account.
                debit = amount if amount > 0.0 else 0.0
                credit = -amount if amount < 0.0 else 0.0
                debit_line = self._get_existing_lines(
                    line_ids + new_lines, line, debit_account_id, debit, credit)

                if not debit_line:
                    debit_line = self._prepare_line_values(line, debit_account_id, date, debit, credit)
                    debit_line['tax_ids'] = [(4, tax_id) for tax_id in line.salary_rule_id.account_debit.tax_ids.ids]
                    # Store component type ID if available and we're using the grouped by component type functionality
                    if line.salary_rule_id.component_type_id and self.env.context.get('group_by_component_type', False):
                        debit_line['component_type_id'] = line.salary_rule_id.component_type_id.id
                    new_lines.append(debit_line)
                else:
                    debit_line['debit'] += debit
                    debit_line['credit'] += credit

            if credit_account_id:  # If the rule has a credit account.
                debit = -amount if amount < 0.0 else 0.0
                credit = amount if amount > 0.0 else 0.0
                credit_line = self._get_existing_lines(
                    line_ids + new_lines, line, credit_account_id, debit, credit)

                if not credit_line:
                    credit_line = self._prepare_line_values(line, credit_account_id, date, debit, credit)
                    credit_line['tax_ids'] = [(4, tax_id) for tax_id in line.salary_rule_id.account_credit.tax_ids.ids]
                    # Store component type ID if available and we're using the grouped by component type functionality
                    if line.salary_rule_id.component_type_id and self.env.context.get('group_by_component_type', False):
                        credit_line['component_type_id'] = line.salary_rule_id.component_type_id.id
                    new_lines.append(credit_line)
                else:
                    credit_line['debit'] += debit
                    credit_line['credit'] += credit
        return new_lines
