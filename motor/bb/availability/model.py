"""Isolated, whole-period CP-SAT model; no production imports or fabricated facts.

The source-plan mode preserves actual Ar minutes, not an inferred SSG contract.
Every input occurrence has a coverage decision, including occurrences that have
no verified assignment support. A diagnostic solve is expressly not approval of
unknown controls. Integer-minute cropping avoids enumerating endpoint pairs.
"""
from __future__ import annotations

import copy
import resource
import tempfile
import time
from collections import defaultdict
from datetime import datetime, time as clock, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ortools.sat.python import cp_model

from .history import jour_windows, merged_intervals, overlap, utc_minute
from .daily_rest import add_standard_daily_rest
from ..concurrency_policy import reviewed_modes

DAY, WEEK, ROLLING = 1440, 10080, 40320
SAFE_BUDGET_CEILINGS = {"max_occurrences": 4000, "max_candidates": 20000,
                        "max_supports": 250000}


class ModelInputError(ValueError):
    """Unsupported or inconsistent input, not a scheduling impossibility."""


class ResourceBudgetExceeded(ModelInputError):
    """An explicit resource budget was exceeded without dropping input."""


def _availability_unknown(employee):
    """Observed presence never supplies a person's confirmed availability.

    Legacy verified fixtures omit the aggregate status and supply explicit
    allowed windows.  The new source adapter always states UNKNOWN/VERIFIED.
    A literal VERIFIED empty list is a known unavailable domain, not a missing
    value, and may legitimately make a requested target infeasible.
    """
    status = employee.get("availability_status")
    if status is not None:
        return status != "VERIFIED"
    windows = employee.get("allowed_presence_windows")
    if windows is None:
        return True
    return any(w.get("status") not in (None, "VERIFIED") for w in windows)


def _availability_facts(data):
    mutable_people = {c["employee_id"] for c in data.get("candidates", [])}
    return [{"employee_id": employee["id"], "field": "confirmed_availability",
             "status": "UNKNOWN", "observed_presence_is_not_availability": True,
             "why": "Confirmed allowed work windows are missing; source-plan duties are a reference diagnostic only"}
            for employee in data.get("employees", [])
            if employee["id"] in mutable_people and _availability_unknown(employee)]


def _presence_windows(employee, candidate, diagnostic_only):
    if not _availability_unknown(employee):
        return employee.get("allowed_presence_windows", [])
    if not diagnostic_only:
        raise ModelInputError(f"{employee['id']}: confirmed availability is UNKNOWN; normal CP search is not allowed")
    if candidate.get("mode", "CROP_SOURCE") != "CROP_SOURCE":
        raise ModelInputError(f"{candidate['id']}: missing availability cannot authorize a shifted duty even in a source-plan diagnostic")
    observed = employee.get("observed_presence_windows")
    if observed is not None:
        return observed
    # Compatibility with an archived SOURCE_PLAN_ONLY input.  The diagnostic
    # label remains explicit; these values cannot enter the normal domain.
    return [w for w in employee.get("allowed_presence_windows", [])
            if w.get("status") == "SOURCE_PLAN_ONLY"]


def _bounds(candidate, name):
    value = candidate.get(name + "_bounds", [candidate[name], candidate[name]])
    pair = tuple(value[k] for k in ("min", "max")) if isinstance(value, dict) else tuple(value)
    if len(pair) != 2 or any(not isinstance(v, int) or isinstance(v, bool) for v in pair) or pair[1] < pair[0]:
        raise ModelInputError(f"{candidate['id']}: invalid exact-minute {name} bounds")
    return pair


def _and(model, terms, name):
    result = model.NewBoolVar(name)
    if not terms:
        model.Add(result == 1)
    else:
        for term in terms:
            model.Add(result <= term)
        model.Add(result >= sum(terms) - len(terms) + 1)
    return result


def _lt(model, left, right, name):
    """Exact Boolean equivalence left < right for integer minutes."""
    result = model.NewBoolVar(name)
    model.Add(left < right).OnlyEnforceIf(result)
    model.Add(left >= right).OnlyEnforceIf(result.Not())
    return result


def _clip(model, start, end, lo, hi, bounds, name):
    """Dynamic nonnegative intersection length, including absent intersections."""
    lower, upper = bounds
    left = model.NewIntVar(min(lower, lo), max(upper, lo), name + "_left")
    right = model.NewIntVar(min(lower, hi), max(upper, hi), name + "_right")
    model.AddMaxEquality(left, [start, lo])
    model.AddMinEquality(right, [end, hi])
    size = model.NewIntVar(0, max(0, hi - lo), name + "_minutes")
    model.AddMaxEquality(size, [right - left, 0])
    return left, right, size


def _selected_minutes(model, value, presence, limit, name):
    result = model.NewIntVar(0, limit, name)
    model.Add(result == value).OnlyEnforceIf(presence)
    model.Add(result == 0).OnlyEnforceIf(presence.Not())
    return result


def _civil_days(lo, hi, zone):
    start = datetime.fromtimestamp(lo * 60, timezone.utc).astimezone(zone).date()
    result = []
    while True:
        a = utc_minute(datetime.combine(start, clock(0), zone))
        b = utc_minute(datetime.combine(start + timedelta(days=1), clock(0), zone))
        if a >= hi:
            return result
        if b > lo:
            result.append((start.isoformat(), a, b))
        start += timedelta(days=1)


def _longest_night_jour(start, end, zone):
    """Continuous typed Jo inside a local 22:00--08:00 night window."""
    day = datetime.fromtimestamp(start * 60, timezone.utc).astimezone(zone).date() - timedelta(days=1)
    last = datetime.fromtimestamp((end - 1) * 60, timezone.utc).astimezone(zone).date()
    best = 0
    while day <= last:
        a = utc_minute(datetime.combine(day, clock(22), zone))
        b = utc_minute(datetime.combine(day + timedelta(days=1), clock(8), zone))
        best = max(best, overlap(start, end, a, b))
        day += timedelta(days=1)
    return best


def _allowed_role(employee, role):
    value = employee.get("source_role_permissions", {}).get(role)
    return value.get("allowed") is True if isinstance(value, dict) else value is True


def _has_active_night(intervals, zone, window):
    # Only a sourced local profile can define a clock-based night class.
    start_clock, end_clock = clock.fromisoformat(window["start"]), clock.fromisoformat(window["end"])
    for start, end in intervals:
        day = datetime.fromtimestamp(start * 60, timezone.utc).astimezone(zone).date() - timedelta(days=1)
        last = datetime.fromtimestamp((end - 1) * 60, timezone.utc).astimezone(zone).date()
        while day <= last:
            a = utc_minute(datetime.combine(day, start_clock, zone))
            next_day = day + timedelta(days=1) if end_clock <= start_clock else day
            b = utc_minute(datetime.combine(next_day, end_clock, zone))
            if overlap(start, end, a, b):
                return True
            day += timedelta(days=1)
    return False


def _validate_shift(candidate, employee, bounds, zone, rules):
    values = candidate.get("start_values")
    if not isinstance(values, list) or not values:
        raise ModelInputError(f"{candidate['id']}: every shifted duty needs finite clock-profile-compatible start_values")
    reference = candidate.get("reference_start", candidate["start"])
    source_clock = datetime.fromtimestamp(reference * 60, timezone.utc).astimezone(zone).time()
    proof = candidate.get("clock_profile_verification")
    known_roles = {"day", "evening", "sleeping_oncall", "awake_night"}
    if proof is not None:
        if proof.get("status") != "VERIFIED" or not proof.get("source_ref") or not isinstance(proof.get("required_roles"), list) or not proof["required_roles"]:
            raise ModelInputError(f"{candidate['id']}: clock-profile change requires sourced VERIFIED role proof")
        if any(role not in known_roles for role in proof["required_roles"]):
            raise ModelInputError(f"{candidate['id']}: unrecognized verified role classification")
    required_roles = candidate.get("required_roles", [])
    if not isinstance(required_roles, list) or any(r not in known_roles for r in required_roles):
        raise ModelInputError(f"{candidate['id']}: invalid required_roles classification")
    required_roles = set(required_roles) | set(proof.get("required_roles", []) if proof else [])
    work = candidate.get("reference_work", candidate.get("work", []))
    jour = candidate.get("reference_jour", candidate.get("jour", []))
    night_window = rules.get("active_night_clock_window")
    night_known = isinstance(night_window, dict) and night_window.get("status") == "VERIFIED" and bool(night_window.get("source_ref"))
    if work and not required_roles.intersection({"day", "evening", "awake_night"}):
        required_roles.add("day")
    if jour:
        required_roles.add("sleeping_oncall")
    for value in values:
        if not isinstance(value, int) or isinstance(value, bool) or not bounds[0] <= value <= bounds[1]:
            raise ModelInputError(f"{candidate['id']}: invalid shifted start_value")
        actual_clock = datetime.fromtimestamp(value * 60, timezone.utc).astimezone(zone).time()
        if actual_clock != source_clock:
            if proof is None or actual_clock.strftime("%H:%M") not in proof.get("allowed_start_clocks", []):
                raise ModelInputError(f"{candidate['id']}: unverified change of Swedish source start clock")
        delta = value - reference
        actual_work = [[a + delta, b + delta] for a, b in work]
        actual_jour = [[a + delta, b + delta] for a, b in jour]
        if night_known and _has_active_night(actual_work, zone, night_window):
            required_roles.add("awake_night")
        for (a, b), (original_a, original_b) in zip(actual_jour, jour):
            left = datetime.fromtimestamp(a * 60, timezone.utc).astimezone(zone)
            right = datetime.fromtimestamp(b * 60, timezone.utc).astimezone(zone)
            original_left = datetime.fromtimestamp(original_a * 60, timezone.utc).astimezone(zone)
            original_right = datetime.fromtimestamp(original_b * 60, timezone.utc).astimezone(zone)
            expected_left = clock.fromisoformat(night_window["start"]) if night_known else original_left.time()
            expected_right = clock.fromisoformat(night_window["end"]) if night_known else original_right.time()
            if left.time() != expected_left or right.time() != expected_right or (right.date() - left.date()) != (original_right.date() - original_left.date()):
                raise ModelInputError(f"{candidate['id']}: shifted Jo violates its sourced local clock profile")
    denied_or_unknown = sorted(role for role in required_roles if not _allowed_role(employee, role))
    if denied_or_unknown:
        raise ModelInputError(f"{candidate['id']}: shifted duty uses denied/unknown roles {denied_or_unknown}")
    return [] if night_known else [{"candidate_id": candidate["id"],
        "field": "active_night_clock_window", "why": "No verified local night classification; no universal clock threshold inferred"}]


def _validate_work_available(candidate, employee, zone, rules):
    """New Ar can use the confirmed window without copying old duty clocks."""
    if _availability_unknown(employee):
        raise ModelInputError(f"{candidate['id']}: new work requires confirmed availability")
    if not _allowed_role(employee, "day"):
        raise ModelInputError(f"{candidate['id']}: new active work requires the sourced permitted day role")
    if candidate.get("jour") or candidate.get("reference_jour"):
        raise ModelInputError(f"{candidate['id']}: WORK_AVAILABLE cannot manufacture or convert Jo")
    work = candidate.get("work", [])
    if merged_intervals(work) != [(candidate["start"], candidate["end"])]:
        raise ModelInputError(f"{candidate['id']}: new Ar profile must be the complete confirmed work window")
    night = rules.get("active_night_clock_window")
    known_night = isinstance(night, dict) and night.get("status") == "VERIFIED" and bool(night.get("source_ref"))
    if known_night and _has_active_night(work, zone, night) and not _allowed_role(employee, "awake_night"):
        raise ModelInputError(f"{candidate['id']}: new work window includes the sourced night interval without awake-night permission")
    return [] if known_night else [{"candidate_id": candidate["id"], "field": "active_night_clock_window",
        "why": "No sourced night-role interval; new Ar is not a claim that an unknown role is permitted"}]


def _unknown_facts(data):
    result = copy.deepcopy(data.get("unknown_controls", []))
    result.extend(_availability_facts(data))
    for need in data["needs"]:
        if need.get("blockers"):
            result.append({"need_id": need["id"], "fields": list(need["blockers"])})
        if need.get("count_confirmed") is None:
            result.append({"need_id": need["id"], "field": "personnel_count_unconfirmed"})
        if need.get("movable") is False and need.get("locked_start") is None:
            result.append({"need_id": need["id"], "field": "explicit_lock_start_unknown"})
    for employee in data["employees"]:
        if employee.get("hard_condition_unknown"):
            result.append({"employee_id": employee["id"], "field": "individual_hard_condition"})
        if employee.get("staffing_type") == "UNKNOWN":
            result.append({"employee_id": employee["id"], "field": "staffing_type"})
    return result


def build_model(data, diagnostic_only=False):
    """Build all occurrences and global duties; return (model, extraction context)."""
    concurrency = reviewed_modes(data)
    availability_missing = _availability_facts(data)
    if availability_missing and not diagnostic_only:
        people = ", ".join(fact["employee_id"] for fact in availability_missing)
        raise ModelInputError(f"Confirmed availability is UNKNOWN for {people}; use only an explicitly labelled source-plan diagnostic")
    began = time.perf_counter()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    model = cp_model.CpModel()
    period, rules = data["period"], data["rules"]
    lo, hi = period["lo"], period["hi"]
    history_lo = period.get("history_lo", lo)
    budget = dict(SAFE_BUDGET_CEILINGS)
    requested_budget = data.get("resource_budget", {})
    if not isinstance(requested_budget, dict):
        raise ModelInputError("resource_budget must be an explicit object")
    for name, value in requested_budget.items():
        if name not in budget or not isinstance(value, int) or isinstance(value, bool) or not 0 < value <= SAFE_BUDGET_CEILINGS[name]:
            raise ModelInputError(f"Invalid or unsafe resource budget {name}={value!r}; no implicit unlimited option")
        budget[name] = value
    for name, default, lower, upper in (("min_duty_minutes", 240, 240, 1440),
            ("min_free_days", 9, 9, 28), ("daily_rest_minutes", 660, 660, 10080),
            ("weekly_rest_minutes", 2160, 2160, 10080)):
        value = rules.get(name, default)
        if not isinstance(value, int) or isinstance(value, bool) or not lower <= value <= upper:
            raise ModelInputError(f"Unsupported or weakened decided rule {name}={value!r}")
    if rules.get("jour_cap_minutes", 2880) != 2880 or rules.get("jour_window_minutes", ROLLING) != ROLLING:
        raise ModelInputError("The decided 48-hour rolling-28-day Jo cap cannot be changed")
    if rules.get("free_days_mode", "rolling28") not in {"rolling28", "fixed28"}:
        raise ModelInputError("Unsupported free-day rule mode")
    if len(data["needs"]) > budget["max_occurrences"]:
        raise ResourceBudgetExceeded("Occurrence budget exceeded; no needs dropped")
    if len(data["candidates"]) > budget["max_candidates"]:
        raise ResourceBudgetExceeded("Duty-domain budget exceeded; no candidates dropped")
    if len({n["id"] for n in data["needs"]}) != len(data["needs"]):
        raise ModelInputError("Duplicate occurrence IDs")
    employees = {e["id"]: e for e in data["employees"]}
    if len(employees) != len(data["employees"]) or any(
            e.get("is_vacant") or e.get("vacant") or
            str(e.get("alias", "")).strip().casefold() in {"vakant", "vakans", "vacant"}
            for e in employees.values()):
        raise ModelInputError("Duplicate employee IDs or vacancy posing as a person")
    if len({c["id"] for c in data["candidates"]}) != len(data["candidates"]):
        raise ModelInputError("Duplicate candidate IDs")
    frozen_by_person = defaultdict(list)
    for duty in data.get("frozen_duties", []):
        if duty.get("is_vacant"):
            raise ModelInputError("A vacancy cannot be frozen personal history")
        frozen_by_person[duty["employee_id"]].append(duty)
    context = {"data": data, "duties": {}, "needs": {}, "supports": [],
               "week_phases": {}, "historical_certificates": [],
               "unknown_controls": _unknown_facts(data), "support_count": 0}
    by_person = defaultdict(list)
    zone = ZoneInfo(period.get("timezone", "Europe/Stockholm"))
    min_duty = rules.get("min_duty_minutes", 240)
    for candidate in data["candidates"]:
        cid, employee_id = candidate["id"], candidate["employee_id"]
        if employee_id not in employees:
            raise ModelInputError(f"{cid}: no real employee")
        sb, eb = _bounds(candidate, "start"), _bounds(candidate, "end")
        if sb[0] < lo:
            raise ModelInputError(f"{cid}: mutable duty could edit frozen P1")
        bounds = (min(sb[0], eb[0]), max(sb[1], eb[1]))
        presence = model.NewBoolVar(cid + "_selected")
        if candidate.get("start_values"):
            start = model.NewIntVarFromDomain(cp_model.Domain.FromValues(candidate["start_values"]), cid + "_start")
            model.Add(start >= sb[0]); model.Add(start <= sb[1])
        else:
            start = model.NewIntVar(*sb, cid + "_start")
        end = model.NewIntVar(*eb, cid + "_end")
        span = model.NewIntVar(1, max(1, eb[1] - sb[0]), cid + "_span")
        model.Add(span == end - start)
        mode = candidate.get("mode", "CROP_SOURCE")
        if mode not in {"CROP_SOURCE", "SHIFT_COMPLETE", "WORK_AVAILABLE"}:
            raise ModelInputError(f"{cid}: unsupported duty-domain mode {mode}")
        if mode == "SHIFT_COMPLETE":
            length = candidate.get("fixed_duration_minutes", candidate["end"] - candidate["start"])
            model.Add(end == start + length)
            model.Add(span >= min_duty).OnlyEnforceIf(presence)
            if candidate.get("reference_jour", candidate.get("jour")) and not candidate.get("start_values"):
                raise ModelInputError(f"{cid}: shifted Jo needs explicit verified profile-compatible start_values")
            context["unknown_controls"].extend(_validate_shift(candidate, employees[employee_id], sb, zone, rules))
        else:
            # Whole mutable duties include retained original duties as well.
            model.Add(span >= min_duty).OnlyEnforceIf(presence)
        if mode == "WORK_AVAILABLE":
            context["unknown_controls"].extend(_validate_work_available(candidate, employees[employee_id], zone, rules))
        # A source row is evidence, never an exemption from the whole-duty rule.
        available = _presence_windows(employees[employee_id], candidate, diagnostic_only)
        windows = [[w["start"], w["end"]] for w in available]
        individual = candidate.get("individual_allowed_windows")
        if individual is not None:
            windows = [[max(a, x), min(b, y)] for a, b in windows for x, y in individual
                       if min(b, y) > max(a, x)]
        if not windows:
            model.Add(presence == 0)
        else:
            choices = []
            for index, (a, b) in enumerate(windows):
                if b < sb[0] or a > eb[1]:
                    continue
                choice = model.NewBoolVar(f"{cid}_available_{index}")
                model.Add(start >= a).OnlyEnforceIf(choice)
                model.Add(end <= b).OnlyEnforceIf(choice)
                choices.append(choice)
            model.Add(sum(choices) == presence)
        item = {"source": candidate, "presence": presence, "start": start, "end": end,
                "bounds": bounds, "work": [], "jour": [], "Ar_P2": []}
        for kind in ("work", "jour"):
            source_segments = candidate.get("reference_" + kind, candidate.get(kind, [])) if mode == "SHIFT_COMPLETE" else candidate.get(kind, [])
            for index, (a, b) in enumerate(merged_intervals(source_segments)):
                name = f"{cid}_{kind}_{index}"
                if mode == "SHIFT_COMPLETE":
                    reference = candidate.get("reference_start", candidate["start"])
                    left, right = start + a - reference, start + b - reference
                    minutes = b - a
                    active = presence
                else:
                    left, right, minutes = _clip(model, start, end, a, b, bounds, name)
                    positive = _lt(model, 0, minutes, name + "_positive")
                    active = _and(model, [presence, positive], name + "_active")
                    if kind == "jour":
                        whole = model.NewBoolVar(name + "_whole")
                        model.Add(minutes == b - a).OnlyEnforceIf(whole)
                        model.Add(minutes == 0).OnlyEnforceIf(whole.Not())
                selected = _selected_minutes(model, minutes, presence, b - a, name + "_selected_minutes")
                item[kind].append({"left": left, "right": right, "minutes": minutes,
                                   "active": active, "selected": selected, "reference": (a, b)})
                if kind == "work":
                    _, _, p2_minutes = _clip(model, left, right, lo, hi, bounds, name + "_P2")
                    item["Ar_P2"].append(_selected_minutes(model, p2_minutes, presence, hi - lo, name + "_P2_selected"))
        context["duties"][cid] = item
        by_person[employee_id].append(item)
        if eb[1] > hi:
            context["unknown_controls"].append({"candidate_id": cid,
                "field": "post_period_rest", "why": "Known outgoing duty remains whole; following post-period rest is not inferred from missing future duties"})
        long = _lt(model, 1199, span, cid + "_20h_or_longer")
        # The documented exceptional profile is 20--24h with at least five
        # continuous typed night-Jo hours. It is not an invented general cap on
        # every unclassified source row. New long active-only duties cannot
        # manufacture an exception. Compensation remains separately unknown.
        combined_profile = bool(candidate.get("work")) and bool(candidate.get("jour"))
        redesigned = candidate.get("variable") or candidate.get("is_new_or_shortened")
        if combined_profile or redesigned:
            model.Add(span <= 1440).OnlyEnforceIf([presence, long])
            night_supports = []
            for index, block in enumerate(item["jour"]):
                a, b = block["reference"]
                if mode == "SHIFT_COMPLETE":
                    reference = candidate.get("reference_start", candidate["start"])
                    for value in candidate["start_values"]:
                        if _longest_night_jour(a + value - reference, b + value - reference, zone) >= 300:
                            at_value = _and(model, [presence,
                                _lt(model, start, value + 1, f"{cid}_nightJo{index}_le_{value}"),
                                _lt(model, value - 1, start, f"{cid}_nightJo{index}_ge_{value}")],
                                f"{cid}_nightJo{index}_at_{value}")
                            night_supports.append(at_value)
                elif _longest_night_jour(a, b, zone) >= 300:
                    night_supports.append(block["active"])
            model.Add(sum(night_supports) >= 1).OnlyEnforceIf([presence, long])
        elif candidate["end"] - candidate["start"] >= 1200:
            context["unknown_controls"].append({"candidate_id": cid,
                "field": "long_duty_profile", "why": "Unclassified source long duty is not automatically an approved Ar/Jo exception"})
        longest_domain_span = candidate.get("fixed_duration_minutes", candidate["end"] - candidate["start"]) if mode == "SHIFT_COMPLETE" else eb[1] - sb[0]
        if longest_domain_span >= 1200 and rules.get("jour_compensation") is None:
            context["unknown_controls"].append({"candidate_id": cid,
                "field": "jour_compensation", "why": "Applicable post-long-duty compensation length and placement unknown"})
    # Duty-presence overlap and eleven-hour rest. Frozen/frozen breaches are
    # certificates, never false constraints that eliminate every future plan.
    rest = rules.get("daily_rest_minutes", 660)
    for employee_id, items in by_person.items():
        for i, first in enumerate(items):
            for second in items[i + 1:]:
                p, q = first["presence"], second["presence"]
                before = model.NewBoolVar(f"order_{first['source']['id']}_{second['source']['id']}")
                model.Add(first["end"] + rest <= second["start"]).OnlyEnforceIf([p, q, before])
                model.Add(second["end"] + rest <= first["start"]).OnlyEnforceIf([p, q, before.Not()])
            for fixed in frozen_by_person[employee_id]:
                before = model.NewBoolVar(f"frozen_order_{first['source']['id']}_{fixed['id']}")
                model.Add(first["end"] + rest <= fixed["start"]).OnlyEnforceIf([first["presence"], before])
                model.Add(fixed["end"] + rest <= first["start"]).OnlyEnforceIf([first["presence"], before.Not()])
    # An exact target includes the frozen incoming duty's actual P2 Ar slices.
    for employee_id, employee in employees.items():
        fixed = sum(overlap(a, b, lo, hi) for duty in frozen_by_person[employee_id] for a, b in duty.get("work", []))
        mode = data.get("target_mode", "PRESERVE_SOURCE_AR")
        if mode == "PRESERVE_SOURCE_AR":
            target = employee.get("planned_Ar_target_minutes")
            # Verified temporary workers have a decision workload, rather than
            # an invented contractual promise to repeat historical hours.
            if employee.get("staffing_type") == "TEMPORARY_VERIFIED" and employee.get("preserve_Ar_target") is not True:
                continue
        elif mode == "VERIFIED_CONTRACT":
            target = employee.get("contract_target_minutes") if employee.get("contract_target_status") == "VERIFIED" else None
        else:
            raise ModelInputError("Unrecognized target mode")
        if target is None:
            raise ModelInputError(f"{employee_id}: selected target is unknown; no zero default")
        if not isinstance(target, int) or isinstance(target, bool) or target < 0:
            raise ModelInputError(f"{employee_id}: invalid exact-minute person target")
        model.Add(sum(v for duty in by_person[employee_id] for v in duty["Ar_P2"]) + fixed == target)
    # Actual touched calendar days, including Jo and cross-midnight duties.
    days = _civil_days(history_lo, hi, zone)
    context["calendar_days"] = days
    for employee_id, employee in employees.items():
        occupied = []
        frozen_occupied = []
        for day, a, b in days:
            fixed = int(any(overlap(d["start"], d["end"], a, b) for d in frozen_by_person[employee_id]))
            frozen_occupied.append(fixed)
            occupied_by_candidate = []
            for duty in by_person[employee_id]:
                if duty["bounds"][1] <= a or duty["bounds"][0] >= b:
                    continue
                has_left = _lt(model, duty["start"], b, duty["source"]["id"] + "_before_" + day)
                has_right = _lt(model, a, duty["end"], duty["source"]["id"] + "_after_" + day)
                occupied_by_candidate.append(_and(model, [duty["presence"], has_left, has_right], duty["source"]["id"] + "_touches_" + day))
            flag = model.NewBoolVar(f"{employee_id}_occupied_{day}")
            if fixed:
                model.Add(flag == 1)
            elif occupied_by_candidate:
                model.AddMaxEquality(flag, occupied_by_candidate)
            else:
                model.Add(flag == 0)
            occupied.append(flag)
        for index in range(len(days) - 27):
            window = days[index:index + 28]
            if window[-1][2] <= lo:
                continue
            if rules.get("free_days_mode", "rolling28") == "fixed28" and window[0][1] != lo:
                continue
            if not employee.get("history_known", False) and window[0][1] < lo:
                context["unknown_controls"].append({"employee_id": employee_id, "field": "rolling_free_days_history", "start": window[0][1], "end": window[-1][2]})
                continue
            frozen_count = sum(frozen_occupied[index:index + 28])
            allowed = 28 - rules.get("min_free_days", 9)
            if frozen_count > allowed:
                context["historical_certificates"].append({"rule": "rolling_free_days", "employee_id": employee_id, "start": window[0][1], "end": window[-1][2], "frozen_occupied_days": frozen_count, "cap_occupied_days": allowed})
                model.Add(sum(occupied[index:index + 28]) == frozen_count)
            else:
                model.Add(sum(occupied[index:index + 28]) <= allowed)
    # Exact rolling Jo: source cropping keeps a whole source Jo or no Jo.
    # Shifted profiles are finite verified start_values, so all endpoint extrema
    # and frozen-cap crossings can be included without minute-grid sampling.
    for employee_id, employee in employees.items():
        items = by_person[employee_id]
        basis_candidates, term_presence = [], {}
        for duty in items:
            source = duty["source"]
            for index, block in enumerate(duty["jour"]):
                a, b = block["reference"]
                if source.get("mode") == "SHIFT_COMPLETE":
                    reference = source.get("reference_start", source["start"])
                    for start_value in source["start_values"]:
                        phase = _and(model, [duty["presence"], _lt(model, duty["start"], start_value + 1, f"{source['id']}_at_le_{start_value}"), _lt(model, start_value - 1, duty["start"], f"{source['id']}_at_ge_{start_value}")], f"{source['id']}_at_{start_value}")
                        jid = f"{source['id']}_Jo{index}_at{start_value}"
                        basis_candidates.append({"id": jid, "employee_id": employee_id, "jour": [[a + start_value - reference, b + start_value - reference]]})
                        term_presence[jid] = phase
                else:
                    jid = f"{source['id']}_Jo{index}"
                    basis_candidates.append({"id": jid, "employee_id": employee_id, "jour": [[a, b]]})
                    term_presence[jid] = block["active"]
        windows = jour_windows(frozen_by_person[employee_id], basis_candidates, lo, hi + rules.get("jour_window_minutes", ROLLING), rules.get("jour_window_minutes", ROLLING), rules.get("jour_cap_minutes", 2880))
        for window in windows:
            model.Add(sum(minutes * term_presence[jid] for jid, minutes in window["terms"]) <= window["mutable_allowance_minutes"])
            if window["historical_excess_minutes"]:
                context["historical_certificates"].append({"rule": "rolling_jour", "employee_id": employee_id, **window})
    # One freely chosen fixed weekly anchor per employee. For a span without a
    # civil UTC-offset transition, a minute phase covers every possible local
    # weekday/clock combination exactly. Do not silently apply it across DST.
    offsets = {datetime.fromtimestamp(t * 60, timezone.utc).astimezone(zone).utcoffset() for _, a, b in days for t in (a, b - 1)}
    if len(offsets) != 1:
        raise ModelInputError("Weekly variable-anchor implementation requires a DST-aware calendar extension for this period")
    week_rest = rules.get("weekly_rest_minutes", 2160)
    for employee_id, employee in employees.items():
        known_lo = history_lo if employee.get("history_known", False) else lo
        anchor = rules.get("week_anchor")
        phase = model.NewIntVar(0, WEEK - 1, employee_id + "_fixed_week_phase")
        if anchor is not None:
            model.Add(phase == (utc_minute(anchor) - history_lo) % WEEK)
        context["week_phases"][employee_id] = phase
        for index in range(-1, (hi - history_lo) // WEEK + 1):
            week_start = history_lo + index * WEEK + phase
            week_end = week_start + WEEK
            inside_left = _lt(model, known_lo - 1, week_start, f"{employee_id}_week{index}_known_left")
            inside_right = _lt(model, week_end, hi + 1, f"{employee_id}_week{index}_known_right")
            touches_p2 = _lt(model, lo, week_end, f"{employee_id}_week{index}_touches_p2")
            enforce = _and(model, [inside_left, inside_right, touches_p2], f"{employee_id}_week{index}_active")
            rest_start = model.NewIntVar(history_lo + index * WEEK, history_lo + (index + 2) * WEEK, f"{employee_id}_week{index}_rest_start")
            model.Add(rest_start >= week_start).OnlyEnforceIf(enforce)
            model.Add(rest_start + week_rest <= week_end).OnlyEnforceIf(enforce)
            for duty in by_person[employee_id]:
                before = model.NewBoolVar(f"{duty['source']['id']}_before_week{index}_rest")
                model.Add(duty["end"] <= rest_start).OnlyEnforceIf([enforce, duty["presence"], before])
                model.Add(duty["start"] >= rest_start + week_rest).OnlyEnforceIf([enforce, duty["presence"], before.Not()])
            for fixed in frozen_by_person[employee_id]:
                before = model.NewBoolVar(f"{fixed['id']}_before_week{index}_rest")
                model.Add(fixed["end"] <= rest_start).OnlyEnforceIf([enforce, before])
                model.Add(fixed["start"] >= rest_start + week_rest).OnlyEnforceIf([enforce, before.Not()])
    # Full standard 11h/24h arithmetic is separate from pairwise duty gaps.
    # The unknown local daily anchor is explicit in this bounded scenario.
    add_standard_daily_rest(model, context)
    # Whole needs: one common start, exactly count different real people, each
    # within one actual active-Ar interval. Jo is never customer capacity.
    assignments_by_person = defaultdict(list)
    for need in data["needs"]:
        nid = need["id"]
        if not isinstance(need.get("count"), int) or isinstance(need.get("count"), bool) or need["count"] < 1:
            raise ModelInputError(f"{nid}: personnel count must be a positive source-supported integer")
        if need.get("count_confirmed") is not None and need["count_confirmed"] != need["count"]:
            raise ModelInputError(f"{nid}: confirmed personnel count contradicts the represented count")
        semantics = need.get("window_semantics")
        if semantics not in ("EXECUTION_WINDOW", "START_WINDOW"):
            raise ModelInputError(f"{nid}: window meaning requires a reviewed decision")
        latest_start = need["latest_end"] - need["duration"] if semantics == "EXECUTION_WINDOW" else need["latest_end"]
        latest_start = min(latest_start, hi - need["duration"])
        if need["duration"] <= 0 or need["earliest"] > latest_start:
            raise ModelInputError(f"{nid}: impossible duration/window; no automatic repair")
        if overlap(need["earliest"], need["latest_end"], lo, hi) == 0:
            raise ModelInputError(f"{nid}: execution window does not intersect selected P2; no silent period remapping")
        coverage = model.NewBoolVar(nid + "_fully_covered")
        start = model.NewIntVar(need["earliest"], latest_start, nid + "_start")
        blockers = list(need.get("blockers", []))
        if need.get("movable") is False and need.get("locked_start") is None:
            blockers.append("LOCKED_PLAN_START_UNKNOWN")
        if need.get("count_confirmed") is None:
            blockers.append("PERSONNEL_COUNT_UNCONFIRMED")
        if need.get("locked_start") is not None:
            model.Add(start == need["locked_start"])
        supports, per_person = [], defaultdict(list)
        eligible = set(need.get("eligible_employee_ids", []))
        if "qualification_matching_employee_ids" in need:
            eligible &= set(need["qualification_matching_employee_ids"])
        missing_employee_ids = eligible - set(employees)
        if missing_employee_ids:
            raise ModelInputError(f"{nid}: eligibility references no real employee {sorted(missing_employee_ids)}")
        profession = need.get("required_profession_source")
        required_skills = need.get("required_skills_confirmed")
        for employee_id in list(eligible):
            skills = employees.get(employee_id, {}).get("skills_known")
            if profession not in (None, "Ingen yrkesgrupp") and (not isinstance(skills, list) or profession not in skills):
                eligible.remove(employee_id)
            elif isinstance(required_skills, list) and required_skills and (not isinstance(skills, list) or not set(required_skills) <= set(skills)):
                eligible.remove(employee_id)
        if not blockers:
            for employee_id in sorted(eligible):
                if employee_id not in employees:
                    raise ModelInputError(f"{nid}: eligibility references no real employee")
                for duty in by_person[employee_id]:
                    for index, block in enumerate(duty["work"]):
                        a, b = block["reference"]
                        source = duty["source"]
                        if source.get("mode") != "SHIFT_COMPLETE" and (b < need["earliest"] + need["duration"] or a > latest_start):
                            continue
                        context["support_count"] += 1
                        if context["support_count"] > budget["max_supports"]:
                            raise ResourceBudgetExceeded("Assignment-support budget exceeded; no needs/candidates truncated")
                        support = model.NewBoolVar(f"{nid}_{source['id']}_Ar{index}")
                        model.Add(support <= duty["presence"])
                        model.Add(start >= block["left"]).OnlyEnforceIf(support)
                        model.Add(start + need["duration"] <= block["right"]).OnlyEnforceIf(support)
                        interval = model.NewOptionalFixedSizeIntervalVar(start, need["duration"], support, f"{nid}_{source['id']}_Ar{index}_interval")
                        assignments_by_person[employee_id].append((interval, nid))
                        supports.append(support); per_person[employee_id].append(support)
                        context["supports"].append({"need_id": nid, "employee_id": employee_id, "candidate_id": source["id"], "presence": support, "start": start, "duration": need["duration"]})
                for fixed in frozen_by_person[employee_id]:
                    for index, (a, b) in enumerate(merged_intervals(fixed.get("work", []))):
                        if overlap(a, b, lo, hi) == 0 or b < need["earliest"] + need["duration"] or a > latest_start:
                            continue
                        context["support_count"] += 1
                        if context["support_count"] > budget["max_supports"]:
                            raise ResourceBudgetExceeded("Assignment-support budget exceeded; frozen Ar not dropped")
                        support = model.NewBoolVar(f"{nid}_{fixed['id']}_frozenAr{index}")
                        model.Add(start >= a).OnlyEnforceIf(support)
                        model.Add(start + need["duration"] <= b).OnlyEnforceIf(support)
                        interval = model.NewOptionalFixedSizeIntervalVar(start, need["duration"], support, f"{nid}_{fixed['id']}_frozenAr{index}_interval")
                        assignments_by_person[employee_id].append((interval, nid))
                        supports.append(support); per_person[employee_id].append(support)
                        context["supports"].append({"need_id": nid, "employee_id": employee_id,
                            "candidate_id": fixed["id"], "presence": support, "start": start,
                            "duration": need["duration"], "frozen": True})
        for supports_person in per_person.values():
            model.Add(sum(supports_person) <= coverage)
        model.Add(sum(supports) == need["count"] * coverage)
        if blockers:
            model.Add(coverage == 0)
        context["needs"][nid] = {"source": need, "coverage": coverage, "start": start,
                                  "blockers": sorted(set(blockers)), "supports": supports}
    for entries in assignments_by_person.values():
        intervals = [interval for interval, nid in entries]
        shared = {nid for interval, nid in entries if concurrency and concurrency[nid] == 'SHARED'}
        if not shared:
            model.AddNoOverlap(intervals)
        else:
            # An exclusive task occupies this employee completely. Shared
            # tasks can overlap; each need still requires its own distinct,
            # eligible performers at its actual start. The integer capacity
            # is an encoding bound, not an invented business concurrency cap.
            capacity = len(shared)
            model.AddCumulative(intervals,
                [1 if concurrency[nid] == 'SHARED' else capacity for interval, nid in entries], capacity)
    coverage_total = sum(n["coverage"] for n in context["needs"].values())
    model.Maximize(coverage_total)
    context["coverage_total"] = coverage_total
    context["temporary_minutes"] = sum(v for duty in context["duties"].values() if duty["source"].get("staffing_type") == "TEMPORARY_VERIFIED" for v in duty["Ar_P2"])
    context["unfilled_need_person_minutes"] = sum(
        need["source"]["count"] * need["source"]["duration"] * (1 - need["coverage"])
        for need in context["needs"].values())
    context["phase2_time_objective"] = context["temporary_minutes"] + context["unfilled_need_person_minutes"]
    context["phase2_unknown_staffing"] = [e["id"] for e in employees.values() if e.get("staffing_type") == "UNKNOWN" and by_person[e["id"]]]
    context["phase2_unknown_requirement_counts"] = [n["id"] for n in data["needs"] if n.get("count_confirmed") is None]
    proto = model.Proto()
    with tempfile.NamedTemporaryFile(suffix=".bin", prefix="bb-availability-model-") as exported:
        if not model.ExportToFile(exported.name):
            raise ModelInputError("Unable to measure binary model representation")
        proto_bytes = Path(exported.name).stat().st_size
    context["build_metrics"] = {"build_wall_seconds": round(time.perf_counter() - began, 6),
        "input_needs": len(data["needs"]), "retained_needs": len(context["needs"]),
        "candidate_domains": len(context["duties"]), "assignment_supports": context["support_count"],
        "variables": len(proto.variables), "constraints": len(proto.constraints),
        "model_proto_bytes": proto_bytes, "peak_RSS_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "previous_peak_RSS_KiB": rss_before, "period_split": False,
        "weekly_anchor_representation": "ONE_EXACT_INTEGER_MINUTE_FIXED_PHASE_PER_PERSON"}
    return model, context


def _result_duties(context, solver):
    result = []
    for cid, item in context["duties"].items():
        if not solver.Value(item["presence"]):
            continue
        start, end = solver.Value(item["start"]), solver.Value(item["end"])
        source = item["source"]
        exported = {**copy.deepcopy(source), "start": start, "end": end, "work": [], "jour": []}
        for kind in ("work", "jour"):
            for block in item[kind]:
                if solver.Value(block["selected"]):
                    left, right = solver.Value(block["left"]), solver.Value(block["right"])
                    exported[kind].append([left, right])
        changed = start != source["start"] or end != source["end"]
        exported["is_original"] = bool(source.get("is_original")) and not changed
        exported["is_new_or_shortened"] = bool(source.get("is_new_or_shortened")) or changed
        result.append(exported)
    return result
