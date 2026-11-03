"""The baseline audit must include every Medvind row and expose boundary uncertainty."""

import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vg_medvind_baseline_audit import audit


class MedvindBaselineAuditTest(unittest.TestCase):
    def test_all_rows_are_bound_and_boundary_is_clipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            medvind = Path(tmp) / "medvind.xlsx"
            workbook = Path(tmp) / "workbook.xlsx"
            m = Workbook()
            m.active.title = "Medvind"
            m.active.append(["Namn", "Anstnr", "Fr.o.m", "T.o.m", "Fr.o.m kl", "T.o.m kl",
                             "Typ", "Uppdrag", "Uppgift", "Summa"])
            m.active.append([None, None, None, None, None, None, None, None, None, 2.5])
            m.active.append([None, None, None, None, None, None, None, None, None, 1.0])
            m.save(medvind)
            w = Workbook()
            s = w.active
            s.title = "SCHEMA_DEC"
            s.append(["source_excel_row", "person_id", "netto_timmar", "brutto_minuter",
                      "start_lokal", "slut_lokal"])
            s.append([2, "P-1", 2.5, 150, "2026-12-02T06:30:00+01:00",
                      "2026-12-02T09:00:00+01:00"])
            s.append([3, "P-1", 1.0, 60, "2026-12-29T23:30:00+01:00",
                      "2026-12-30T00:30:00+01:00"])
            p = w.create_sheet("PERSONAL")
            p.append(["person_id", "anstallning"])
            p.append(["P-1", "Tillsvidareanställd"])
            w.save(workbook)
            result = audit(medvind, workbook)
            self.assertEqual(result["source_problems"], {})
            self.assertEqual(result["medvind_reported_row_sum_hours"], "3.5")
            self.assertEqual(result["medvind_period_clipped_as_reported_hours"], "3.0")
            self.assertEqual(result["boundary_rows"], 1)
            self.assertEqual(result["rows_by_type"], {"ordinary_rows": 2})
            self.assertEqual(result["actual_medvind_substitute_total"], "UNKNOWN")
            self.assertEqual(result["status"], "SOURCE_RECONCILED_COMPARISON_NOT_LOCKED")

    def test_missing_source_row_blocks_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            medvind = Path(tmp) / "medvind.xlsx"
            workbook = Path(tmp) / "workbook.xlsx"
            m = Workbook()
            m.active.title = "Medvind"
            m.active.append([None] * 10)
            m.active.append([None] * 9 + [1.0])
            m.active.append([None] * 9 + [1.0])
            m.save(medvind)
            w = Workbook()
            s = w.active
            s.title = "SCHEMA_DEC"
            s.append(["source_excel_row", "person_id", "netto_timmar", "brutto_minuter",
                      "start_lokal", "slut_lokal"])
            s.append([2, "P-1", 1.0, 60, "2026-12-02T06:30:00+01:00",
                      "2026-12-02T07:30:00+01:00"])
            p = w.create_sheet("PERSONAL")
            p.append(["person_id", "anstallning"])
            p.append(["P-1", "Tillsvidareanställd"])
            w.save(workbook)
            result = audit(medvind, workbook)
            self.assertEqual(result["status"], "SOURCE_RECONCILIATION_FAILED")
            self.assertIn("SOURCE_ROW_COVERAGE", result["source_problems"])


if __name__ == "__main__":
    unittest.main()
