"""Independent validation for the reviewed availability scenario.

This module intentionally imports no model, adapter, or shared time helper.  It
recalculates the controls from the public input and exported schedule.  All
intervals are half-open; integer times are absolute UTC Unix minutes.
Unknown contracts or boundary information remain UNKNOWN.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from hashlib import sha256
import json
from math import ceil, floor
from zoneinfo import ZoneInfo


DAY = 1440
WEEK = 7 * DAY
ROLLING = 28 * DAY
FEASIBLE_STATUSES = {"OPTIMAL", "FEASIBLE"}


def _reviewed_shared_needs(data, issue, unknown):
    """Independently check decision provenance; do not import the model/parser."""
    needs = data.get('needs', [])
    if 'concurrency_policy' not in data:
        if any('concurrency' in n for n in needs):
            issue('concurrency_decision', 'Concurrency classifications have no reviewed policy')
        return set()
    p = data['concurrency_policy']
    text = lambda v: isinstance(v, str) and bool(v.strip())
    context = data.get('integration', {})
    if (not isinstance(p, dict) or set(p) != {'schema_version', 'mode', 'status', 'decision_id', 'source', 'business_id', 'source_identity', 'period_lo', 'period_hi'}
            or p.get('schema_version') != 'bb-concurrency-policy/1.0'
            or p.get('mode') != 'EXPLICIT_PER_NEED_COMPATIBILITY'
            or p.get('status') not in ('SCENARIO', 'CONFIRMED_BY_USER')
            or not all(text(p.get(k)) for k in ('decision_id', 'source', 'business_id', 'source_identity'))
            or p.get('period_lo') != data['period']['lo'] or p.get('period_hi') != data['period']['hi']
            or p.get('business_id') != context.get('business_id')
            or p.get('source_identity') != context.get('source_identity')):
        issue('concurrency_decision', 'Concurrency policy is missing or belongs to another source, period or business')
        return set()
    shared, valid = set(), True
    for need in needs:
        row_valid = True
        d, row = need.get('concurrency'), need.get('original_submitted_row')
        if (not isinstance(d, dict) or set(d) != {'mode', 'decision_id', 'source_ref', 'source_row_sha256', 'reason'}
                or d.get('mode') not in ('SHARED', 'EXCLUSIVE', 'UNCLASSIFIED')
                or d.get('decision_id') != p['decision_id']
                or not text(d.get('source_ref')) or not text(d.get('reason'))
                or not isinstance(row, dict) or row.get('need_id') != need['id']):
            row_valid = False
        else:
            digest = sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            if d.get('source_row_sha256') != digest:
                row_valid = False
            elif d['mode'] == 'SHARED':
                shared.add(need['id'])
            elif d['mode'] == 'UNCLASSIFIED':
                unknown('concurrency_classification', 'Unclassified activity remains exclusive; no sharing inferred', need_id=need['id'])
        if not row_valid:
            valid = False
            issue('concurrency_decision', 'Activity concurrency decision is not bound to its actual source row', need_id=need['id'])
    if valid:
        unknown('practical_concurrency', 'Explicit sharing is a mathematical scenario; active attention, location and travel remain unverified', decision_id=p['decision_id'])
    return shared if valid else set()


def _origin(data):
    value = data["period"]["start"]
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=ZoneInfo(data["period"].get("tz", data["period"].get("timezone", "Europe/Stockholm"))))


def _minute(value, origin):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a time")
    if isinstance(value, (int, float)):
        if value != int(value):
            raise ValueError("Non-integer minute")
        return int(value)
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    # Wall-clock exports without timezone are interpreted in the same calendar
    # as the origin.  Aware exports are compared in UTC (including DST).
    if dt.tzinfo is None and origin.tzinfo is not None:
        dt = dt.replace(tzinfo=origin.tzinfo)
    seconds = dt.timestamp()
    if seconds % 60:
        raise ValueError("Time has sub-minute precision")
    return int(seconds // 60)


def _interval(value, origin):
    if isinstance(value, dict):
        start, end = value["start"], value["end"]
    else:
        start, end = value
    a, b = _minute(start, origin), _minute(end, origin)
    if b <= a:
        raise ValueError(f"Invalid interval [{a}, {b})")
    return a, b


def _union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _overlap(intervals, start, end):
    return sum(max(0, min(b, end) - max(a, start)) for a, b in _union(intervals))


def _inside(intervals, start, end):
    return _overlap(intervals, start, end) == end - start


def _longest_free(intervals, start, end):
    cursor, best = start, 0
    for a, b in _union(intervals):
        if b <= start or a >= end:
            continue
        a, b = max(start, a), min(end, b)
        best = max(best, a - cursor)
        cursor = max(cursor, b)
    return max(best, end - cursor)


def _stamp(origin, minute):
    return datetime.fromtimestamp(minute * 60, timezone.utc).astimezone(origin.tzinfo).isoformat(timespec="minutes")


def _day_intervals(origin, tz_name, start, end):
    """Calendar days, rather than one day per pass or 24-hour work totals."""
    zone = ZoneInfo(tz_name) if tz_name else origin.tzinfo
    moment = datetime.fromtimestamp(start * 60, timezone.utc).astimezone(zone or origin.tzinfo)
    date = moment.date()
    result = []
    while True:
        begin = datetime.combine(date, datetime.min.time(), tzinfo=zone)
        finish = datetime.combine(date + timedelta(days=1), datetime.min.time(), tzinfo=zone)
        a, b = _minute(begin, origin), _minute(finish, origin)
        if a >= end:
            break
        if b > start:
            result.append((date.isoformat(), a, b))
        date += timedelta(days=1)
    return result


def _clock_windows(origin, zone_name, start, end, start_clock, end_clock):
    """Only a supplied business time profile defines a role's clock window."""
    start_hour, start_minute = map(int, start_clock.split(":"))
    end_hour, end_minute = map(int, end_clock.split(":"))
    if not (0 <= start_hour < 24 and 0 <= end_hour < 24 and 0 <= start_minute < 60 and 0 <= end_minute < 60):
        raise ValueError("Invalid verified role clock window")
    zone = ZoneInfo(zone_name) if zone_name else origin.tzinfo
    date = datetime.fromtimestamp(start * 60, zone).date() - timedelta(days=1)
    last = datetime.fromtimestamp(end * 60, zone).date()
    result = []
    while date <= last:
        begin = datetime.combine(date, datetime.min.time(), tzinfo=zone) + timedelta(hours=start_hour, minutes=start_minute)
        finish = datetime.combine(date, datetime.min.time(), tzinfo=zone) + timedelta(hours=end_hour, minutes=end_minute)
        if finish <= begin:
            finish += timedelta(days=1)
        a, b = _minute(begin, origin), _minute(finish, origin)
        if a < end and b > start:
            result.append((max(a, start), min(b, end)))
        date += timedelta(days=1)
    return result


def _rule_value(rules, names, default):
    for name in names:
        if name in rules:
            return rules[name]
    return default


def _known_limits(data, origin, lo, hi, frozen):
    # P1/P2 period provenance is required to certify the boundary.  An earliest
    # observed duty is not proof that the preceding interval was free.
    period = data["period"]
    known_lo = period.get("history_lo", period.get("known_history_start", data.get("history_start")))
    known_hi = period.get("known_end", period.get("known_history_end", period.get("end_exclusive")))
    inferred = known_lo is None
    known_lo = min([lo - ROLLING] + [d["start"] for d in frozen]) if known_lo is None else _minute(known_lo, origin)
    known_hi = hi if known_hi is None else _minute(known_hi, origin)
    return known_lo, known_hi, inferred


def _normal_duty(raw, origin, frozen=False):
    a, b = _minute(raw["start"], origin), _minute(raw["end"], origin)
    if b <= a:
        raise ValueError(f"Duty {raw.get('id')} has invalid bounds")
    work = [_interval(v, origin) for v in raw.get("work", [])]
    jour = [_interval(v, origin) for v in raw.get("jour", [])]
    if any(x < a or y > b for x, y in work + jour):
        raise ValueError(f"Segment outside duty {raw.get('id')}")
    if any(max(x, u) < min(y, v) for x, y in work for u, v in jour):
        raise ValueError(f"Ar/Jo overlap in duty {raw.get('id')}")
    return {**raw, "start": a, "end": b, "work": work, "jour": jour, "frozen": frozen}


def _minute_runs(values):
    result = []
    for value in sorted(set(values)):
        if result and value == result[-1][1] + 1:
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def _standard_daily_assessment(duties, hist_duties, employee, period, lo, hi,
                               known_lo, known_hi, requested_anchor, exceptions_enabled,
                               anchor_decision=None):
    """Independent fixed-24h examination, with no model/shared-time import.

    If no anchor was exported, examine all 1440 integer phases, not a clock
    sample. The chosen witness is explicitly a post-hoc mathematical scenario,
    never a claim that the old solver selected a confirmed local daily anchor.
    Frozen-only shortfalls are separate; adding work may not worsen them.
    """
    base = period.get("history_lo", lo)
    presence = _union([(d["start"], d["end"]) for d in duties])
    frozen = _union([(d["start"], d["end"]) for d in hist_duties])
    ar = _union([v for d in duties for v in d["work"]])
    jour = _union([v for d in duties for v in d["jour"]])
    typed = _union(ar + jour)
    exceptional, rejected = [], []
    zone = ZoneInfo(period.get("timezone", "Europe/Stockholm"))
    for index, (a, b) in enumerate(typed):
        if not exceptions_enabled or not _overlap(ar, a, b) or not _overlap(jour, a, b):
            continue
        longest_night = 0
        date = datetime.fromtimestamp(a * 60, timezone.utc).astimezone(zone).date() - timedelta(days=1)
        last = datetime.fromtimestamp(b * 60, timezone.utc).astimezone(zone).date()
        while date <= last:
            night_a = int((datetime.combine(date, datetime.min.time(), zone) + timedelta(hours=22)).timestamp() // 60)
            night_b = int((datetime.combine(date + timedelta(days=1), datetime.min.time(), zone) + timedelta(hours=8)).timestamp() // 60)
            portions = _union([(max(x, night_a, a), min(y, night_b, b)) for x, y in jour
                if max(x, night_a, a) < min(y, night_b, b)])
            longest_night = max(longest_night, max((y - x for x, y in portions), default=0))
            date += timedelta(days=1)
        following = typed[index + 1][0] if index + 1 < len(typed) else None
        inherited = _inside(frozen, a, b)
        gap_ok = following is None or following - b >= b - a
        if longest_night >= 300 and b - a <= DAY and (inherited or b - a <= 1200) and gap_ok:
            exceptional.append((a, b))
        else:
            rejected.append({"interval": [a, b], "longest_night_jour_minutes": longest_night,
                "following_start": following, "required_following_rest_minutes": b - a,
                "observed_following_rest_minutes": following - b if following is not None else None,
                "why": "NO_BLANKET_B_WAIVER_WITHOUT_FULL_NIGHT_LENGTH_AND_COMPENSATION_ARITHMETIC"})
    confirmed_scenario_anchor = (isinstance(anchor_decision, dict)
        and anchor_decision.get("status") == "CONFIRMED" and anchor_decision.get("scope") == "TEST_SCENARIO_ONLY"
        and bool(anchor_decision.get("source_ref")) and anchor_decision.get("mode") == "MODEL_SELECTED_FIXED_PHASE_SCENARIO")

    relevant_hi = max([hi] + [b for a, b in presence])

    def examine(phase, retain=False):
        rows, new, historical = [], 0, 0
        for index in range(-1, (relevant_hi - base) // DAY + 1):
            a = base + index * DAY + phase
            b = a + DAY
            if b <= known_lo or a >= relevant_hi:
                continue
            fully_known = a >= known_lo and b <= known_hi
            longest = _longest_free(presence, a, b)
            baseline = _longest_free(frozen, a, b)
            ex = [(x, y) for x, y in exceptional if max(x, a) < min(y, b)]
            status, inherited, worsened = "PASS_STANDARD_ARITHMETIC", False, False
            mixed = False
            if longest < 660 and ex:
                # If a second disjoint whole duty touches this period, their
                # full >=11h gap is inside it. If that premise is broken, do
                # not let proximity to Jo waive the pure-Ar violation.
                nonexceptional = [(x, y) for x, y in typed
                    if max(x, a) < min(y, b) and (x, y) not in ex]
                mixed = bool(nonexceptional) or len(ex) > 1
                if mixed:
                    status = "FAIL_MIXED_EXCEPTION_SAFETY"
                    inherited = baseline < 660 and longest >= baseline
                else:
                    status = "B_C_EXCEPTION_ARITHMETIC_ONLY"
            elif longest < 660:
                inherited = baseline < 660
                worsened = inherited and longest < baseline
                status = "FROZEN_STANDARD_SHORTFALL" if inherited and not worsened else "FAIL_STANDARD_11H_IN_24H"
            elif not fully_known:
                status = "UNKNOWN_OUTSIDE_VERIFIED_HORIZON"
            is_new = (b > lo and status.startswith("FAIL") and (not inherited or worsened))
            is_historical = longest < 660 and status != "B_C_EXCEPTION_ARITHMETIC_ONLY" and (b <= lo or inherited)
            new += int(is_new)
            historical += int(is_historical)
            if retain:
                rows.append({"start": a, "end": b, "longest_rest_minutes": longest,
                    "frozen_longest_rest_minutes": baseline, "standard_rest_minutes": 660,
                    "status": status, "historical_shortfall": is_historical,
                    "new_violation": is_new, "worsens_frozen_rest": worsened,
                    "exception_chains": [list(v) for v in ex],
                    "mixed_exception_window": mixed,
                    "exception_application_status": "UNKNOWN" if ex else "NOT_APPLICABLE",
                    "fully_known": fully_known,
                    "maximum_possible_rest_minutes": longest if not fully_known else None,
                    "outer_bound_kind": "OPTIMISTIC_NECESSARY_ONLY_NEVER_APPROVAL" if not fully_known else None})
        return new, historical, rows

    allowed, historical_counts = [], []
    for phase in range(DAY):
        new, hist, _ = examine(phase)
        if not new:
            allowed.append(phase)
            historical_counts.append(hist)
    selected = None
    exported = isinstance(requested_anchor, dict) and isinstance(requested_anchor.get("phase_minutes"), int)
    if exported:
        value = requested_anchor["phase_minutes"]
        if isinstance(value, bool) or not 0 <= value < DAY:
            return {"arithmetic_status": "FAIL_INVALID_ANCHOR", "selected_phase_minutes": value,
                "anchor_application_status": "UNKNOWN", "windows": [], "long_active_only_duties": []}
        selected = value
    elif allowed:
        selected = allowed[0]
    else:
        # Retain a complete diagnostic witness without presenting it as a
        # feasible phase when every constant phase has a new violation.
        selected = min(range(DAY), key=lambda value: examine(value)[:2])
    new, hist, rows = examine(selected, retain=True)
    long_pure = []
    for a, b in typed:
        if b - a <= DAY - 660 or not _overlap(ar, a, b) or _overlap(jour, a, b):
            continue
        if _inside(frozen, a, b):
            continue
        touching = [row for row in rows if max(a, row["start"]) < min(b, row["end"])]
        outer_touching = [row for row in touching if not row["fully_known"]]
        long_pure.append({"interval": [a, b], "duration_minutes": b - a,
            "Ar_minutes": _overlap(ar, a, b), "Jo_minutes": 0,
            "fixed_phase_arithmetic_status": "FAIL" if any(v["new_violation"] for v in touching)
                else "UNKNOWN_BOUNDARY" if outer_touching or not touching else "PASS",
            "anchor_application_status": "CONFIRMED_SCENARIO_ANCHOR_SELECTION" if confirmed_scenario_anchor else "UNKNOWN",
            "operational_local_anchor_status": "UNKNOWN", "selected_phase_minutes": selected,
            "touching_periods": touching, "B_C_exception_available": False,
            "universal_13h_cap_applied": False})
    return {"mode": "FIXED_PHASE_STANDARD_WITH_SEPARATE_AR_JO_EXCEPTIONS",
        "arithmetic_status": "PASS_FOR_EXPORTED_PHASE" if exported and not new else
            "PASS_EXISTS_FIXED_PHASE" if not new else "FAIL_EXPORTED_PHASE" if exported else "FAIL_ALL_FIXED_PHASES",
        "selected_phase_minutes": selected,
        "anchor_status": requested_anchor.get("status", "MODEL_EXPORTED_PHASE_SCENARIO") if exported else "POST_HOC_FIXED_PHASE_WITNESS_NOT_EXPORTED_BY_OLD_SOLVER",
        "anchor_application_status": "CONFIRMED_SCENARIO_ANCHOR_SELECTION" if confirmed_scenario_anchor else "UNKNOWN",
        "operational_local_anchor_status": "UNKNOWN", "anchor_decision": anchor_decision,
        "same_phase_entire_known_horizon": True,
        "tested_integer_phases": DAY, "new_violation_free_phase_count": len(allowed),
        "new_violation_free_phase_intervals": _minute_runs(allowed),
        "selected_phase_new_violations": new, "selected_phase_historical_shortfalls": hist,
        "historical_shortfall_count_range_for_new_violation_free_phases":
            [min(historical_counts), max(historical_counts)] if historical_counts else None,
        "windows": rows, "long_active_only_duties": long_pure,
        "combined_chains_rejected_as_exception": rejected,
        "outer_periods": "UNKNOWN_OUTSIDE_VERIFIED_HORIZON",
        "interpretation_is_not_confirmed_local_rule": True}


def validate(data, result):
    """Return independently recalculated coverage, rules, and uncertainty.

    A time-limited UNKNOWN/INFEASIBLE result is never treated as a proposed
    schedule.  Historical controls are still evaluated and retained.
    """
    origin = _origin(data)
    period = data["period"]
    lo = _minute(period.get("lo", period["start"]), origin)
    hi = _minute(period.get("hi", period["end_exclusive"]), origin)
    rules = data.get("rules", {})
    minimum_pass = int(_rule_value(rules, ("min_pass_minutes", "min_duty_minutes", "min240", "minimum_pass_minutes"), 240))
    minimum_days = int(_rule_value(rules, ("minimum_free_days", "min_free_days", "min9"), 9))
    daily = int(_rule_value(rules, ("daily_rest_minutes", "daily660"), 660))
    weekly = int(_rule_value(rules, ("weekly_rest_minutes", "weekly2160"), 2160))
    jour_cap = int(_rule_value(rules, ("jour_cap_minutes", "jour2880"), 2880))
    jour_length = int(_rule_value(rules, ("jour_window_minutes", "rolling40320"), ROLLING))
    compensation_profile = rules.get("jour_compensation")
    dynamic_requested = (isinstance(compensation_profile, dict)
                         and compensation_profile.get("mode") == "PLANNED_AR_JO_REST_AT_LEAST_DUTY_SPAN")
    dynamic_verified = (dynamic_requested
                        and compensation_profile.get("source_status") == "VERIFIED"
                        and bool(compensation_profile.get("source_ref")))
    solver_status = str(result.get("solver_status", result.get("status", "UNKNOWN"))).upper()
    feasible = solver_status in FEASIBLE_STATUSES
    report = {
        "schema_version": "bb-availability-validation/1",
        "solver_status": solver_status,
        "status": "UNKNOWN" if feasible else "NO_PROPOSED_SCHEDULE",
        "schedule_status": "PENDING_CHECKS" if feasible else "NO_PROPOSED_SCHEDULE",
        "rules": [], "violations": {"historical": [], "new": []},
        "unknown_controls": [], "metrics": {},
        "coverage": {"status": "NOT_CHECKABLE", "input_need_count": len(data.get("needs", [])), "assigned_needs": None, "unassigned_needs": None},
        "historical_jour_windows": [], "new_jour_windows": [],
        "assumptions": {"breaks": "EXCLUDED_BY_SCENARIO", "SSG": "NEVER_INFERRED_FROM_PLANNED_AR"},
    }

    def issue(rule, detail, historical=False, **context):
        item = {"rule": rule, "detail": detail, **context}
        report["violations"]["historical" if historical else "new"].append(item)

    def unknown(rule, detail, **context):
        item = {"rule": rule, "detail": detail, **context}
        if item not in report["unknown_controls"]:
            report["unknown_controls"].append(item)

    def rule_status(rule, details=None, applicable=True):
        new = [x for x in report["violations"]["new"] if x["rule"] == rule]
        hist = [x for x in report["violations"]["historical"] if x["rule"] == rule]
        missing = [x for x in report["unknown_controls"] if x["rule"] == rule]
        status = "FAIL" if new else "UNKNOWN" if missing or not feasible else "PASS" if applicable else "NOT_APPLICABLE"
        report["rules"].append({"rule": rule, "status": status, "new_violations": len(new), "historical_violations": len(hist), "unknown_count": len(missing), "details": details or {}})

    shared_needs = _reviewed_shared_needs(data, issue, unknown)

    if dynamic_requested:
        # Verification of the contract text and verification of its local
        # application are separate facts.  Neither a mathematical result nor a
        # sourced arithmetic profile proves the latter.
        report["business_schedule_approved"] = False
        report["ar_jo_rest_assessments"] = []
        report["application_assessment"] = {
            "status": "UNKNOWN", "arithmetic_profile_only": True,
            "application_authorized": False,
            "process_evidence": compensation_profile.get("process_evidence"),
            "source_ref": compensation_profile.get("source_ref"),
        }
        unknown("planned_exception_process", "Source verification does not establish local special reasons, the required balancing of interests, MBL negotiation, or the additional necessity/no-reasonable-alternative and sector conditions for class C",
                process_evidence=compensation_profile.get("process_evidence"),
                arithmetic_profile_only=True, application_authorized=False)
        if not dynamic_verified:
            unknown("jour_compensation", "Dynamic compensatory-rest profile lacks VERIFIED source_status and a source reference; local application cannot be inferred from a profile name")

    for raw_unknown in data.get("unknown_controls", []):
        unknown("input_unknown", raw_unknown.get("why", raw_unknown.get("detail", "Unresolved input control")), source=raw_unknown)

    employees = {str(e["id"]): e for e in data.get("employees", [])}
    if len(employees) != len(data.get("employees", [])):
        issue("input_integrity", "Duplicate employee IDs")
    for employee_id, employee in employees.items():
        if employee.get("vacant") or str(employee.get("alias", "")).strip().lower() in {"vakant", "vakans", "vacant"}:
            issue("input_integrity", "Vacancy is not an employee", employee_id=employee_id)
        if employee.get("availability_status") not in (None, "VERIFIED") and any(c.get("employee_id") == employee_id for c in data.get("candidates", [])):
            unknown("availability", "Confirmed work windows are missing; historical or planned presence does not define sole permitted times", employee_id=employee_id,
                    observed_presence_is_not_availability=True)
    frozen = []
    for duty in data.get("frozen_duties", []):
        try:
            frozen.append(_normal_duty(duty, origin, frozen=True))
        except (ValueError, KeyError, TypeError) as exc:
            issue("input_integrity", str(exc), historical=True, duty_id=duty.get("id"))
    known_lo, known_hi, inferred_history = _known_limits(data, origin, lo, hi, frozen)
    if inferred_history:
        unknown("history_boundary", "Known P1 coverage boundary is absent; an earliest observed pass is not evidence of preceding rest")
    if known_hi <= hi:
        unknown("post_period_rest", "No verified post-P2 duty/absence history; rest after the last duty cannot be approved")

    candidate_list = data.get("candidates", [])
    candidates = {str(c["id"]): c for c in candidate_list}
    if len(candidates) != len(candidate_list):
        issue("input_integrity", "Duplicate candidate IDs")
    selected = []
    ids = result.get("selected_candidate_ids", []) if feasible else []
    actual_list = result.get("selected_duties", []) if feasible else []
    actual_map = {str(d.get("id")): d for d in actual_list}
    if len(actual_map) != len(actual_list):
        issue("selected_duties", "Duplicate actual selected-duty IDs")
    if actual_list and set(actual_map) != set(map(str, ids)):
        issue("selected_duties", "Actual selected duties do not match selected candidate IDs", actual_only=sorted(set(actual_map) - set(map(str, ids))), ids_only=sorted(set(map(str, ids)) - set(actual_map)))
    duplicates = [cid for cid, count in Counter(map(str, ids)).items() if count > 1]
    for cid in duplicates:
        issue("selected_duties", "Candidate selected more than once", candidate_id=cid)
    for cid in dict.fromkeys(map(str, ids)):
        if cid not in candidates:
            issue("selected_duties", "Selected candidate does not exist", candidate_id=cid)
            continue
        try:
            candidate = candidates[cid]
            exported = actual_map.get(cid)
            mode = candidate.get("mode", "CROP_SOURCE")
            if mode not in {"CROP_SOURCE", "SHIFT_COMPLETE", "WORK_AVAILABLE"}:
                raise ValueError(f"Actual candidate {cid} has unsupported domain mode {mode}")
            if (candidate.get("variable") or mode == "SHIFT_COMPLETE") and exported is None:
                raise ValueError(f"Variable candidate {cid} has no exported actual bounds")
            actual = {**candidate, **exported} if exported is not None else candidate
            duty = _normal_duty(actual, origin)
            if str(duty["employee_id"]) != str(candidate["employee_id"]):
                raise ValueError(f"Actual candidate {cid} changed employee")
            reference = _normal_duty(candidate, origin)
            if candidate.get("variable") or mode == "SHIFT_COMPLETE":
                for field in ("start", "end"):
                    bounds = candidate[f"{field}_bounds"]
                    lower, upper = (bounds["min"], bounds["max"]) if isinstance(bounds, dict) else bounds
                    lower, upper = _minute(lower, origin), _minute(upper, origin)
                    if not lower <= duty[field] <= upper:
                        raise ValueError(f"Actual candidate {cid} {field} is outside its verified domain")
                if candidate.get("start_values") is not None and duty["start"] not in {_minute(v, origin) for v in candidate["start_values"]}:
                    raise ValueError(f"Actual candidate {cid} start is outside its approved discrete time-profile domain")
                if mode == "SHIFT_COMPLETE":
                    source_start = _minute(candidate.get("reference_start", candidate["start"]), origin)
                    source_end = _minute(candidate.get("reference_end", candidate["end"]), origin)
                    length = candidate.get("fixed_duration_minutes", source_end - source_start)
                    if duty["end"] - duty["start"] != length:
                        raise ValueError(f"Actual shifted candidate {cid} changed whole-profile duration")
                    delta = duty["start"] - source_start
                    source_clock = datetime.fromtimestamp(source_start * 60, origin.tzinfo).strftime("%H:%M")
                    actual_clock = datetime.fromtimestamp(duty["start"] * 60, origin.tzinfo).strftime("%H:%M")
                    if source_clock != actual_clock:
                        proof = candidate.get("clock_profile_verification", candidate.get("verified_profile_data"))
                        if not isinstance(proof, dict) or proof.get("status") != "VERIFIED" or not proof.get("source_ref"):
                            issue("duty_profile", "Shift changed the source local start clock without verified role/time-profile evidence", candidate_id=cid, employee_id=duty["employee_id"], source_start_clock=source_clock, actual_start_clock=actual_clock)
                        elif actual_clock not in proof.get("allowed_start_clocks", []) or not proof.get("required_roles", proof.get("roles")):
                            issue("duty_profile", "Verified profile does not explicitly permit this start clock and role", candidate_id=cid, employee_id=duty["employee_id"], actual_start_clock=actual_clock)
                        else:
                            for role in proof.get("required_roles", proof.get("roles", [])):
                                permission = employees.get(str(duty["employee_id"]), {}).get("source_role_permissions", {}).get(role)
                                allowed = permission.get("allowed") if isinstance(permission, dict) else permission
                                if allowed is False:
                                    issue("role_permissions", "Changed clock profile uses an expressly denied role", employee_id=duty["employee_id"], candidate_id=cid, role=role)
                                elif allowed is not True:
                                    unknown("role_permissions", "Changed clock profile requires an unverified role", employee_id=duty["employee_id"], candidate_id=cid, role=role)
                elif mode not in {"CROP_SOURCE", "WORK_AVAILABLE"}:
                    raise ValueError(f"Actual candidate {cid} has unsupported domain mode {mode}")
                for kind in ("work", "jour"):
                    if mode == "SHIFT_COMPLETE":
                        source_segments = [_interval(v, origin) for v in candidate.get("reference_" + kind, candidate.get(kind, []))]
                        expected = _union([(a + delta, b + delta) for a, b in source_segments])
                    else:
                        expected = _union([(max(a, duty["start"]), min(b, duty["end"])) for a, b in reference[kind] if max(a, duty["start"]) < min(b, duty["end"])])
                    if _union(duty[kind]) != expected:
                        raise ValueError(f"Actual candidate {cid} changed {kind} classification rather than preserving its source-profile mode")
                changed = duty["start"] != reference["start"] or duty["end"] != reference["end"]
                duty["is_original"] = bool(candidate.get("is_original")) and not changed
                duty["is_new_or_shortened"] = bool(candidate.get("is_new_or_shortened")) or changed
            elif exported is not None and (duty["start"] != reference["start"] or duty["end"] != reference["end"] or _union(duty["work"]) != _union(reference["work"]) or _union(duty["jour"]) != _union(reference["jour"])):
                raise ValueError(f"Fixed candidate {cid} was changed in the output")
            if mode == "WORK_AVAILABLE":
                duty["is_original"] = False
                duty["is_new_or_shortened"] = True
                if reference["jour"] or duty["jour"] or _union(reference["work"]) != [(reference["start"], reference["end"])]:
                    raise ValueError(f"Actual candidate {cid} did not preserve an Ar-only confirmed work window")
        except (ValueError, KeyError, TypeError) as exc:
            issue("selected_duties", str(exc), candidate_id=cid)
            continue
        if str(duty.get("employee_id")) not in employees:
            issue("selected_duties", "Selected duty has no real known employee", candidate_id=cid, employee_id=duty.get("employee_id"))
            continue
        selected.append(duty)
    by_person = defaultdict(list)
    frozen_by_person = defaultdict(list)
    for duty in frozen + selected:
        employee_id = str(duty.get("employee_id"))
        by_person[employee_id].append(duty)
        if duty["frozen"]:
            frozen_by_person[employee_id].append(duty)
    person_ids = sorted(set(employees) | set(by_person))

    # Candidate choices are presence, not customer capacity; Ar and Jo remain
    # separate.  Only the immutable incoming Ar part may cover P2 activities.
    work_by_person = {}
    for employee_id in person_ids:
        duties = by_person[employee_id]
        work_by_person[employee_id] = _union([v for d in duties for v in d["work"]])
        if feasible:
            mutable = [d for d in duties if not d["frozen"]]
            employee_record = employees.get(employee_id, {})
            for duty in mutable:
                changed = duty.get("is_new_or_shortened") or not duty.get("is_original", False)
                if changed and employee_record.get("hard_condition_unknown"):
                    issue("individual_conditions", "Changed duty relies on an unresolved individual hard condition", employee_id=employee_id, candidate_id=duty["id"], source_condition=employee_record.get("hard_condition_raw"))
                condition = employee_record.get("verified_hard_condition")
                if condition is not None:
                    allowed_individual = [_interval(w, origin) for w in condition.get("allowed_windows", [])]
                    if not _inside(allowed_individual, duty["start"], duty["end"]):
                        issue("individual_conditions", "Whole duty falls outside the dated confirmed individual condition",
                              employee_id=employee_id, candidate_id=duty["id"], interval=[duty["start"], duty["end"]])
                for typed, duty_kind in (("confirmed_active_windows", "work"), ("confirmed_oncall_windows", "jour")):
                    if typed in employee_record:
                        typed_allowed = [_interval(w, origin) for w in employee_record[typed]]
                        if any(not _inside(typed_allowed, a, b) for a, b in duty[duty_kind]):
                            issue("availability", "Duty segment falls outside its separately confirmed typed availability",
                                  employee_id=employee_id, candidate_id=duty["id"], segment_type=duty_kind)
                permissions = employee_record.get("source_role_permissions", {})
                roles = ["sleeping_oncall"] if duty["jour"] else []
                if changed and duty["work"]:
                    roles.append("day")
                for role in roles:
                    permission = permissions.get(role)
                    if permission is None:
                        if duty.get("mode") == "WORK_AVAILABLE":
                            unknown("role_permissions", "New active work requires an explicitly permitted sourced role", employee_id=employee_id, candidate_id=duty["id"], role=role)
                        continue  # Generic original-duty fixtures may specify eligibility directly.
                    allowed = permission.get("allowed") if isinstance(permission, dict) else permission
                    if allowed is False:
                        issue("role_permissions", "Duty uses an expressly denied source role", employee_id=employee_id, candidate_id=duty["id"], role=role)
                    elif allowed is not True:
                        unknown("role_permissions", "Blank/unknown role permission is not JA", employee_id=employee_id, candidate_id=duty["id"], role=role)
                night_profile = rules.get("active_night_clock_window")
                if changed and duty["work"] and night_profile is not None:
                    if not isinstance(night_profile, dict) or night_profile.get("status") != "VERIFIED" or not night_profile.get("source_ref"):
                        unknown("duty_profile", "Night role/time-window provenance is unverified; no clock thresholds were inferred", employee_id=employee_id, candidate_id=duty["id"])
                    else:
                        try:
                            night_intervals = _clock_windows(origin, period.get("tz", period.get("timezone")), duty["start"], duty["end"], night_profile["start"], night_profile["end"])
                            night_work = any(max(a, x) < min(b, y) for a, b in duty["work"] for x, y in night_intervals)
                            if night_work:
                                permission = permissions.get("awake_night")
                                allowed = permission.get("allowed") if isinstance(permission, dict) else permission
                                if allowed is False:
                                    issue("role_permissions", "New active work overlaps the verified night profile despite explicit NEJ for awake night", employee_id=employee_id, candidate_id=duty["id"], role="awake_night", night_profile=night_profile)
                                elif allowed is not True:
                                    unknown("role_permissions", "New active night work has no verified awake-night authorization", employee_id=employee_id, candidate_id=duty["id"], role="awake_night")
                        except (KeyError, TypeError, ValueError) as exc:
                            issue("duty_profile", str(exc), employee_id=employee_id, candidate_id=duty["id"])
            for i, first in enumerate(mutable):
                for second in mutable[i + 1:]:
                    if max(first["start"], second["start"]) < min(first["end"], second["end"]):
                        issue("selected_duties", "Selected whole duties overlap", employee_id=employee_id, candidate_ids=[first["id"], second["id"]])
                for historical in frozen_by_person[employee_id]:
                    if max(first["start"], historical["start"]) < min(first["end"], historical["end"]):
                        issue("selected_duties", "Mutable candidate duplicates frozen presence", employee_id=employee_id, candidate_ids=[first["id"], historical.get("id")])
            available = employee_record.get("allowed_presence_windows")
            availability_status = employee_record.get("availability_status")
            unconfirmed = availability_status is not None and availability_status != "VERIFIED"
            if availability_status is None and available is not None:
                unconfirmed = any(v.get("status") not in (None, "VERIFIED") for v in available)
            if (available is None or unconfirmed) and mutable:
                unknown("availability", "Confirmed availability is missing; observed source-plan presence is only a reference diagnostic", employee_id=employee_id,
                        observed_presence_is_not_availability=True)
                if result.get("diagnostic_only"):
                    observed = employee_record.get("observed_presence_windows")
                    if observed is None:
                        observed = [v for v in available or [] if v.get("status") == "SOURCE_PLAN_ONLY"]
                    try:
                        reference_windows = [_interval(v, origin) for v in observed]
                        for duty in mutable:
                            if not _inside(reference_windows, duty["start"], duty["end"]):
                                issue("diagnostic_presence_scope", "Reference diagnostic moved outside its observed source-plan domain", employee_id=employee_id, candidate_id=duty["id"])
                    except (ValueError, KeyError, TypeError) as exc:
                        issue("diagnostic_presence_scope", str(exc), employee_id=employee_id)
            elif available is not None:
                try:
                    windows = [_interval(v, origin) for v in available]
                    for duty in mutable:
                        if not _inside(windows, duty["start"], duty["end"]):
                            issue("availability", "Selected presence extends beyond verified available windows", employee_id=employee_id, candidate_id=duty["id"])
                except (ValueError, KeyError, TypeError) as exc:
                    issue("availability", str(exc), employee_id=employee_id)

    needs = {str(n["id"]): n for n in data.get("needs", [])}
    if len(needs) != len(data.get("needs", [])):
        issue("input_integrity", "Duplicate need IDs")
    assignments = defaultdict(list)
    if feasible:
        unassigned = result.get("unassigned", [])
        unassigned_ids = [str(x["need_id"]) if isinstance(x, dict) else str(x) for x in unassigned]
        for nid, count in Counter(unassigned_ids).items():
            if count > 1:
                issue("need_partition", "Need is repeated in unassigned list", need_id=nid)
        for nid in unassigned_ids:
            if nid not in needs:
                issue("need_partition", "Unknown unassigned need ID", need_id=nid)
        for assignment in result.get("assignments", []):
            nid = str(assignment.get("need_id"))
            if nid not in needs:
                issue("need_partition", "Assignment references unknown need", need_id=nid)
                continue
            try:
                a, b = _minute(assignment["start"], origin), _minute(assignment["end"], origin)
                if b <= a:
                    raise ValueError("Assigned interval is not positive")
            except (ValueError, KeyError, TypeError) as exc:
                issue("need_timing", str(exc), need_id=nid)
                continue
            assignments[nid].append({**assignment, "start": a, "end": b, "employee_id": str(assignment.get("employee_id"))})
        assigned_set, omitted_set = set(assignments), set(unassigned_ids)
        for nid in sorted(set(needs) - assigned_set - omitted_set):
            issue("need_partition", "Input need silently disappeared from output", need_id=nid)
        for nid in sorted(assigned_set & omitted_set):
            issue("need_partition", "Need appears both assigned and unassigned", need_id=nid)
        for nid, records in assignments.items():
            need = needs[nid]
            count = need.get("count")
            if count is None:
                unknown("person_count", "Required number of people is unknown", need_id=nid)
            elif len(records) != count or len({r["employee_id"] for r in records}) != count:
                issue("person_count", "Need lacks exact distinct concurrent performer count", need_id=nid, expected=count, actual=len(records), distinct=len({r["employee_id"] for r in records}))
            if "count_confirmed" in need and need["count_confirmed"] is None:
                unknown("person_count", "Source two-person field gives only a candidate count; exact active performer count is unconfirmed", need_id=nid, source_count_status=need.get("count_status"))
            if len({(r["start"], r["end"]) for r in records}) > 1:
                issue("person_count", "Double-staffed need has different performer intervals", need_id=nid)
            if need.get("blockers"):
                issue("need_eligibility", "Assigned need still has an unresolved input blocker", need_id=nid, blockers=need["blockers"])
            earliest = _minute(need["earliest"], origin)
            latest = _minute(need["latest_end"], origin)
            duration = need.get("duration")
            if duration is None:
                unknown("need_timing", "Duration is unknown", need_id=nid)
            semantics = need.get("window_semantics")
            if semantics not in ("EXECUTION_WINDOW", "START_WINDOW"):
                issue("need_timing", "Window meaning lacks a reviewed decision", need_id=nid)
            if duration is not None and semantics == "EXECUTION_WINDOW" and earliest + duration > latest:
                issue("need_timing", "Input duration cannot fit its window", need_id=nid)
            locked = need.get("locked_start")
            # The user's latest decision permits choosing a start inside the
            # whole execution window unless a particular lock is evidenced.
            for record in records:
                employee_id = record["employee_id"]
                a, b = record["start"], record["end"]
                if duration is not None and b - a != duration:
                    issue("need_timing", "Assigned duration differs from the original/scenario duration", need_id=nid, employee_id=employee_id)
                if a < earliest or (b > latest if semantics == "EXECUTION_WINDOW" else a > latest):
                    issue("need_timing", "Activity is outside its reviewed window semantics", need_id=nid, employee_id=employee_id)
                if b <= lo or a >= hi:
                    issue("need_timing", "Assigned activity does not overlap P2; boundary-crossing activities must remain whole and overlap the selected period", need_id=nid, employee_id=employee_id)
                if locked is not None and a != _minute(locked, origin):
                    issue("need_movement", "Assignment moved a verified locked start", need_id=nid, employee_id=employee_id)
                if locked is None and need.get("movable") is False:
                    unknown("need_movement", "A fixed need lacks its independently evidenced exact start", need_id=nid)
                eligible = need.get("eligible_employee_ids")
                if eligible is None:
                    unknown("need_eligibility", "Performer eligibility is unknown", need_id=nid, employee_id=employee_id)
                elif employee_id not in set(map(str, eligible)):
                    issue("need_eligibility", "Performer is outside the verified eligible set", need_id=nid, employee_id=employee_id)
                if employee_id not in employees:
                    issue("need_eligibility", "Performer is not a known actual employee", need_id=nid, employee_id=employee_id)
                if not _inside(work_by_person.get(employee_id, []), a, b):
                    issue("active_presence", "Activity is not entirely inside Ar; Jo/vacancy are not active capacity", need_id=nid, employee_id=employee_id)
                skills = employees.get(employee_id, {}).get("skills_known")
                profession = need.get("required_profession_source")
                if isinstance(skills, list):
                    if profession not in (None, "Ingen yrkesgrupp") and profession not in skills:
                        issue("skills", "Performer lacks the explicit required source profession", need_id=nid, employee_id=employee_id, required_profession=profession)
                    required = need.get("required_skills_confirmed")
                    if isinstance(required, list) and not set(required) <= set(skills):
                        issue("skills", "Performer lacks a confirmed required skill", need_id=nid, employee_id=employee_id, required_skills=required)
                elif skills is not True:
                    unknown("skills", "Performer skill/authorization record is incomplete", need_id=nid, employee_id=employee_id)
        active_records = defaultdict(list)
        for nid, records in assignments.items():
            for record in records:
                active_records[record["employee_id"]].append((record["start"], record["end"], nid))
        allowed_pairs, examples, peaks = 0, [], {}
        for employee_id, records in active_records.items():
            ongoing = []
            for a, b, nid in sorted(records):
                ongoing = [(x, y, n) for x, y, n in ongoing if y > a]
                for x, y, other in ongoing:
                    if nid in shared_needs and other in shared_needs:
                        allowed_pairs += 1
                        if len(examples) < 20:
                            examples.append(dict(employee_id=employee_id, need_ids=[other, nid], overlap=[a, min(b, y)]))
                    else:
                        issue("activity_capacity", "Same person overlaps an exclusive or unverified activity", employee_id=employee_id, need_ids=[other, nid], overlap=[a, min(b, y)])
                ongoing.append((a, b, nid))
            events = sorted(event for a, b, nid in records if min(b, hi) > max(a, lo)
                for event in [(max(a, lo), 1), (min(b, hi), -1)])
            active, peak = 0, 0
            for moment, delta in events:
                active += delta
                peak = max(peak, active)
            peaks[employee_id] = peak
        if 'concurrency_policy' in data:
            p = data['concurrency_policy'] if isinstance(data['concurrency_policy'], dict) else {}
            report['concurrency'] = dict(decision_id=p.get('decision_id'),
                permitted_overlapping_pairs=allowed_pairs, examples=examples,
                maximum_simultaneous_by_person=peaks,
                assigned_person_minutes_once=sum(_overlap([(a,b) for a,b,nid in records],lo,hi) for records in active_records.values()),
                summed_need_duration_person_minutes=sum(max(0,min(b,hi)-max(a,lo)) for records in active_records.values() for a,b,nid in records),
                practical_execution_verified=False)
        report["coverage"] = {
            "status": "COMPLETE" if len(assignments) == len(needs) and not omitted_set else "PARTIAL",
            "input_need_count": len(needs), "assigned_needs": len(assignments),
            "unassigned_needs": len(omitted_set), "performer_assignments": sum(map(len, assignments.values())),
            "assigned_need_minutes": sum(needs[nid].get("duration", 0) or 0 for nid in assignments),
            "assigned_person_minutes": sum(r["end"] - r["start"] for records in assignments.values() for r in records),
            "unassigned_need_ids": sorted(omitted_set),
        }
    else:
        unknown("proposed_schedule", "Solver exported no feasible schedule; selected duties, coverage and P2 compliance are not assessable", solver_status=solver_status)

    for employee_id in person_ids:
        employee = employees.get(employee_id, {})
        duties = by_person[employee_id]
        hist_duties = frozen_by_person[employee_id]
        presence = _union([(d["start"], d["end"]) for d in duties])
        hist_presence = _union([(d["start"], d["end"]) for d in hist_duties])
        jour = _union([v for d in duties for v in d["jour"]])
        hist_jour = _union([v for d in hist_duties for v in d["jour"]])
        new_jour = _union([v for d in duties if not d["frozen"] for v in d["jour"]])
        ar = work_by_person[employee_id]
        metrics = {"alias": employee.get("alias"), "planned_Ar_target_minutes": employee.get("planned_Ar_target_minutes"),
                   "contract_target_minutes": employee.get("contract_target_minutes"),
                   "P2_Ar_minutes": _overlap(ar, lo, hi) if feasible else None,
                   "P2_jour_minutes": _overlap(jour, lo, hi) if feasible else None,
                   "P2_presence_minutes": _overlap(presence, lo, hi) if feasible else None}
        report["metrics"][employee_id] = metrics
        if feasible:
            target = employee.get("planned_Ar_target_minutes")
            flexible_temporary = (employee.get("staffing_type") == "TEMPORARY_VERIFIED"
                                  and employee.get("preserve_Ar_target") is not True)
            if flexible_temporary:
                metrics["Ar_target_mode"] = "DECISION_VARIABLE_VERIFIED_TEMPORARY_BOOKING_FROZEN_HISTORY_PRESERVED"
            elif target is None:
                unknown("planned_Ar", "No verified preserved planned-Ar target; observed hours were not promoted to contract capacity", employee_id=employee_id)
            elif metrics["P2_Ar_minutes"] != target:
                issue("planned_Ar", "P2 active net minutes differ from the preserved planned-time target", employee_id=employee_id, target_minutes=target, actual_minutes=metrics["P2_Ar_minutes"])
            contract = employee.get("contract_target_minutes")
            if contract is None:
                unknown("contract_SSG", "Contract capacity/SSG is not verified; planned Ar is a separate measure", employee_id=employee_id)
            elif metrics["P2_Ar_minutes"] > contract:
                issue("contract_SSG", "P2 active net exceeds verified contract capacity", employee_id=employee_id, contract_minutes=contract, actual_minutes=metrics["P2_Ar_minutes"])
            for a, b in presence:
                components = [d for d in duties if d["start"] < b and d["end"] > a]
                in_proposal = any(not d["frozen"] for d in components) or (a < hi and b > lo)
                if in_proposal and b - a < minimum_pass:
                    issue("minimum_whole_pass", "Whole contiguous Ar/Jo duty in the proposal is under four hours, including retained original duties", employee_id=employee_id, interval=[a, b], duration_minutes=b - a)
            calendar = _day_intervals(origin, period.get("tz", period.get("timezone")), min(known_lo, lo - ROLLING), hi)
            worked = {date for date, a, b in calendar if _overlap(presence, a, b) > 0}
            frozen_worked = {date for date, a, b in calendar if _overlap(hist_presence, a, b) > 0}
            p2_days = [(date, a, b) for date, a, b in calendar if a >= lo and b <= hi]
            p2_free = [date for date, a, b in p2_days if date not in worked]
            metrics["P2_free_calendar_days"] = len(p2_free)
            metrics["P2_free_dates"] = p2_free
            mode = str(rules.get("free_days_mode", "")).lower()
            rolling_rows = []
            if employee.get("history_known") is False or "P1_HISTORY_UNKNOWN" in employee.get("blockers", []):
                unknown("free_calendar_days", "Person-specific P1 history is missing; rolling calendar days are diagnostic and cannot certify freedom", employee_id=employee_id)
            for index in range(27, len(calendar)):
                segment = calendar[index - 27:index + 1]
                start, end = segment[0][1], segment[-1][2]
                if start < known_lo or end <= lo or end > hi:
                    continue
                free = sum(date not in worked for date, _, _ in segment)
                frozen_occupied = sum(date in frozen_worked for date, _, _ in segment)
                new_occupied = sum(date in worked and date not in frozen_worked for date, _, _ in segment)
                rolling_rows.append({"start": segment[0][0], "end_exclusive": (datetime.fromisoformat(segment[-1][0]) + timedelta(days=1)).date().isoformat(), "free_calendar_days": free,
                                     "frozen_occupied_days": frozen_occupied, "new_occupied_days": new_occupied})
            metrics["rolling_28d_free_days"] = rolling_rows
            if mode in {"rolling", "rolling28", "rolling28d", "rolling_28_days", "rolling_28_calendar_days"}:
                for row in rolling_rows:
                    if row["free_calendar_days"] < minimum_days:
                        inherited = 28 - row["frozen_occupied_days"] < minimum_days
                        issue("free_calendar_days", "Frozen history alone causes fewer than nine free calendar days" if inherited else "Fewer than nine free calendar days in a rolling 28-calendar-day period",
                              historical=inherited, employee_id=employee_id, **row)
                        if inherited and row["new_occupied_days"]:
                            issue("free_calendar_days", "New P2 calendar-day occupation worsens an inherited frozen free-day breach",
                                  employee_id=employee_id, **row)
            elif mode in {"fixed", "fixed28", "fixed28d", "fixed_period"}:
                if len(p2_free) < minimum_days:
                    issue("free_calendar_days", "Fewer than nine free calendar days in the fixed P2 period", employee_id=employee_id, free_calendar_days=len(p2_free))
            else:
                unknown("free_calendar_days", "Business-specific fixed versus rolling 28-day applicability is not confirmed; both measurements are reported", employee_id=employee_id)
                if len(p2_free) < minimum_days:
                    issue("free_calendar_days", "Fixed P2 already has fewer than nine free calendar days; either interpretation fails this full 28-day interval", employee_id=employee_id, free_calendar_days=len(p2_free))
        # Internal gaps between whole Ar/Jo duties.  Absence is not duty and may
        # provide rest; the immutable incoming duty remains one chain.
        for (a, b), (c, d) in zip(presence, presence[1:]):
            gap = c - b
            if gap < daily:
                historical = ((a, b) in hist_presence and (c, d) in hist_presence) or not feasible
                issue("daily_rest", "Gap between whole duties is under eleven hours; no documented exception/compensation was supplied", historical=historical, employee_id=employee_id, gap_minutes=gap, interval=[b, c])
        if feasible and presence:
            if presence[0][0] < known_lo + daily or employee.get("history_known") is False or "P1_HISTORY_UNKNOWN" in employee.get("blockers", []):
                unknown("daily_rest_boundary", "Rest before the first observed duty lacks complete known boundary history", employee_id=employee_id, first_start=presence[0][0])
            if known_hi - presence[-1][1] < daily:
                unknown("daily_rest_boundary", "Rest after last duty extends outside the known history horizon", employee_id=employee_id, last_end=presence[-1][1])
        if feasible:
            requested_daily_anchor = result.get("daily_rest_anchors", {}).get(employee_id)
            assessment = _standard_daily_assessment(duties, hist_duties, employee, period,
                lo, hi, known_lo if employee.get("history_known", False) else lo,
                known_hi, requested_daily_anchor, dynamic_verified, rules.get("daily_rest_anchor_decision"))
            report.setdefault("daily_rest_24h_assessments", {})[employee_id] = assessment
            metrics["daily_rest_fixed_phase_minutes"] = assessment.get("selected_phase_minutes")
            metrics["daily_rest_24h_arithmetic_status"] = assessment["arithmetic_status"]
            if assessment.get("anchor_application_status") != "CONFIRMED_SCENARIO_ANCHOR_SELECTION":
                unknown("daily_rest_24h_placement", "Full standard eleven-hour rest is calculated in fixed 24-hour periods, but no supplied decision in this input authorizes the test to select the daily phase",
                    employee_id=employee_id, arithmetic_status=assessment["arithmetic_status"],
                    anchor_status=assessment.get("anchor_status"),
                    local_anchor_application_status="UNKNOWN", universal_13h_cap_applied=False)
            for row in assessment["windows"]:
                if row["new_violation"]:
                    issue("daily_rest_24h_placement", "The applicable fixed 24-hour scenario period has no eleven-hour continuous rest; no pure-Ar B/C exception is inferred",
                        employee_id=employee_id, **row)
                elif row["historical_shortfall"]:
                    issue("daily_rest_24h_placement", "Fixed-period rest shortfall is wholly caused by frozen history; P2 must not reduce the frozen longest rest",
                        historical=True, employee_id=employee_id, **row)
                elif not row.get("fully_known", True):
                    unknown("daily_rest_24h_placement", "This outer period passes only a necessary optimistic-rest bound using all known selected/frozen presence, including outgoing portions; unseen time is not confirmed free",
                        employee_id=employee_id, interval=[row["start"], row["end"]],
                        maximum_possible_rest_minutes=row["maximum_possible_rest_minutes"],
                        outer_bound_kind=row["outer_bound_kind"])
                if row["status"] == "B_C_EXCEPTION_ARITHMETIC_ONLY":
                    unknown("daily_rest_24h_placement", "The fixed 24-hour period uses a separate combined Ar/Jo numerical B/C exception; the local exception process remains unverified",
                        employee_id=employee_id, interval=[row["start"], row["end"]],
                        exception_chains=row["exception_chains"],
                        mixed_exception_window=row["mixed_exception_window"],
                        application_status="UNKNOWN")
        if dynamic_verified:
            # Reconstruct connected duty chains from actual typed intervals,
            # independently of candidate grouping and of any model helper.
            typed_presence = _union([segment for duty in duties for kind in ("work", "jour") for segment in duty[kind]])
            frozen_typed_presence = _union([segment for duty in hist_duties for kind in ("work", "jour") for segment in duty[kind]])
            for jour_start, jour_end in jour:
                adjacent_ar = any(end == jour_start or start == jour_end for start, end in ar if end > start)
                historical = _inside(hist_jour, jour_start, jour_end) or not feasible
                exception = compensation_profile.get("standalone_jour_exception")
                exception_applies = False
                if (isinstance(exception, dict) and exception.get("status") == "CONFIRMED"
                        and exception.get("source_ref")
                        and isinstance(exception.get("employee_ids"), list)
                        and employee_id in set(map(str, exception.get("employee_ids", [])))):
                    try:
                        exception_applies = (jour_start, jour_end) in [_interval(item, origin) for item in exception.get("intervals", [])]
                    except (KeyError, TypeError, ValueError):
                        # A malformed or broader exception is never permission
                        # to manufacture a new standalone jour booking.
                        exception_applies = False
                if not adjacent_ar and not exception_applies:
                    issue("jour_adjacency", "Section 10 requires positive actual Ar immediately before OR after jour; standalone jour has no person-and-interval-specific confirmed special-reason exception",
                          historical=historical, employee_id=employee_id, interval=[jour_start, jour_end],
                          minimum_adjacent_Ar_minutes=None, model_time_resolution_minutes=1)
            for index, (a, b) in enumerate(typed_presence):
                active_minutes = _overlap(ar, a, b)
                jour_minutes = _overlap(jour, a, b)
                used_fixed_exception = any([a, b] in row.get("exception_chains", [])
                    and row.get("status") == "B_C_EXCEPTION_ARITHMETIC_ONLY"
                    for row in report.get("daily_rest_24h_assessments", {}).get(employee_id, {}).get("windows", []))
                if not active_minutes or not jour_minutes or (b - a <= DAY - 660 and not used_fixed_exception):
                    continue
                span = b - a
                historical = _inside(frozen_typed_presence, a, b) or not feasible
                classification = "B_UP_TO_20H" if span <= 20 * 60 else "C_OVER_20H_UP_TO_24H" if span <= DAY else "OUTSIDE_B_C_RANGE"
                following = typed_presence[index + 1][0] if index + 1 < len(typed_presence) else None
                following_historical = (following is not None
                                        and _inside(frozen_typed_presence, *typed_presence[index + 1]))
                longest_night_jour = 0
                for night_start, night_end in _clock_windows(origin, period.get("tz", period.get("timezone")), a, b, "22:00", "08:00"):
                    portions = _union([(max(start, night_start, a), min(end, night_end, b))
                                       for start, end in jour
                                       if max(start, night_start, a) < min(end, night_end, b)])
                    longest_night_jour = max(longest_night_jour, max((end - start for start, end in portions), default=0))
                assessment = {
                    "employee_id": employee_id, "interval": [a, b], "historical_chain": historical,
                    "whole_chain_minutes": span, "Ar_minutes": active_minutes, "jour_minutes": jour_minutes,
                    "classification": classification, "classification_status": "DERIVED_MODEL_CLASSIFICATION",
                    "exception_trigger": "FIXED_24H_STANDARD_SHORTFALL" if used_fixed_exception else "PREVIOUS_DERIVED_OVER_13H_CLASSIFICATION",
                    "derived_threshold_minutes": DAY - 660, "threshold_is_literal_contract_rule": False,
                    "required_immediate_rest_minutes": span,
                    "next_known_duty_start": following,
                    "observed_rest_minutes": following - b if following is not None else None,
                    "longest_continuous_night_jour_minutes": longest_night_jour,
                    "arithmetic_status": "PASS", "scenario_scope_status": "PASS", "application_status": "UNKNOWN",
                    "source_ref": compensation_profile.get("source_ref"),
                }
                if span > 20 * 60:
                    c_application = compensation_profile.get("c_application")
                    c_verified = (isinstance(c_application, dict)
                                  and c_application.get("status") == "CONFIRMED"
                                  and bool(c_application.get("source_ref"))
                                  and c_application.get("not_healthcare_sector") is True
                                  and c_application.get("necessity") is True
                                  and c_application.get("no_reasonable_alternatives") is True
                                  and isinstance(c_application.get("employee_ids"), list)
                                  and employee_id in set(map(str, c_application.get("employee_ids", []))))
                    c_disabled = compensation_profile.get("C_application_mode") == "DISABLED_UNTIL_APPLICATION_VERIFIED"
                    assessment["C_application_authorized"] = bool(c_verified and not c_disabled)
                    if not historical and (c_disabled or not c_verified):
                        assessment["scenario_scope_status"] = "FAIL"
                        issue("C_SCOPE_DISABLED", "Mutable Ar/Jo chain over twenty hours is outside the current B-only scenario; class C requires explicitly enabled, sourced person-specific confirmation of sector, necessity and no reasonable alternatives",
                              employee_id=employee_id, interval=[a, b], duration_minutes=span,
                              C_application_mode=compensation_profile.get("C_application_mode"),
                              application_verified=c_verified)
                    elif historical and (c_disabled or not c_verified):
                        unknown("planned_exception_process", "Frozen historical class-C chain is retained and checked arithmetically; local class-C application is unverified and is not a new scenario-scope breach",
                                employee_id=employee_id, interval=[a, b], historical=True)
                if span > DAY:
                    assessment["arithmetic_status"] = "FAIL"
                    issue("long_duty", "Actual connected Ar/Jo chain exceeds the sourced B/C range of at most 24 hours; the derived 13-hour classification is not a global maximum duty rule",
                          historical=historical, employee_id=employee_id, interval=[a, b], duration_minutes=span)
                if longest_night_jour < 300:
                    assessment["arithmetic_status"] = "FAIL"
                    issue("long_duty", "Planned exceptional Ar/Jo chain lacks five continuous jour hours within one 22:00–08:00 night window",
                          historical=historical, employee_id=employee_id, interval=[a, b],
                          longest_night_jour_minutes=longest_night_jour, classification=classification)
                if following is not None and following - b < span:
                    assessment["arithmetic_status"] = "FAIL"
                    issue("jour_compensation", "Immediate rest after the actual connected Ar/Jo chain is shorter than that whole chain",
                          historical=(historical and following_historical) or not feasible,
                          employee_id=employee_id, duty_interval=[a, b], interval=[b, following],
                          rest_minutes=following - b, required_minutes=span, classification=classification)
                elif known_hi - b < span:
                    if assessment["arithmetic_status"] != "FAIL":
                        assessment["arithmetic_status"] = "UNKNOWN"
                    unknown("jour_compensation", "Duty-length immediate compensation extends beyond the verified history horizon; a late or absent next known pass does not establish absence of unseen work",
                            employee_id=employee_id, duty_interval=[a, b], interval=[b, b + span],
                            required_minutes=span, known_end=known_hi, historical=historical)
                report["ar_jo_rest_assessments"].append(assessment)
        for a, b in presence:
            if not dynamic_requested and b - a >= 20 * 60:
                historical = b <= lo or not feasible
                overnight = []
                for date, night_a, _ in _day_intervals(origin, period.get("tz", period.get("timezone")), a - DAY, b):
                    begin = night_a + 22 * 60
                    finish = night_a + 32 * 60
                    overnight.extend((max(x, begin), min(y, finish)) for x, y in jour if max(x, begin) < min(y, finish))
                longest = max((y - x for x, y in _union(overnight)), default=0)
                if b - a > 24 * 60:
                    issue("long_duty", "Whole Ar/Jo duty exceeds the documented 20–24-hour exceptional range", historical=historical, employee_id=employee_id, interval=[a, b], duration_minutes=b - a)
                if longest < 5 * 60:
                    issue("long_duty", "20–24-hour Ar/Jo duty lacks five continuous jour hours within 22:00–08:00", historical=historical, employee_id=employee_id, interval=[a, b], longest_night_jour_minutes=longest)
                compensation = rules.get("jour_compensation")
                if (isinstance(compensation, dict) and compensation.get("status") == "CONFIRMED"
                    and compensation.get("mode") == "IMMEDIATE_REST_MINUTES"
                    and isinstance(compensation.get("rest_minutes"), int)):
                    required = compensation["rest_minutes"]
                    following = min((c for c, d in presence if c >= b), default=None)
                    if following is not None and following - b < required:
                        issue("jour_compensation", "Confirmed immediate compensatory-rest duration is not met", employee_id=employee_id,
                              interval=[b, following], rest_minutes=following - b, required_minutes=required, historical=historical)
                    elif following is None and known_hi - b < required:
                        unknown("jour_compensation", "Confirmed compensation extends beyond known history; unseen future work is not inferred absent",
                                employee_id=employee_id, interval=[b, b + required], required_minutes=required, historical=historical)
                else:
                    unknown("jour_compensation", "Exact applicable length and placement of compensatory rest after 20–24-hour Ar/Jo duty is not supplied", employee_id=employee_id, interval=[a, b], historical=historical)
        anchor_value = rules.get("week_anchor")
        if rules.get("week_anchor_mode") == "PER_EMPLOYEE_FIXED_SELECTED":
            chosen = result.get("week_anchors", {}).get(employee_id) if feasible else None
            if isinstance(chosen, dict):
                try:
                    weekday = int(chosen["weekday"])
                    hour, minute = map(int, str(chosen["clock"]).split(":"))
                    if weekday not in range(7) or hour not in range(24) or minute not in range(60):
                        raise ValueError("Selected fixed week anchor is invalid")
                    date = origin.date() - timedelta(days=(origin.weekday() - weekday) % 7)
                    anchor_value = datetime.combine(date, datetime.min.time(), tzinfo=origin.tzinfo) + timedelta(hours=hour, minutes=minute)
                except (ValueError, KeyError, TypeError) as exc:
                    issue("weekly_rest", str(exc), employee_id=employee_id)
            else:
                anchor_value = None
        if anchor_value is None:
            if rules.get("week_anchor_mode") == "PER_EMPLOYEE_FIXED_SELECTED":
                detail = "No feasible schedule supplies this person's selected fixed weekly anchor; the per-employee fixed-anchor rule is decided" if not feasible else "The exported schedule omits this person's selected fixed weekly anchor; the per-employee fixed-anchor rule is decided"
            else:
                detail = "The required fixed seven-day anchor is not supplied; it cannot be moved between weeks to manufacture 36-hour rest"
            unknown("weekly_rest", detail, employee_id=employee_id)
        else:
            anchor = _minute(anchor_value, origin)
            first_k = ceil((known_lo - anchor) / WEEK)
            last_k = floor((min(known_hi, hi) - anchor - WEEK) / WEEK)
            week_rows = []
            for k in range(first_k, last_k + 1):
                a, b = anchor + k * WEEK, anchor + (k + 1) * WEEK
                longest = _longest_free(presence, a, b)
                if b > lo and not feasible:
                    continue
                row = {"start": _stamp(origin, a), "end_exclusive": _stamp(origin, b), "longest_rest_minutes": longest, "Ar_minutes": _overlap(ar, a, b), "jour_minutes": _overlap(jour, a, b), "presence_minutes": _overlap(presence, a, b)}
                week_rows.append(row)
                if longest < weekly:
                    issue("weekly_rest", "No 36-hour continuous rest inside the fixed seven-day interval", historical=b <= lo, employee_id=employee_id, **row)
            metrics["fixed_week_metrics"] = week_rows
        # Exact critical points of the piecewise-linear rolling integral.  Its
        # extrema can only occur at interval endpoints or shifted endpoints.
        points = {known_lo, lo - jour_length, lo, hi - jour_length}
        for a, b in jour + hist_jour:
            points.update((a, b, a - jour_length, b - jour_length))
        starts = sorted(p for p in points if p >= known_lo and p + jour_length <= min(known_hi, hi))
        # The inherited-breach rule is piecewise max(0, cap - frozen). Its
        # additional corner occurs where frozen jour crosses the cap, even
        # when no source interval has an endpoint there. Check both adjacent
        # integral minutes around this independently recalculated crossing.
        crossings = set()
        for left, right in zip(starts, starts[1:]):
            first = _overlap(hist_jour, left, left + jour_length)
            second = _overlap(hist_jour, right, right + jour_length)
            if min(first, second) < jour_cap < max(first, second):
                crossing = Fraction(left) + Fraction(jour_cap - first, second - first) * (right - left)
                crossings.update((floor(crossing), ceil(crossing)))
        starts = sorted(set(starts) | crossings)
        critical_rows = []
        for start in starts:
            end = start + jour_length
            frozen_minutes = _overlap(hist_jour, start, end)
            mutable_minutes = _overlap(new_jour, start, end) if feasible else 0
            total = _overlap(jour, start, end)
            if frozen_minutes <= jour_cap and total <= jour_cap:
                continue
            row = {"employee_id": employee_id, "alias": employee.get("alias"), "window_start": _stamp(origin, start), "window_end_exclusive": _stamp(origin, end), "start_minute": start, "end_minute": end, "frozen_jour_minutes": frozen_minutes, "mutable_P2_jour_minutes": mutable_minutes, "total_jour_minutes": total, "cap_minutes": jour_cap, "overlap_with_P2_minutes": max(0, min(end, hi) - max(start, lo))}
            critical_rows.append(row)
            if frozen_minutes > jour_cap:
                report["historical_jour_windows"].append(row)
                issue("jour_rolling_28d", "Frozen historical jour already exceeds 48 hours; P1 was not changed", historical=True, **row)
                if feasible and mutable_minutes > 0:
                    issue("jour_rolling_28d", "Mutable P2 jour adds to an already over-cap immutable rolling window", **row)
                    report["new_jour_windows"].append(row)
            elif feasible and total > jour_cap:
                issue("jour_rolling_28d", "New selected P2 jour makes a rolling 28-day window exceed 48 hours", **row)
                report["new_jour_windows"].append(row)
        metrics["jour_over_cap_critical_windows"] = critical_rows
    if feasible:
        rule_names = ["input_integrity", "input_unknown", "selected_duties", "duty_profile", "individual_conditions", "role_permissions", "need_partition", "need_timing", "need_movement", "person_count", "need_eligibility", "skills", "active_presence", "activity_capacity", "availability", "diagnostic_presence_scope", "planned_Ar", "contract_SSG", "minimum_whole_pass", "free_calendar_days", "daily_rest", "daily_rest_boundary", "weekly_rest", "long_duty", "jour_compensation", "jour_rolling_28d", "history_boundary", "post_period_rest"]
    else:
        rule_names = ["input_integrity", "input_unknown", "proposed_schedule", "availability", "daily_rest", "weekly_rest", "long_duty", "jour_compensation", "jour_rolling_28d", "history_boundary", "post_period_rest"]
    if dynamic_requested:
        rule_names.extend(["jour_adjacency", "planned_exception_process", "daily_rest_24h_placement", "C_SCOPE_DISABLED"])
    if 'concurrency_policy' in data or any('concurrency' in n for n in data.get('needs', [])):
        rule_names.extend(['concurrency_decision', 'concurrency_classification', 'practical_concurrency'])
    for name in rule_names:
        rule_status(name)
    report["summary"] = {"new_violations": len(report["violations"]["new"]), "historical_violations": len(report["violations"]["historical"]), "unknown_controls": len(report["unknown_controls"])}
    if feasible:
        if report["violations"]["new"]:
            report["status"] = "FAIL"
            report["schedule_status"] = "INVALID_PROPOSED_SCHEDULE"
        elif report["unknown_controls"]:
            report["status"] = "UNKNOWN"
            report["schedule_status"] = "SCENARIO_WITH_UNKNOWN_CONTROLS"
        elif report["coverage"]["status"] != "COMPLETE":
            report["status"] = "PARTIAL"
            report["schedule_status"] = "VALID_PARTIAL_COVERAGE"
        elif report["violations"]["historical"]:
            report["status"] = "HISTORICAL_FAILURE"
            report["schedule_status"] = "NO_NEW_FAILURES_WITH_HISTORICAL_BREACHES"
        else:
            report["status"] = "PASS"
            report["schedule_status"] = "VALIDATED"
    return report
