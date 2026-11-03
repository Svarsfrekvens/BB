"""Regression checks for the two mistakes that invalidated the first C handoff."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vg_delivery_gate import _ledger_minutes, candidate_paid_minutes, check
from vg_validate_candidate import validate


class DeliveryGateTest(unittest.TestCase):
    def test_duty_time_is_clipped_and_substitute_type_is_explicit(self):
        candidate = {
            "staff": [{"id": "P-1", "type": "ORDINARY"},
                      {"id": "VIK-1", "type": "SYNTHETIC_SUBSTITUTE"}],
            "duties": [
                {"id": "A", "person_id": "P-1", "start": 60, "end": 360,
                 "breaks": [], "net_minutes": 300},
                {"id": "B", "person_id": "VIK-1", "start": 40300, "end": 40420,
                 "breaks": [[40340, 40370]], "net_minutes": 90},
            ],
        }
        period, whole, errors = candidate_paid_minutes(candidate)
        self.assertEqual(errors, [])
        self.assertEqual(period, {"ordinary": 300, "substitute": 20})
        self.assertEqual(whole, {"ordinary": 300, "substitute": 90})

    def test_medvind_report_is_split_by_period_and_type(self):
        ledger = {"rows": [
            {"source_ref": "R-1", "person_id": "P-1", "staff_type": "ORDINARY", "paid_intervals": [
                {"start": "2026-12-29T23:30:00+01:00", "end": "2026-12-30T01:00:00+01:00"}]},
            {"source_ref": "R-2", "person_id": "VIK-1", "staff_type": "SYNTHETIC_SUBSTITUTE", "paid_intervals": [
                {"start": "2026-12-02T06:30:00+01:00", "end": "2026-12-02T07:00:00+01:00"}]},
        ]}
        raw, clipped, _, errors = _ledger_minutes(ledger)
        self.assertEqual(errors, [])
        self.assertEqual(raw, {"ordinary": 90, "substitute": 30})
        self.assertEqual(clipped, {"ordinary": 30, "substitute": 30})

    def test_medvind_overlapping_person_time_is_rejected(self):
        ledger = {"rows": [
            {"source_ref": "R-1", "person_id": "P-1", "staff_type": "ORDINARY", "paid_intervals": [
                {"start": "2026-12-02T07:00:00+01:00", "end": "2026-12-02T08:00:00+01:00"}]},
            {"source_ref": "R-2", "person_id": "P-1", "staff_type": "ORDINARY", "paid_intervals": [
                {"start": "2026-12-02T07:30:00+01:00", "end": "2026-12-02T08:30:00+01:00"}]},
        ]}
        _, _, _, errors = _ledger_minutes(ledger)
        self.assertIn("MEDVIND_PERSON_TIME_OVERLAP", errors)

    def test_missing_locked_baseline_and_proof_block_delivery(self):
        candidate = {"staff": [], "duties": [], "validation": {"workload": {}},
                     "business_id": "6d0002a5-c34f-4709-af13-c04f96786e8c",
                     "period": {"start": "2026-12-02", "end": "2026-12-29",
                                "timezone": "Europe/Stockholm"}}
        result = check(candidate, "candidate-hash", 0, None, None, None, None, None, None)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("LOCKED_MEDVIND_BASELINE_MISSING", result["errors"])
        self.assertIn("JOINT_OPTIMIZATION_PROOF_MISSING", result["errors"])

    def test_whole_boundary_duty_cannot_be_reported_as_period_net(self):
        candidate = {"staff": [{"id": "VIK-1", "type": "SYNTHETIC_SUBSTITUTE"}],
                     "duties": [{"id": "D-1", "person_id": "VIK-1", "start": 40300,
                                 "end": 40420, "breaks": [], "net_minutes": 120}],
                     "validation": {"workload": {"ordinary_minutes": 0,
                                                 "temporary_minutes": 120,
                                                 "model_cost_sek": 586.0}},
                     "period": {"start": "2026-12-02", "end": "2026-12-29",
                                "timezone": "Europe/Stockholm"}}
        result = check(candidate, "candidate-hash", 0, None, None, None, None, None, None)
        self.assertEqual(result["after_period_minutes"]["substitute"], 20)
        self.assertIn("AFTER_NOT_PERIOD_CLIPPED", result["errors"])
        self.assertIn("AFTER_COST_NOT_PERIOD_CLIPPED", result["errors"])
        independent = validate(candidate)
        self.assertEqual(independent["substitute_minutes"], 20)
        self.assertEqual(independent["whole_duty_substitute_minutes"], 120)


if __name__ == "__main__":
    unittest.main()
