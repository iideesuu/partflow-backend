import csv
import io
import json
from decimal import Decimal

from django.test import TestCase, override_settings

from .export_service import export_rows, render_export
from .models import BOM, BOMItem, BOMRevision, Part, PartRevision, Unit


class ExportServiceContractTests(TestCase):
    def setUp(self):
        self.unit = Unit.objects.create(code="EXP-EA", name="Each", dimension="count")
        self.part_a = self._part("EXP-A", "Alpha", tenant="tenant-a", description="=SUM(A1:A2)")
        self.part_b = self._part("EXP-B", "Beta", tenant="tenant-b")
        self.child = self._part("EXP-CHILD", "Child", tenant="tenant-a")
        self.bom = BOM.objects.create(tenant_id="tenant-a", bom_code="EXP-BOM", name="Export BOM")
        self.bom_rev = BOMRevision.objects.create(
            bom=self.bom, revision="A", root_part_revision=self.part_a, revision_state="released"
        )

    def _part(self, code, name, *, tenant, description=""):
        part = Part.objects.create(tenant_id=tenant, part_code=code)
        return PartRevision.objects.create(
            part=part, revision="A", revision_seq=1, name=name,
            description=description, unit=self.unit, revision_state="released"
        )

    def test_part_export_is_tenant_scoped_and_filterable(self):
        header, rows = export_rows("part", {"q": "Alpha"}, "tenant-a")
        values = list(rows)
        self.assertIn("part_code", header)
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0][0], "EXP-A")
        _, other_rows = export_rows("part", {}, "tenant-b")
        self.assertEqual([row[0] for row in other_rows], ["EXP-B"])

    def test_unknown_filter_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "UNKNOWN_EXPORT_FILTER"):
            export_rows("part", {"secret_lookup": "x"}, "tenant-a")

    def test_nested_bom_reference_does_not_require_child_part(self):
        child_bom = BOM.objects.create(tenant_id="tenant-a", bom_code="EXP-CHILD-BOM")
        child_rev = BOMRevision.objects.create(
            bom=child_bom, revision="B", root_part_revision=self.child, revision_state="released"
        )
        BOMItem.objects.create(
            bom_revision=self.bom_rev, line_no=1, child_bom_revision=child_rev,
            quantity=Decimal("2.500000"), unit=self.unit, position="P1",
        )
        header, rows = export_rows("bom", {"bom_code": "EXP-BOM"}, "tenant-a")
        record = dict(zip(header, next(iter(rows))))
        self.assertEqual(record["child_part_code"], "")
        self.assertEqual(record["child_bom_code"], "EXP-CHILD-BOM")
        self.assertEqual(record["child_bom_revision"], "B")

    def test_csv_formula_escape_and_frozen_dialect(self):
        body, count, content_type = render_export("part", "csv", {}, "tenant-a")
        self.assertEqual(count, 2)  # root and child revisions in tenant-a
        self.assertEqual(content_type, "text/csv; charset=utf-8")
        self.assertTrue(body.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(body[3:].decode("utf-8"))))
        self.assertEqual(rows[0][0], "part_code")
        self.assertEqual(rows[1][14], "'=SUM(A1:A2)")

    def test_json_keeps_original_text_without_csv_escape(self):
        body, count, content_type = render_export("part", "json", {}, "tenant-a")
        self.assertEqual(count, 2)
        self.assertEqual(content_type, "application/json; charset=utf-8")
        payload = json.loads(body)
        alpha = next(row for row in payload if row["part_code"] == "EXP-A")
        self.assertEqual(alpha["description"], "=SUM(A1:A2)")

    @override_settings(EXPORT_MAX_ROWS=1)
    def test_row_limit_is_checked_while_iterating(self):
        with self.assertRaisesMessage(ValueError, "EXPORT_ROW_LIMIT_EXCEEDED"):
            render_export("part", "csv", {}, "tenant-a")
