from django.test import TestCase
from .jobs import _safe_cell, _preview_hash


class ImportExportContractTests(TestCase):
    def test_contract_module_loaded(self):
        self.assertEqual(_safe_cell('=SUM(A1:A2)'), "'=SUM(A1:A2)")
        self.assertEqual(_safe_cell('plain'), 'plain')

    def test_preview_hash_is_stable_for_structured_rows(self):
        self.assertEqual(_preview_hash([{'b': 2, 'a': 1}]), _preview_hash([{'a': 1, 'b': 2}]))
