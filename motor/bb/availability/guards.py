"""Explicit reviewed rest policy and typed source-oncall demand; no business defaults."""
from collections import defaultdict
import copy
from zoneinfo import ZoneInfo
from .model import _lt, _and, _longest_night_jour
from .history import merged_intervals, overlap, utc_minute as minute
ZONE = ZoneInfo("Europe/Stockholm")

def source_verified_dynamic_profile(value):
    return (isinstance(value, dict)
            and value.get("mode") == "PLANNED_AR_JO_REST_AT_LEAST_DUTY_SPAN"
            and value.get("source_status") == "VERIFIED" and bool(value.get("source_ref")))

def _inside(intervals, a, b):
    return any(x <= a and b <= y for x, y in merged_intervals(intervals))

def add_compensation(model, context):
    """Exact supplied immediate-rest profile; never infers the missing duration."""
    profile = context["data"]["rules"].get("jour_compensation")
    if source_verified_dynamic_profile(profile):
        return add_dynamic_ar_jo_rest(model, context, profile)
    if not isinstance(profile, dict) or profile.get("status") != "CONFIRMED" or profile.get("mode") != "IMMEDIATE_REST_MINUTES":
        raise ValueError("Explicit supported compensation profile missing")
    minutes = profile.get("rest_minutes")
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 660:
        raise ValueError("Compensation requires sourced exact rest_minutes >= 660")
    per_person = defaultdict(list)
    for duty in context["duties"].values():
        per_person[duty["source"]["employee_id"]].append(duty)
    for identity, duties in per_person.items():
        for first in duties:
            long = _lt(model, 1199, first["end"] - first["start"], first["source"]["id"] + "_compensation_long")
            for second in duties:
                if first is second:
                    continue
                follows = _lt(model, first["end"] - 1, second["start"], first["source"]["id"] + "_before_" + second["source"]["id"] + "_comp")
                model.Add(second["start"] >= first["end"] + minutes).OnlyEnforceIf([first["presence"], second["presence"], long, follows])
    # Frozen P1 Ar/Jo ending near P2 also restricts new work when the supplied
    # profile applies historically. Frozen breaches remain separately reported.
    for fixed in context["data"].get("frozen_duties", []):
        if fixed["end"] - fixed["start"] < 1200:
            continue
        for duty in per_person[fixed["employee_id"]]:
            follows = _lt(model, fixed["end"] - 1, duty["start"], duty["source"]["id"] + "_after_frozen_long")
            model.Add(duty["start"] >= fixed["end"] + minutes).OnlyEnforceIf([duty["presence"], follows])


def _standalone_jo_exception(profile, employee_id, interval):
    record = profile.get("standalone_jour_exception")
    return (isinstance(record, dict) and record.get("status") == "CONFIRMED"
            and bool(record.get("source_ref"))
            and employee_id in record.get("employee_ids", [])
            and any((minute(w["start"]), minute(w["end"])) == tuple(interval)
                    for w in record.get("intervals", [])))


def _c_application_confirmed(profile, employee_id):
    record = profile.get("c_application")
    return (profile.get("C_application_mode") != "DISABLED_UNTIL_APPLICATION_VERIFIED"
            and isinstance(record, dict) and record.get("status") == "CONFIRMED"
            and bool(record.get("source_ref"))
            and employee_id in record.get("employee_ids", [])
            and all(record.get(key) is True for key in (
                "not_healthcare_sector", "necessity", "no_reasonable_alternatives")))


def add_dynamic_ar_jo_rest(model, context, profile):
    """Source-backed numeric B/C scenario; process evidence stays separate.

    780=24h-11h is an EXPLICIT DERIVED MODEL CLASSIFICATION for combined
    duties. It is not quoted contract text, a general duty cap or proof of
    complete standard 11h-in-24h placement. The independent validator retains
    that limitation. No 9h exception or unforeseen-event profile is activated.
    """
    per_person = defaultdict(list)
    dynamic_flags = {}
    for duty in context["duties"].values():
        source = duty["source"]
        identity, cid = source["employee_id"], source["id"]
        per_person[identity].append(duty)
        selected_Ar = sum(block["selected"] for block in duty["work"])
        has_Ar = _lt(model, 0, selected_Ar, cid + "_contract_positive_Ar")
        selected_Jo = sum(block["selected"] for block in duty["jour"])
        has_Jo = _lt(model, 0, selected_Jo, cid + "_contract_positive_Jo")
        for block in duty["jour"]:
            if not _standalone_jo_exception(profile, identity, block["reference"]):
                # Positive Ar in the whole connected candidate is before or
                # after its typed night; one minute is domain resolution only.
                model.Add(has_Ar == 1).OnlyEnforceIf(block["active"])
        exceeds_standard_class = _lt(model, 780, duty["end"] - duty["start"], cid + "_derived_over_13h")
        deviation = _and(model, [duty["presence"], has_Ar, has_Jo, exceeds_standard_class], cid + "_numeric_B_or_C")
        dynamic_flags[cid] = deviation
        # First bounded case permits B arithmetic with process evidence UNKNOWN.
        # C is a separate scope, never activated from the contract text alone.
        cap = 1440 if _c_application_confirmed(profile, identity) else 1200
        model.Add(duty["end"] - duty["start"] <= cap).OnlyEnforceIf(deviation)
        night_supports = []
        for index, block in enumerate(duty["jour"]):
            a, b = block["reference"]
            if source.get("mode") == "SHIFT_COMPLETE":
                for value in source["start_values"]:
                    offset = value - source.get("reference_start", source["start"])
                    if _longest_night_jour(a+offset, b+offset, ZONE) >= 300:
                        at = _and(model, [duty["presence"],
                            _lt(model, duty["start"], value+1, cid + f"_bc_night{index}_le{value}"),
                            _lt(model, value-1, duty["start"], cid + f"_bc_night{index}_ge{value}")],
                            cid + f"_bc_night{index}_at{value}")
                        night_supports.append(at)
            elif _longest_night_jour(a, b, ZONE) >= 300:
                night_supports.append(block["active"])
        model.Add(sum(night_supports) >= 1).OnlyEnforceIf(deviation)
    for identity, duties in per_person.items():
        for first in duties:
            span = first["end"] - first["start"]
            for second in duties:
                if first is second:
                    continue
                follows = _lt(model, first["end"]-1, second["start"],
                              first["source"]["id"] + "_bc_before_" + second["source"]["id"])
                model.Add(second["start"] >= first["end"] + span).OnlyEnforceIf([
                    first["presence"], second["presence"], dynamic_flags[first["source"]["id"]], follows])
    for fixed in context["data"].get("frozen_duties", []):
        span = fixed["end"] - fixed["start"]
        if not (fixed.get("work") and fixed.get("jour") and span > 780):
            continue
        for duty in per_person[fixed["employee_id"]]:
            follows = _lt(model, fixed["end"]-1, duty["start"], duty["source"]["id"] + "_bc_after_frozen")
            model.Add(duty["start"] >= fixed["end"] + span).OnlyEnforceIf([duty["presence"], follows])
    context["contract_profile_scope"] = {
        "mode": profile["mode"], "mathematics": "REST_AT_LEAST_SELECTED_WHOLE_DUTY_LENGTH",
        "classification": "EXPLICIT_DERIVED_24H_MINUS_11H_NOT_CONTRACT_QUOTE",
        "B": "COMBINED_DERIVED_DEVIATION_UP_TO_AND_INCLUDING_1200_MINUTES",
        "C": profile.get("C_application_mode", "DISABLED_UNTIL_APPLICATION_VERIFIED"),
        "process_evidence": copy.deepcopy(profile.get("process_evidence", {})),
        "business_schedule_approved": False}


def source_jo_requirements(data):
    """Source planned oncall staffing is demand, including vacant source rows.

    Preserve complete incoming/outgoing typed windows. Only reporting minutes
    are clipped at P2. This is source-plan preservation, not an inferred generic
    local night-staffing rule or a fabricated Sekoia customer need.
    """
    lo, hi = data["period"]["lo"], data["period"]["hi"]
    groups = defaultdict(list)
    for segment in data["source_schedule_segments"]:
        if segment["source_code"] != "Jo":
            continue
        a, b = minute(segment["start"]), minute(segment["end"])
        if overlap(a, b, lo, hi):
            groups[(a, b)].append(segment)
    return [{"start": a, "end": b, "required_people": len(rows),
             "source_segment_ids": [r["segment_id"] for r in rows],
             "source_vacant_rows": sum(r["is_vacant"] for r in rows),
             "P2_person_minutes": overlap(a, b, lo, hi) * len(rows)}
            for (a, b), rows in sorted(groups.items())]


def add_source_jo_coverage(model, context):
    requirements = source_jo_requirements(context["data"])
    for requirement in requirements:
        a, b = requirement["start"], requirement["end"]
        frozen_count = sum(_inside(d.get("jour", []), a, b) for d in context["data"]["frozen_duties"])
        supports = [block["active"] for duty in context["duties"].values() for block in duty["jour"]
                    if tuple(block["reference"]) == (a, b)]
        model.Add(sum(supports) + frozen_count == requirement["required_people"])
    context["source_oncall_requirements"] = requirements


def validate_source_jo(data, result):
    """Recount separate typed Jo from exported duties, without CP variables."""
    feasible = result["solver_status"] in {"FEASIBLE", "OPTIMAL"}
    rows = []
    for required in source_jo_requirements(data):
        a, b = required["start"], required["end"]
        duties = data["frozen_duties"] + result.get("selected_duties", [])
        people = sorted({d["employee_id"] for d in duties if _inside(d.get("jour", []), a, b)})
        rows.append({**required, "assigned_employee_ids": people,
                     "status": "PASS" if feasible and len(people) == required["required_people"] else "BROKEN" if feasible else "UNKNOWN"})
    return {"scope": "PRESERVE_SOURCE_PLANNED_TYPED_JO_INCLUDING_VACANCY_AS_DEMAND",
            "source_window_rows": len(rows), "P2_person_minutes": sum(r["P2_person_minutes"] for r in rows),
            "all_windows_covered": all(r["status"] == "PASS" for r in rows) if feasible else None,
            "rows": rows}
