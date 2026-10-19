"""Exact standard 11h-in-fixed-24h arithmetic for an isolated scenario.

The supplied contract establishes eleven consecutive rest hours per 24 hours.
It does not establish the business's daily anchor. A single, constant minute phase
per employee is therefore an explicitly labelled model choice, not a confirmed
local rule. This module neither introduces a universal 13h duty cap nor checks
every rolling minute as though that interpretation had been agreed.

B/C combined-duty deviations are a separate numeric profile. A period may use
that profile only when it intersects the actual selected combined duty. All
whole duties still have >=11h gaps (and the separate dynamic compensation).
Thus if another whole duty also intersects the period, their entire >=11h gap
is inside that period; a pure-Ar duty cannot be excused merely by proximity.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DAY = 1440
STANDARD = 660
MODE = "FIXED_PHASE_STANDARD_WITH_SEPARATE_AR_JO_EXCEPTIONS"
ANCHOR_STATUS = "MODEL_SELECTED_FIXED_PHASE_SCENARIO"


def _lt(model, a, b, name):
    result = model.NewBoolVar(name)
    model.Add(a < b).OnlyEnforceIf(result)
    model.Add(a >= b).OnlyEnforceIf(result.Not())
    return result


def _and(model, terms, name):
    value = model.NewBoolVar(name)
    model.AddBoolAnd(terms).OnlyEnforceIf(value)
    model.AddBoolOr([t.Not() for t in terms]).OnlyEnforceIf(value.Not())
    return value


def _longest_free(intervals, start, end):
    cursor, best = start, 0
    for a, b in sorted(intervals):
        if b <= start or a >= end:
            continue
        a, b = max(start, a), min(end, b)
        best = max(best, a - cursor)
        cursor = max(cursor, b)
    return max(best, end - cursor)


def _intervals(values):
    """Compact integer-domain runs, not a sampled set of clock anchors."""
    result = []
    for value in sorted(set(values)):
        if result and value == result[-1][1] + 1:
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def _has_five_night_hours(a, b, zone):
    date = datetime.fromtimestamp(a * 60, timezone.utc).astimezone(zone).date() - timedelta(days=1)
    last = datetime.fromtimestamp(b * 60, timezone.utc).astimezone(zone).date()
    while date <= last:
        start = datetime.combine(date, datetime.min.time(), zone) + timedelta(hours=22)
        end = datetime.combine(date + timedelta(days=1), datetime.min.time(), zone) + timedelta(hours=8)
        if min(b, int(end.timestamp() // 60)) - max(a, int(start.timestamp() // 60)) >= 300:
            return True
        date += timedelta(days=1)
    return False


def _actual_night_supports(model, item, zone, prefix):
    """Actual selected continuous Jo, including a potentially cropped block."""
    values = []
    low, high = item["bounds"]
    date = datetime.fromtimestamp(low * 60, timezone.utc).astimezone(zone).date() - timedelta(days=1)
    last = datetime.fromtimestamp(high * 60, timezone.utc).astimezone(zone).date()
    night_index = 0
    while date <= last:
        night_a = int((datetime.combine(date, datetime.min.time(), zone) + timedelta(hours=22)).timestamp() // 60)
        night_b = int((datetime.combine(date + timedelta(days=1), datetime.min.time(), zone) + timedelta(hours=8)).timestamp() // 60)
        for block_index, block in enumerate(item["jour"]):
            label = prefix + f"_actual_night{night_index}_block{block_index}"
            # The original model represents each contiguous typed Jo block;
            # do not sum disjoint pieces to manufacture five continuous hours.
            clipped_left = model.NewIntVar(min(low, night_a), max(high, night_a), label + "_left")
            clipped_right = model.NewIntVar(min(low, night_b), max(high, night_b), label + "_right")
            model.AddMaxEquality(clipped_left, [block["left"], night_a])
            model.AddMinEquality(clipped_right, [block["right"], night_b])
            enough = _lt(model, 299, clipped_right - clipped_left, label + "_five_hours")
            values.append(_and(model, [block["active"], enough], label + "_selected_five_hours"))
        date += timedelta(days=1)
        night_index += 1
    return values


def add_standard_daily_rest(model, context):
    """Constrain every fixed 24h period intersecting P2/known outgoing duty.

    Unavoidable frozen-only shortfalls are retained as certificates, while new
    duties must preserve the exact longest available frozen rest in that
    period. Their rest requirement is never reset to zero. Unknown outer
    periods get a necessary optimistic-rest bound, never an approval of unseen
    rest: actual selected/frozen presence is included beyond the complete
    history horizon, and only the remaining unknown time is optimistically
    free. Uses only minute-exact domains.
    """
    from ortools.sat.python import cp_model

    data, period = context["data"], context["data"]["period"]
    rules = data["rules"]
    mode = rules.get("daily_rest_24h_mode", MODE)
    if mode != MODE:
        raise ValueError("Unsupported daily-rest interpretation; no implicit weakening")
    if rules.get("daily_rest_minutes", STANDARD) != STANDARD:
        raise ValueError("This source-backed standard profile requires exactly eleven hours")
    lo, hi = period["lo"], period["hi"]
    origin = period.get("history_lo", lo)
    known_hi = period.get("known_end", hi)
    if not isinstance(known_hi, int):
        raise ValueError("daily-rest known_end requires an absolute integer minute")
    people = {e["id"]: e for e in data["employees"]}
    by_person, frozen = defaultdict(list), defaultdict(list)
    for item in context["duties"].values():
        by_person[item["source"]["employee_id"]].append(item)
    for item in data.get("frozen_duties", []):
        frozen[item["employee_id"]].append(item)
    profile = rules.get("jour_compensation", {})
    exceptions_enabled = (isinstance(profile, dict)
        and profile.get("mode") == "PLANNED_AR_JO_REST_AT_LEAST_DUTY_SPAN"
        and profile.get("source_status") == "VERIFIED" and bool(profile.get("source_ref")))
    phases, windows = {}, []
    zone = ZoneInfo(period.get("timezone", "Europe/Stockholm"))
    context["daily_rest_phases"] = phases
    context["daily_rest_24h_scope"] = {
        "mode": MODE, "anchor_status": ANCHOR_STATUS,
        "local_application_status": "UNKNOWN", "same_phase_throughout_history_and_P2": True,
        "source": rules.get("daily_rest_source_ref", "REVIEWED_SOURCE_PROFILE; LOCAL_APPLICATION_SEPARATE"),
        "daily_anchor_source": None, "standard_rest_minutes": STANDARD,
        "period_minutes": DAY, "universal_13h_duty_cap": False,
        "rolling_every_minute_rule_inferred": False,
        "B_C_exception_application_status": "UNKNOWN",
        "mixed_window_safety": "WHOLE_DUTY_GAP_AT_LEAST_660_INSIDE_WINDOW_IF_TWO_DUTIES_TOUCH",
        "unknown_outer_periods_are_not_approved": True,
    }
    anchor_decision = rules.get("daily_rest_anchor_decision")
    confirmed_scenario_anchor = (isinstance(anchor_decision, dict)
        and anchor_decision.get("status") == "CONFIRMED" and anchor_decision.get("scope") == "TEST_SCENARIO_ONLY"
        and bool(anchor_decision.get("source_ref")) and anchor_decision.get("mode") == ANCHOR_STATUS)
    context["daily_rest_24h_scope"]["scenario_anchor_selection_status"] = "CONFIRMED_SCENARIO_ANCHOR_SELECTION" if confirmed_scenario_anchor else "UNKNOWN"
    context["daily_rest_24h_scope"]["anchor_decision"] = anchor_decision
    if not confirmed_scenario_anchor:
        context["unknown_controls"].append({"field": "daily_rest_24h_anchor_application",
            "status": "UNKNOWN", "why": "No supplied test decision authorizes selecting a constant daily phase; the source text alone does not establish the business's local anchor"})
    for identity, employee in people.items():
        known_lo = origin if employee.get("history_known", False) else lo
        phase = model.NewIntVar(0, DAY - 1, identity + "_fixed_daily_phase")
        supplied = employee.get("daily_rest_anchor_phase_minutes")
        if supplied is not None:
            if (employee.get("daily_rest_anchor_status") != "VERIFIED"
                    or not employee.get("daily_rest_anchor_source_ref")
                    or not isinstance(supplied, int) or isinstance(supplied, bool)
                    or not 0 <= supplied < DAY):
                raise ValueError(identity + ": daily anchor is not a sourced verified minute phase")
            model.Add(phase == supplied)
        phases[identity] = phase
        mutable_exceptions = []
        for item in by_person[identity]:
            cid = item["source"]["id"]
            if not exceptions_enabled or not item["work"] or not item["jour"]:
                continue
            positive_ar = _lt(model, 0, sum(v["selected"] for v in item["work"]), cid + "_24h_positive_ar")
            positive_jo = _lt(model, 0, sum(v["selected"] for v in item["jour"]), cid + "_24h_positive_jo")
            # Section b has no literal thirteen-hour lower threshold. Even a
            # shorter combined duty can need the exception for a fixed daily
            # phase. Choice of that exception entails its complete arithmetic.
            eligible = _and(model, [item["presence"], positive_ar, positive_jo], cid + "_24h_B_eligible")
            used = model.NewBoolVar(cid + "_24h_B_used")
            model.AddImplication(used, eligible)
            c = profile.get("c_application")
            allow_c = (isinstance(c, dict) and c.get("status") == "CONFIRMED"
                and bool(c.get("source_ref")) and identity in c.get("employee_ids", [])
                and all(c.get(key) is True for key in ("not_healthcare_sector", "necessity", "no_reasonable_alternatives"))
                and profile.get("C_application_mode") != "DISABLED_UNTIL_APPLICATION_VERIFIED")
            model.Add(item["end"] - item["start"] <= (1440 if allow_c else 1200)).OnlyEnforceIf(used)
            night_supports = _actual_night_supports(model, item, zone, cid + "_24h_B")
            model.Add(sum(night_supports) >= 1).OnlyEnforceIf(used)
            for other in by_person[identity]:
                if other is item:
                    continue
                follows = _lt(model, item["end"] - 1, other["start"], cid + "_24h_B_before_" + other["source"]["id"])
                model.Add(other["start"] >= 2 * item["end"] - item["start"]).OnlyEnforceIf([used, other["presence"], follows])
            mutable_exceptions.append((item, used))
        frozen_exceptions = [d for d in frozen[identity] if exceptions_enabled
            and d.get("work") and d.get("jour")
            and d["end"] - d["start"] <= DAY
            and any(_has_five_night_hours(a, b, zone) for a, b in d["jour"])]
        frozen_exception_flags = {}
        for fixed in frozen_exceptions:
            used = model.NewBoolVar(fixed["id"] + "_24h_frozen_B_used")
            frozen_exception_flags[fixed["id"]] = used
            for other in by_person[identity]:
                follows = _lt(model, fixed["end"] - 1, other["start"], fixed["id"] + "_24h_B_before_" + other["source"]["id"])
                model.Add(other["start"] >= 2 * fixed["end"] - fixed["start"]).OnlyEnforceIf([used, other["presence"], follows])
        relevant_hi = max([hi] + [item["bounds"][1] for item in by_person[identity]]
            + [item["end"] for item in frozen[identity] if item["end"] > lo])
        for index in range(-1, (relevant_hi - origin) // DAY + 1):
            base = origin + index * DAY
            # Skip periods that cannot intersect mutable P2 at any phase.
            if base + 2 * DAY <= lo or base >= relevant_hi:
                continue
            start, end = base + phase, base + phase + DAY
            prefix = f"{identity}_day{index}"
            active = _and(model, [
                _lt(model, start, relevant_hi, prefix + "_before_relevant_end"),
                _lt(model, lo, end, prefix + "_touches_p2")], prefix + "_known_or_outer_p2")
            fully_known = _and(model, [
                _lt(model, known_lo - 1, start, prefix + "_known_left"),
                _lt(model, end, known_hi + 1, prefix + "_known_right")], prefix + "_fully_known")
            exception_flags = []
            for item, flag in mutable_exceptions:
                if item["bounds"][1] <= base or item["bounds"][0] >= base + 2 * DAY:
                    continue
                exception_flags.append(_and(model, [flag,
                    _lt(model, item["start"], end, prefix + item["source"]["id"] + "_left"),
                    _lt(model, start, item["end"], prefix + item["source"]["id"] + "_right")],
                    prefix + item["source"]["id"] + "_exception_overlap"))
            for fixed in frozen_exceptions:
                if fixed["end"] <= base or fixed["start"] >= base + 2 * DAY:
                    continue
                exception_flags.append(_and(model, [
                    frozen_exception_flags[fixed["id"]],
                    _lt(model, fixed["start"], end, prefix + fixed["id"] + "_left"),
                    _lt(model, start, fixed["end"], prefix + fixed["id"] + "_right")],
                    prefix + fixed["id"] + "_exception_overlap"))
            enforce = _and(model, [active] + [v.Not() for v in exception_flags], prefix + "_standard")
            baseline = [(d["start"], d["end"]) for d in frozen[identity]
                if d["end"] > base and d["start"] < base + 2 * DAY]
            requirement = STANDARD
            if baseline:
                values = [min(STANDARD, _longest_free(baseline, base + value, base + value + DAY)) for value in range(DAY)]
                if min(values) < STANDARD:
                    requirement = model.NewIntVar(min(values), STANDARD, prefix + "_frozen_rest_requirement")
                    model.AddElement(phase, values, requirement)
                    context["historical_certificates"].append({
                        "rule": "daily_rest_24h_frozen_phase_dependent", "employee_id": identity,
                        "period_base": base, "affected_phase_intervals": _intervals(i for i, value in enumerate(values) if value < STANDARD),
                        "minimum_frozen_longest_rest_minutes": min(values),
                        "policy": "P2_MUST_NOT_REDUCE_FROZEN_LONGEST_REST; selected phase must be independently reported"})
            rest = model.NewIntVar(base, base + 2 * DAY, prefix + "_rest_start")
            model.Add(rest >= start).OnlyEnforceIf(enforce)
            model.Add(rest + requirement <= end).OnlyEnforceIf(enforce)
            for item in by_person[identity]:
                if item["bounds"][1] <= base or item["bounds"][0] >= base + 2 * DAY:
                    continue
                before = model.NewBoolVar(prefix + item["source"]["id"] + "_before_rest")
                model.Add(item["end"] <= rest).OnlyEnforceIf([enforce, item["presence"], before])
                model.Add(item["start"] >= rest + requirement).OnlyEnforceIf([enforce, item["presence"], before.Not()])
            for fixed in frozen[identity]:
                if fixed["end"] <= base or fixed["start"] >= base + 2 * DAY:
                    continue
                before = model.NewBoolVar(prefix + fixed["id"] + "_before_rest")
                model.Add(fixed["end"] <= rest).OnlyEnforceIf([enforce, before])
                model.Add(fixed["start"] >= rest + requirement).OnlyEnforceIf([enforce, before.Not()])
            windows.append({"employee_id": identity, "index": index, "base": base,
                "active": active, "standard_enforced": enforce, "exception_flags": exception_flags,
                "rest_start": rest, "required_rest": requirement, "fully_known": fully_known,
                "outer_policy": "OPTIMISTIC_NECESSARY_BOUND_NEVER_APPROVAL"})
    context["daily_rest_windows"] = windows
    return context["daily_rest_24h_scope"]
