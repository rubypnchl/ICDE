"""Unit tests: synthetic records only; do not establish domain transfer."""
from decimal import Decimal
from pathlib import Path
import json
import unittest

from src.generic_verifier import evaluate_row, evaluate_rows, validate_rule

RULES_PATH = Path(__file__).resolve().parents[1] / 'data/rules/generic_examples.json'
RULES = {r['id']: r for r in json.loads(RULES_PATH.read_text(encoding='utf-8'))['rules']}


class GenericVerifierTests(unittest.TestCase):
    def test_glucose_precision_and_mismatch(self):
        r = RULES['health-glucose-3sig']
        self.assertEqual(evaluate_row(r, {'LBXGLU': 100, 'LBDGLUSI': 5.55}).status, 'satisfied')
        self.assertEqual(evaluate_row(r, {'LBXGLU': 100, 'LBDGLUSI': 5.5}).status, 'violated')
        self.assertEqual(evaluate_row(r, {'LBXGLU': None, 'LBDGLUSI': 5.55}).status, 'abstained')

    def test_finance_sum_and_context(self):
        r = RULES['finance-balance-sheet-candidate']
        row = {'Assets': 100, 'Liabilities': 60, 'StockholdersEquity': 40}
        ctx = {'entity':'A','reporting_date':'2025-12-31','accounting_scope':'consolidated','currency':'USD'}
        row['_field_context'] = {key: dict(ctx) for key in ('Assets','Liabilities','StockholdersEquity')}
        self.assertEqual(evaluate_row(r, row).status, 'satisfied')
        row['_field_context']['StockholdersEquity']['reporting_date'] = '2024-12-31'
        self.assertEqual(evaluate_row(r, row).status, 'abstained')
        del row['_field_context']
        self.assertEqual(evaluate_row(r, row).status, 'abstained')

    def test_cyber_conditional_comparison(self):
        r = RULES['cyber-packet-length-order-candidate']
        base = {' Total Fwd Packets':3, ' Fwd Packet Length Min':5,' Fwd Packet Length Mean':10,' Fwd Packet Length Max':20}
        self.assertEqual(evaluate_row(r, base).status, 'satisfied')
        self.assertEqual(evaluate_row(r, {**base,' Fwd Packet Length Max':9}).status, 'violated')
        self.assertEqual(evaluate_row(r, {**base,' Total Fwd Packets':0}).status, 'not_applicable')
        self.assertEqual(evaluate_row(r, {**base,' Total Fwd Packets':None}).status, 'abstained')

    def test_manufacturing_categorical_context(self):
        r = RULES['manufacturing-nonnegative-torque-conditional-demo']
        self.assertEqual(evaluate_row(r, {'Type':'L','Torque [Nm]':5}).status, 'satisfied')
        self.assertEqual(evaluate_row(r, {'Type':'L','Torque [Nm]':-2}).status, 'violated')
        self.assertEqual(evaluate_row(r, {'Type':'M','Torque [Nm]':-2}).status, 'not_applicable')

    def test_summary_counts_and_denominator(self):
        rule = RULES['cyber-packet-length-order-candidate']
        base = {' Total Fwd Packets':2,' Fwd Packet Length Min':5, ' Fwd Packet Length Mean':8,' Fwd Packet Length Max':10}
        result = evaluate_rows(rule,[base,{**base,' Total Fwd Packets':0},{**base,' Fwd Packet Length Mean':None},{**base,' Fwd Packet Length Mean':30}])
        self.assertEqual(result['counts'],{'satisfied':1,'violated':1,'not_applicable':1,'abstained':1})
        self.assertEqual(result['eligible_records'],3)
        self.assertAlmostEqual(result['coverage_on_eligible'],2/3)

    def test_unknown_expression_cannot_execute(self):
        r = json.loads(json.dumps(RULES['health-glucose-3sig']))
        r['assertions'][0]['right'] = {'python':'__import__("os").system("echo unsafe")'}
        with self.assertRaises(ValueError):
            validate_rule(r)

    def test_nonfinite_values_abstain(self):
        r = RULES['health-glucose-3sig']
        self.assertEqual(evaluate_row(r, {'LBXGLU':float('nan'),'LBDGLUSI':5}).status,'abstained')
        self.assertEqual(evaluate_row(r, {'LBXGLU':float('inf'),'LBDGLUSI':5}).status,'abstained')

    def test_partial_condition_groups_use_three_valued_logic(self):
        r = json.loads(json.dumps(RULES['manufacturing-nonnegative-torque-conditional-demo']))
        r['when'] = {'all': [
            {'column':'Missing', 'op':'eq', 'value':'L'},
            {'column':'Type', 'op':'eq', 'value':'M'}]}
        self.assertEqual(evaluate_row(r, {'Type':'L', 'Torque [Nm]':5}).status,'not_applicable')
        self.assertEqual(evaluate_row(r, {'Type':'M', 'Torque [Nm]':5}).status,'abstained')
        r['when'] = {'any': [
            {'column':'Missing', 'op':'eq', 'value':'L'},
            {'column':'Type', 'op':'eq', 'value':'M'}]}
        self.assertEqual(evaluate_row(r, {'Type':'M', 'Torque [Nm]':5}).status,'satisfied')
        self.assertEqual(evaluate_row(r, {'Type':'L', 'Torque [Nm]':5}).status,'abstained')

    def test_conditional_unsupported_comparator_rejected(self):
        r = json.loads(json.dumps(RULES['manufacturing-nonnegative-torque-conditional-demo']))
        r['when']['op']='is_approximately'
        with self.assertRaises(ValueError):
            validate_rule(r)

    def test_missing_context_column_abstain_even_if_numeric_identity_holds(self):
        r = RULES['finance-balance-sheet-candidate']
        row = {'Assets':100,'Liabilities':60,'StockholdersEquity':40,
               '_field_context':{'Assets':{'entity':'A','reporting_date':'2025','accounting_scope':'consolidated','currency':'USD'}}}
        self.assertEqual(evaluate_row(r,row).status,'abstained')

    def test_rounding_mode_is_explicit_and_distinct(self):
        r = json.loads(json.dumps(RULES['health-glucose-3sig']))
        row = {'LBXGLU':100,'LBDGLUSI':5.55}
        self.assertEqual(evaluate_row(r,row).status,'satisfied')
        r['assertions'][0]['round_right'] = {'mode':'decimal_places','digits':3}
        self.assertEqual(evaluate_row(r,row).status,'violated')


if __name__ == '__main__':
    unittest.main()
