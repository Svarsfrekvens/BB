"""Synthetic import tests: no private staff, dates or source workbooks."""
from copy import deepcopy
import unittest

from bb.flora_import import FloraImportError, prepare_case


def sample():
    periods = [dict(id="history",start="2027-01-01",end="2027-01-28"),
               dict(id="next",start="2027-01-29",end="2027-02-25")]
    staff = [dict(person_id="person-a",alias="Test A",employment_type="Tillsvidare",
                  ssg_pct=None,fulltime_hours_28d=None,day_allowed=True,evening_allowed=True,
                  sleeping_oncall_allowed=True,awake_night_allowed=False,
                  hard_individual_condition=None,soft_preference=None,
                  individual_delegations="ALLA_BEFINTLIGA_INSATSKRAV")]
    segments = [dict(segment_id="history-row",person_id="person-a",start="2027-01-28T12:00",
                     end="2027-01-28T16:00",source_code="Ar",category="AKTIVT_ARBETE"),
                dict(segment_id="active-row",person_id="person-a",start="2027-01-29T08:00",
                     end="2027-01-29T12:00",source_code="Ar",category="AKTIVT_ARBETE"),
                dict(segment_id="absence-row",person_id="person-a",start="2027-01-30T08:00",
                     end="2027-01-30T12:00",source_code="Se",category="FRANVARO")]
    need = dict(need_id="source-need",date="2027-01-29",customer_id="customer-a",activity="Besök",
                window_start="09:00",window_end="11:00",duration_minutes=30,
                source_two_person_flag=False,personnel_count_candidate=None,
                profession_raw="Omsorg",delegated_profession_raw=None,medication=False,hsl=False,
                source_fields={"Beskrivning":"Ett självständigt besök","source_row":17},
                source_ref="Behov rad 17",fixed_or_flexible=None)
    raw = dict(metadata=dict(schema_version="flora-bb-input/1.0",timezone="Europe/Stockholm",periods=periods),
               staff=staff,customers=[dict(customer_id="customer-a",scope="INDIVIDUAL")],
               schedule_segments=segments,customer_needs=[need],business_rules=[],untimed_codes=[],
               source_archive={"private_bytes":"must stay outside adapter case"})
    expected = {key:deepcopy(value) for key,value in staff[0].items() if key not in ("person_id","alias")}
    semkeys=("customer_id","activity","profession_raw","delegated_profession_raw","medication","hsl","source_two_person_flag")
    profile = dict(schema_version="bb-analysis-input-profile/1.0",profile_id="synthetic-profile",
                   period_id="next",history_period_id="history",applicable_periods=deepcopy(periods),
                   absence_mode="omit_p2",allowed_absence_modes=["omit_p2","preserve"],
                   config=dict(min_shift=240,min_free_days=9,calendar_mode="rolling"),
                   staff={"person-a":dict(ordinary=True,target_net=240,expected=expected)},
                   segment_decisions={r["segment_id"]:dict(mode="fixed" if i==0 else "mutable" if i==1 else "excluded",
                           locked_reason="HISTORY" if i==0 else "SOURCE_MUTABLE" if i==1 else "P2_SE_TI_GROUND_SCENARIO",
                           reference_import=True,expected={k:r[k] for k in ("person_id","source_code","category")})
                       for i,r in enumerate(segments)},
                   candidate_windows=[dict(person_id="person-a",date="2027-01-29",earliest=480,latest=1020,
                                           min_length=240,max_length=600,source_segment_id="active-row")],
                   need_decisions={"source-need":dict(engine_id="engine-need",expected={k:need[k] for k in semkeys},
                        description=need["source_fields"]["Beskrivning"],flex=False,exclusive=True,
                        parallel_permission="EXCLUSIVE_ONLY",previous_class="ORIGINAL_WINDOW")},
                   business_rules_expected=[],reference_breaks=[],reassignable_units=[],issues=[])
    return raw,profile


class ImportTest(unittest.TestCase):
    def test_uploaded_values_and_generic_period_ids(self):
        raw,profile=sample(); result=prepare_case(raw,profile)
        self.assertEqual(result["origin"],"2027-01-29T00:00")
        self.assertEqual(result["horizon"],40320)
        self.assertEqual(result["needs"][0]["duration"],30)
        self.assertEqual(result["needs"][0]["domains"],[[540,630]])
        self.assertEqual(result["integration"]["need_id_map"],{"engine-need":"source-need"})
        raw["customer_needs"][0]["duration_minutes"]=20
        raw["schedule_segments"][0]["end"]="2027-01-28T16:17"
        changed=prepare_case(raw,profile)
        self.assertEqual(changed["needs"][0]["domains"],[[540,640]])
        self.assertEqual(changed["fixed_segments"][0]["end"],-463)
        self.assertNotEqual(changed["integration"]["input_sha256"],result["integration"]["input_sha256"])

    def test_preserves_raw_and_no_in_place_mutation(self):
        raw,profile=sample(); before=deepcopy(raw); original_profile=deepcopy(profile)
        result=prepare_case(raw,profile)
        self.assertEqual(raw,before); self.assertEqual(profile,original_profile)
        self.assertNotIn("source_archive",result["import_provenance"]["upload"])
        self.assertEqual(len(result["import_provenance"]["all_timed_history"]),1)
        self.assertEqual(result["staff"][0]["target_net"],240)
        self.assertIsNone(result["import_provenance"]["upload"]["staff"][0]["ssg_pct"])

    def test_real_absence_is_locked_not_capacity(self):
        raw,profile=sample(); result=prepare_case(raw,profile,{"absence_mode":"preserve"})
        self.assertEqual(len(result["confirmed_absence_locks"]),1)
        self.assertEqual(result["confirmed_absence_locks"][0]["code"],"Se")
        self.assertEqual(result["fixed_segments"][-1]["locked_reason"],"CONFIRMED_ABSENCE")

    def test_empty_defaults_and_source_equal_drafts_are_valid(self):
        raw,profile=sample()
        scenario=dict(drafts={"person-a":dict(ssg_pct=dict(value=None,source="unknown"),
                      sleeping_oncall_allowed=dict(value=True,source="import"),reviewed_by_vc=False)},
                      workspace=dict(unit_rules=dict(default_form=None,person_forms={},freeday=None),
                      competence=dict(codes=[],persons={}),activities=[dict(on=False,minutes=17)],
                      contacts={},people={"person-a":dict(hourly_cost=400,availability="",absences=[],admin_hours_per_week=None)}))
        self.assertEqual(len(prepare_case(raw,profile,scenario)["needs"]),1)

    def test_unknown_count_never_becomes_one(self):
        raw,profile=sample(); raw["customer_needs"][0]["source_two_person_flag"]=None
        profile["need_decisions"]["source-need"]["expected"]["source_two_person_flag"]=None
        with self.assertRaisesRegex(FloraImportError,"antal personer"):
            prepare_case(raw,profile)

    def test_missing_target_never_becomes_zero(self):
        raw,profile=sample(); profile["staff"]["person-a"]["target_net"]=None
        with self.assertRaisesRegex(FloraImportError,"nettoreferens"):
            prepare_case(raw,profile)

    def test_bad_windows_and_changed_semantics_require_review(self):
        for field,value in (("duration_minutes",121),("activity","Ny insats"),("required_codes",["NEW"])):
            with self.subTest(field=field):
                raw,profile=sample(); raw["customer_needs"][0][field]=value
                with self.assertRaises(FloraImportError): prepare_case(raw,profile)

    def test_no_dropped_rows_or_duplicate_ids(self):
        for change in ("drop","duplicate"):
            raw,profile=sample()
            if change=="drop":raw["schedule_segments"].pop()
            else:raw["customer_needs"].append(deepcopy(raw["customer_needs"][0]))
            with self.assertRaises(FloraImportError):prepare_case(raw,profile)

    def test_meaningful_unmapped_workspace_changes_are_not_ignored(self):
        for workspace in (dict(activities=[dict(on=True,name="Journal")]),
                          dict(people={"person-a":dict(availability="Enbart måndagar")}),
                          dict(competence=dict(codes=["MEDICIN"])),
                          dict(unit_rules=dict(freeday=dict(mode="fast")))):
            with self.subTest(workspace=workspace):
                raw,profile=sample()
                with self.assertRaises(FloraImportError):prepare_case(raw,profile,dict(workspace=workspace))

    def test_profile_cannot_hide_static_result(self):
        raw,profile=sample(); profile["search_hint"]={"schedule":"static"}
        with self.assertRaises(FloraImportError):prepare_case(raw,profile)

    def test_profile_adjustment_keeps_original_before_and_rejects_other_source_bounds(self):
        raw,profile=sample()
        profile["segment_adjustments"]=[dict(segment_id="active-row",status="SCENARIO",
            expected_start="2027-01-29T08:00",expected_end="2027-01-29T12:00",
            model_start="2027-01-29T09:00",model_end="2027-01-29T12:00",
            source="Synthetic reviewed trial",message="Explicitly scoped test shortening")]
        result=prepare_case(raw,profile)
        self.assertEqual(result["references"]["import"]["segments"][1]["start"],480)
        self.assertEqual(result["candidates"][0]["original_start"],540)
        self.assertEqual(result["integration"]["scenario_adjustments"][0]["status"],"SCENARIO")
        raw["schedule_segments"][1]["start"]="2027-01-29T08:30"
        with self.assertRaisesRegex(FloraImportError,"originaltiden"):
            prepare_case(raw,profile)

    def test_unknown_settings_and_pass_templates_are_not_ignored(self):
        for scenario in (dict(unrecognised_hard_rule=17),dict(workspace=dict(unknown_rule=8)),
                         dict(workspace=dict(templates=[dict(id="new-template")]))):
            raw,profile=sample()
            with self.assertRaises(FloraImportError):prepare_case(raw,profile,scenario)

    def test_explicit_global_hourly_cost_has_source_and_currency(self):
        raw,profile=sample()
        case=prepare_case(raw,profile,dict(workspace=dict(finance=dict(values=dict(hourly_cost=399.5)))))
        value=case["economic_parameters"]["hourly_cost_by_person"]["person-a"]
        self.assertEqual(value["value"],399.5)
        self.assertEqual(value["currency"],"SEK")
        self.assertIn("settings.finance.values.hourly_cost",value["source"])
        self.assertEqual(case["economic_parameters"]["missing_person_ids"],[])

    def test_person_cost_overrides_global_including_explicit_zero(self):
        for individual in (0,425.75):
            with self.subTest(individual=individual):
                raw,profile=sample()
                case=prepare_case(raw,profile,dict(workspace=dict(finance=dict(values=dict(hourly_cost=600)),
                     people={"person-a":dict(hourly_cost=individual)})))
                value=case["economic_parameters"]["hourly_cost_by_person"]["person-a"]
                self.assertEqual(value["value"],individual)
                self.assertEqual(value["currency"],"SEK")
                self.assertIn("settings.people.person-a.hourly_cost",value["source"])

    def test_null_person_rate_falls_back_only_to_explicit_global(self):
        raw,profile=sample()
        workspace=dict(people={"person-a":dict(hourly_cost=None)})
        unknown=prepare_case(raw,profile,dict(workspace=workspace))["economic_parameters"]
        self.assertEqual(unknown["hourly_cost_by_person"],{})
        self.assertEqual(unknown["missing_person_ids"],["person-a"])
        workspace["finance"]=dict(values=dict(hourly_cost=0))
        explicit=prepare_case(raw,profile,dict(workspace=workspace))["economic_parameters"]
        self.assertEqual(explicit["hourly_cost_by_person"]["person-a"]["value"],0)
        self.assertIn("settings.finance.values.hourly_cost",explicit["hourly_cost_by_person"]["person-a"]["source"])
        workspace["finance"]["values"]["hourly_cost"]=None
        self.assertEqual(prepare_case(raw,profile,dict(workspace=workspace))["economic_parameters"]["hourly_cost_by_person"],{})

    def test_unsupported_economic_fields_and_invalid_rates_fail_clearly(self):
        scenarios=[dict(workspace=dict(finance=dict(values=dict(hourly_cost=300,staffing_buffer_pct=10)))),
                   dict(workspace=dict(finance=dict(oncall_rate=50))),
                   dict(workspace=dict(people={"unknown-person":dict(hourly_cost=300)}))]
        scenarios.extend(dict(workspace=dict(finance=dict(values=dict(hourly_cost=value))))
                         for value in (-1,True,float("nan"),float("inf"),"300"))
        for scenario in scenarios:
            raw,profile=sample()
            with self.subTest(scenario=scenario):
                with self.assertRaises(FloraImportError):prepare_case(raw,profile,scenario)


if __name__=="__main__": unittest.main()
