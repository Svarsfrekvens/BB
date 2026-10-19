"""Small, independent controls for the fixed-phase standard-rest scenario."""
import copy
import unittest

from ortools.sat.python import cp_model

from bb.availability.daily_rest import add_standard_daily_rest
from bb.availability.validator import _standard_daily_assessment

DAY = 1440
PERSON = "TEST-P"


def raw(name, start, end, jour=None, frozen=False):
    work = [[start, end]] if not jour else [[a, b] for a, b in
        ((start, jour[0]), (jour[1], end)) if b > a]
    return {"id": name, "employee_id": PERSON, "start": start, "end": end,
        "work": work, "jour": [list(jour)] if jour else [], "frozen": frozen}


def context_for(duties, frozen=(), phase=0, exceptions=True, hi=4 * DAY):
    model = cp_model.CpModel()
    employee = {"id": PERSON, "history_known": True}
    if phase is not None:
        employee.update(daily_rest_anchor_phase_minutes=phase,
            daily_rest_anchor_status="VERIFIED", daily_rest_anchor_source_ref="SYNTHETIC TEST ONLY")
    profile = {"mode": "PLANNED_AR_JO_REST_AT_LEAST_DUTY_SPAN",
        "source_status": "VERIFIED", "source_ref": "SYNTHETIC TEST ONLY"} if exceptions else {}
    data = {"employees": [employee], "period": {"lo": 0, "hi": hi, "history_lo": -DAY},
        "rules": {"daily_rest_minutes": 660, "jour_compensation": profile},
        "frozen_duties": list(frozen)}
    context = {"data": data, "duties": {}, "unknown_controls": [], "historical_certificates": []}
    for duty in duties:
        selected = model.NewBoolVar(duty["id"] + "_selected")
        model.Add(selected == 1)
        context["duties"][duty["id"]] = {"source": duty, "presence": selected,
            "start": duty["start"], "end": duty["end"], "bounds": (duty["start"], duty["end"]),
            "work": [{"selected": b - a, "active": selected, "reference": (a, b), "left": a, "right": b} for a, b in duty["work"]],
            "jour": [{"selected": b - a, "active": selected,
                "reference": tuple(duty.get("reference_jour", duty["jour"])[index]),
                "left": a, "right": b} for index, (a, b) in enumerate(duty["jour"])]}
    add_standard_daily_rest(model, context)
    return model, context


def solve(model):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 2
    solver.parameters.num_search_workers = 1
    return solver.StatusName(solver.Solve(model))


def assessment(duties, frozen=(), phase=0, exceptions=True, hi=4 * DAY):
    period = {"history_lo": -DAY}
    return _standard_daily_assessment(list(frozen) + list(duties), list(frozen),
        {"history_known": True}, period, 0, hi, -DAY, hi,
        {"phase_minutes": phase, "status": "SYNTHETIC_TEST_ONLY"} if phase is not None else None,
        exceptions)


class StandardDailyRestTests(unittest.TestCase):
    def test_eleven_hour_gap_alone_does_not_validate_fixed_24h_period(self):
        first = raw("FIRST", 6 * 60, 22 * 60)
        second = raw("SECOND", DAY + 9 * 60, DAY + 13 * 60)
        self.assertEqual(second["start"] - first["end"], 660)
        model, _ = context_for([first, second], phase=0)
        self.assertEqual(solve(model), "INFEASIBLE")
        report = assessment([first, second], phase=0)
        self.assertGreater(report["selected_phase_new_violations"], 0)
        self.assertEqual(report["windows"][1]["longest_rest_minutes"], 360)

    def test_standard_eight_hour_duties_pass(self):
        duties = [raw(str(i), i * DAY + 8 * 60, i * DAY + 16 * 60) for i in range(4)]
        model, _ = context_for(duties, phase=8 * 60)
        self.assertEqual(solve(model), "OPTIMAL")
        self.assertEqual(assessment(duties, phase=8 * 60)["selected_phase_new_violations"], 0)

    def test_long_pure_ar_is_not_automatically_b_exception_or_a_13h_cap(self):
        duty = raw("PURE_AR", 6 * 60, 22 * 60)
        fixed_midnight, _ = context_for([duty], phase=0)
        self.assertEqual(solve(fixed_midnight), "INFEASIBLE")
        # A fixed noon anchor splits this isolated duty. This arithmetic test
        # is why imposing a universal 13h cap would add an unsupported rule.
        fixed_noon, _ = context_for([duty], phase=12 * 60)
        self.assertEqual(solve(fixed_noon), "OPTIMAL")
        report = assessment([duty], phase=0)
        self.assertFalse(report["long_active_only_duties"][0]["B_C_exception_available"])

    def test_combined_b_is_separate_and_requires_actual_positive_jour(self):
        combined = raw("B", 15 * 60, DAY + 10 * 60, jour=(23 * 60, DAY + 6 * 60 + 30))
        with_b, _ = context_for([combined], phase=12 * 60)
        without_b, _ = context_for([combined], phase=12 * 60, exceptions=False)
        self.assertEqual(solve(with_b), "OPTIMAL")
        self.assertEqual(solve(without_b), "INFEASIBLE")
        self.assertTrue(any(row["status"] == "B_C_EXCEPTION_ARITHMETIC_ONLY"
            for row in assessment([combined], phase=12 * 60)["windows"]))

    def test_short_combined_b_has_no_invented_thirteen_hour_lower_limit(self):
        combined = raw("SHORT_B", 20 * 60 + 43, DAY + 9 * 60 + 5,
            jour=(23 * 60, DAY + 6 * 60 + 30))
        self.assertLess(combined["end"] - combined["start"], 780)
        with_b, _ = context_for([combined], phase=15 * 60)
        without_b, _ = context_for([combined], phase=15 * 60, exceptions=False)
        self.assertEqual(solve(with_b), "OPTIMAL")
        self.assertEqual(solve(without_b), "INFEASIBLE")
        self.assertTrue(any(row["status"] == "B_C_EXCEPTION_ARITHMETIC_ONLY"
            for row in assessment([combined], phase=15 * 60)["windows"]))

    def test_short_b_requires_whole_duty_rest_even_when_gap_is_over_eleven_hours(self):
        combined = raw("SHORT_B", 20 * 60 + 43, DAY + 9 * 60 + 5,
            jour=(23 * 60, DAY + 6 * 60 + 30))
        span = combined["end"] - combined["start"]
        for gap, expected in ((span - 1, "INFEASIBLE"), (span, "OPTIMAL")):
            with self.subTest(gap=gap):
                self.assertGreater(gap, 660)
                second = raw("SECOND", combined["end"] + gap, combined["end"] + gap + 240)
                model, _ = context_for([combined, second], phase=15 * 60)
                self.assertEqual(solve(model), expected)
                report = assessment([combined, second], phase=15 * 60)
                self.assertEqual(report["selected_phase_new_violations"] == 0, expected == "OPTIMAL")

    def test_five_night_hours_use_actual_selected_jour_not_reference_block(self):
        for length, expected in ((299, "INFEASIBLE"), (300, "OPTIMAL")):
            with self.subTest(selected_jour=length):
                combined = raw("SHORT_B", 20 * 60 + 43, DAY + 9 * 60 + 5,
                    jour=(23 * 60, 23 * 60 + length))
                # A longer reference must not substitute for the actual crop.
                combined["reference_jour"] = [[23 * 60, DAY + 6 * 60 + 30]]
                model, _ = context_for([combined], phase=15 * 60)
                self.assertEqual(solve(model), expected)
                report = assessment([combined], phase=15 * 60)
                self.assertEqual(report["selected_phase_new_violations"] == 0, expected == "OPTIMAL")

    def test_mixed_window_does_not_excuse_a_separate_ar_duty(self):
        # With two duties inside one 24h window, their full >=11h gap lies
        # inside that window, independently of whether one is exceptional.
        first = raw("AR", 4 * 60, 10 * 60)
        second = raw("B", 21 * 60, DAY + 16 * 60, jour=(23 * 60, DAY + 6 * 60 + 30))
        report = assessment([first, second], phase=0)
        day = next(v for v in report["windows"] if v["start"] == 0)
        self.assertEqual(day["longest_rest_minutes"], 660)
        self.assertEqual(day["status"], "PASS_STANDARD_ARITHMETIC")
        # If the separate-duty gap premise is broken, the independent checker
        # fails closed instead of invoking the B chain as a blanket waiver.
        broken = raw("AR", 4 * 60, 11 * 60)
        invalid = assessment([broken, second], phase=0)
        day = next(v for v in invalid["windows"] if v["start"] == 0)
        self.assertEqual(day["status"], "FAIL_MIXED_EXCEPTION_SAFETY")
        self.assertTrue(day["new_violation"])

    def test_frozen_boundary_shortfall_is_retained_and_cannot_be_worsened(self):
        incoming = raw("P1_INCOMING", -60, 15 * 60, frozen=True)
        model, context = context_for([], frozen=[incoming], phase=0)
        self.assertEqual(solve(model), "OPTIMAL")
        self.assertTrue(context["historical_certificates"])
        report = assessment([], frozen=[incoming], phase=0)
        self.assertEqual(report["selected_phase_new_violations"], 0)
        self.assertTrue(any(v["status"] == "FROZEN_STANDARD_SHORTFALL" for v in report["windows"]))
        new = raw("WORSENS_P2", 23 * 60, DAY + 3 * 60)
        changed, _ = context_for([new], frozen=[incoming], phase=0)
        self.assertEqual(solve(changed), "INFEASIBLE")
        self.assertGreater(assessment([new], frozen=[incoming], phase=0)["selected_phase_new_violations"], 0)

    def test_same_phase_applies_to_every_day_and_unknown_anchor_is_explicit(self):
        model, context = context_for([raw("AR", 8 * 60, 16 * 60)], phase=None)
        self.assertEqual(len(context["daily_rest_phases"]), 1)
        self.assertEqual(context["daily_rest_24h_scope"]["anchor_status"], "MODEL_SELECTED_FIXED_PHASE_SCENARIO")
        self.assertEqual(context["daily_rest_24h_scope"]["local_application_status"], "UNKNOWN")
        self.assertEqual(solve(model), "OPTIMAL")
        witness = assessment([raw("AR", 8 * 60, 16 * 60)], phase=None)
        self.assertEqual(witness["tested_integer_phases"], 1440)
        self.assertEqual(witness["anchor_application_status"], "UNKNOWN")

    def test_unknown_last_24h_period_is_not_silently_approved(self):
        duty = raw("LAST_LONG_AR", 3 * DAY + 7 * 60 + 15, 3 * DAY + 22 * 60 + 15)
        # Synthetic last duty: 09:02 would leave at most 10h47 even if all
        # unseen future time were free. UNKNOWN must not hide this proof.
        impossible, _ = context_for([duty], phase=9 * 60 + 2)
        self.assertEqual(solve(impossible), "INFEASIBLE")
        invalid = assessment([duty], phase=9 * 60 + 2)
        self.assertGreater(invalid["selected_phase_new_violations"], 0)
        self.assertEqual(invalid["long_active_only_duties"][0]["fixed_phase_arithmetic_status"], "FAIL")
        report = assessment([duty], phase=9 * 60 + 15)
        possible, _ = context_for([duty], phase=9 * 60 + 15)
        self.assertEqual(solve(possible), "OPTIMAL")
        self.assertEqual(report["outer_periods"], "UNKNOWN_OUTSIDE_VERIFIED_HORIZON")
        outer = [v for v in report["windows"] if v["end"] > 4 * DAY]
        self.assertTrue(outer)
        self.assertTrue(all(v["status"] == "UNKNOWN_OUTSIDE_VERIFIED_HORIZON" for v in outer))
        self.assertEqual(report["long_active_only_duties"][0]["fixed_phase_arithmetic_status"], "UNKNOWN_BOUNDARY")

    def test_known_outgoing_presence_is_included_beyond_complete_history_horizon(self):
        last = raw("LAST_LONG_AR", 3 * DAY + 7 * 60 + 15, 3 * DAY + 22 * 60 + 15)
        known_future = raw("KNOWN_FUTURE", 4 * DAY + 7 * 60, 4 * DAY + 9 * 60)
        model, _ = context_for([last, known_future], phase=9 * 60 + 15)
        self.assertEqual(solve(model), "INFEASIBLE")
        report = assessment([last, known_future], phase=9 * 60 + 15)
        self.assertGreater(report["selected_phase_new_violations"], 0)
        outer = [v for v in report["windows"] if v["start"] == 3 * DAY + 9 * 60 + 15][0]
        self.assertEqual(outer["maximum_possible_rest_minutes"], 8 * 60 + 45)
        self.assertTrue(outer["new_violation"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
