"""Independent minute arithmetic extracted from the reviewed experiment.

No solver/model imports. PASS applies only to named checks. Contract application,
full24h daily rest and practical simultaneous participation remain UNKNOWN.
"""
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta


def check_arithmetic(case, solution):
    started = time.monotonic()
    exports = {}
    original = {"needs": case.get("source_needs",case["needs"]), "references":case["references"]}
    H = case["horizon"]
    profile = case["config"]["duty_profile"]
    ORIGIN = datetime.fromisoformat(case["origin"])
    staff = {p["id"]: p for p in case["staff"]}
    needs = {n["id"]: n for n in case["needs"]}
    WITH_BREAKS = True
    CALENDAR_MODE = case['config']['calendar_mode']
    assert CALENDAR_MODE == 'rolling'
    source_ids = {r["id"] for r in original["references"]["import"]["segments"]}
    # Trust only the importer's reviewed grouping, never a solver-supplied label.
    whole_duty_ids = {r["id"]: r["whole_duty_id"] for r in original["references"]["import"]["segments"] if r.get("whole_duty_id")}
    units = {u["id"]: u for u in case["reassignable_temporary_units"]}
    errors = []
    inherited = []
    people = {}
    available = {}
    gross_masks = {}
    all_occasions = {}
    omitted_break_rule_violations = []
    
    
    def stamp(t):
        return (ORIGIN + timedelta(minutes=t)).isoformat(timespec="minutes")
    
    
    def union(intervals):
        out = []
        for a, b in sorted(intervals):
            if a >= b:
                errors.append({"rule": "invalid_interval", "start": a, "end": b})
                continue
            if out and a <= out[-1][1]:
                out[-1][1] = max(out[-1][1], b)
            else:
                out.append([a, b])
        return out
    
    
    def mask(intervals):
        v = bytearray(H)
        for a, b in intervals:
            a, b = max(0, a), min(H, b)
            if a < b:
                v[a:b] = b"\1" * (b - a)
        return v
    
    
    def subtract(intervals, exclusions):
        out = []
        exclusions = union(exclusions)
        for a, b in union(intervals):
            cursor = a
            for x, y in exclusions:
                if y <= cursor or x >= b:
                    continue
                if x > cursor:
                    out.append((cursor, min(x, b)))
                cursor = max(cursor, y)
                if cursor >= b:
                    break
            if cursor < b:
                out.append((cursor, b))
        return out
    
    
    def save(name, value):
        exports[name] = value
    
    
    actual_needs = {n["id"]:n for n in case["needs"]}
    if len(actual_needs) != len(case["needs"]) or set(actual_needs) != {n["id"] for n in original["needs"]} or any({k:actual_needs[n["id"]].get(k) for k in n} != n for n in original["needs"]):
        errors.append({"rule": "original_need_records_changed"})
    expected_history = {(r["id"],r["person"],r["start"],r["end"],r["code"]) for r in original["references"]["import"]["segments"] if r["code"] in {"Ar","Jo","Kl","Öv"} and r["start"]<0}
    actual_history = {(r["id"],r["person"],r["start"],r["end"],r["code"]) for r in solution.get("segments",[]) if r["code"] in {"Ar","Jo","Kl","Öv"} and r["start"]<0}
    if expected_history-actual_history:
        errors.append({"rule":"known_actual_P1_work_missing","missing":sorted(expected_history-actual_history)})
    source_work_reference = {}
    for person, p in staff.items():
        raw_ar = union([(max(0,r["start"]), min(H,r["end"])) for r in original["references"]["import"]["segments"] if r["person"] == person and r["code"] == "Ar" and r["end"] > 0 and r["start"] < H])
        gross = sum(b-a for a,b in raw_ar)
        active_max = case["config"]["max_continuous_active"]; break_len = case["config"]["break_length"]
        break_minutes = break_len * sum(max(0,(b-a-active_max+active_max+break_len-1)//(active_max+break_len)) for a,b in raw_ar) if WITH_BREAKS else 0
        reference = gross-break_minutes
        source_work_reference[person] = {"gross_minutes": gross, "minimum_repeated_break_minutes": break_minutes, "reference_worked_net_minutes": reference}
        if p["ordinary"] and p["target_net"] != reference:
            errors.append({"rule": "target_not_matched_to_original_known_Ar", "person": person, "case_target": p["target_net"], "independently_derived_reference": reference})
    if not WITH_BREAKS and solution.get("breaks"):
        errors.append({"rule": "unexpected_break_in_authorized_without_breaks_test"})
    
    
    assignments = solution.get("temporary_unit_reassignments", [])
    mapping = {}
    recipient_by_unit = {}
    for assignment in assignments:
        uid = assignment["unit_id"]
        if uid not in units:
            errors.append({"rule": "unknown_unit", "unit": uid})
            continue
        u = units[uid]
        person = assignment["new_person"]
        recipient_by_unit[uid] = person
        if assignment["original_person"] != u["original_person"] or set(assignment["segment_ids"]) != set(u["segment_ids"]):
            errors.append({"rule": "unit_integrity", "unit": uid})
        if person not in staff or (person != u["original_person"] and not staff[person]["ordinary"]):
            errors.append({"rule": "recipient_not_allowed", "unit": uid, "person": person})
        if person != u["original_person"] and u["end"] - u["start"] > profile["max_reassigned_minutes"]:
            errors.append({"rule": "new_recipient_over24h", "unit": uid, "person": person})
        for id in assignment["segment_ids"]:
            if id in mapping:
                errors.append({"rule": "duplicate_mapped_segment", "id": id})
            mapping[id] = person
    if set(recipient_by_unit) != set(units):
        errors.append({"rule": "missing_or_extra_unit_recipient", "missing": sorted(set(units) - set(recipient_by_unit))})
    
    segments = solution.get("segments", [])
    for row in segments:
        if row["person"] not in staff or row["start"] >= row["end"]:
            errors.append({"rule": "invalid_segment_person_or_span", "segment": row.get("id")})
    for row in solution.get("breaks", []):
        if row["person"] not in staff:
            errors.append({"rule": "invalid_break_person", "break": row})
    segment_by_id = {s["id"]: s for s in segments}
    if len(segment_by_id) != len(segments):
        errors.append({"rule": "duplicate_segment_id"})
    keys = ["id", "person", "start", "end", "type", "code"]
    expected_fixed = {tuple(mapping.get(row["id"], row["person"]) if k == "person" else row.get(k) for k in keys) for row in case["fixed_segments"]}
    actual_keys = {tuple(row.get(k) for k in keys) for row in segments}
    if expected_fixed - actual_keys:
        errors.append({"rule": "fixed_segment_modified_or_missing", "count": len(expected_fixed - actual_keys)})
    candidates = {c["id"]: c for c in case["candidates"]}
    fixed_ids = {r["id"] for r in case["fixed_segments"]}
    for r in segments:
        if r["id"] in fixed_ids:
            continue
        c = candidates.get(r["id"])
        if not c or r["person"] != c["person"] or r["code"] != "Ar":
            errors.append({"rule": "unknown_or_invalid_candidate", "segment": r["id"]})
            continue
        length = r["end"] - r["start"]
        if not (c["lo"] <= r["start"] < r["end"] <= c["hi"] and c["min_length"] <= length <= c["max_length"]):
            errors.append({"rule": "candidate_bounds_or_length", "segment": r["id"]})
    if any(r["code"] in {"St", "Sj"} or (r["code"] in {"Kl","Öv"} and r["end"]>0 and r["start"]<H) for r in segments):
        errors.append({"rule": "unexpected_excluded_outcome_code"})
    if case.get("integration",{}).get("absence_mode") != "preserve" and any(r["code"] in {"Se", "Ti"} and r["end"] > 0 and r["start"] < H for r in segments):
        errors.append({"rule": "unexpected_P2_SeTi_in_declared_ground_scenario"})
    
    for lock in case.get("confirmed_absence_locks",[]):
        for row in segments:
            if row["person"]==lock["person"] and row["code"] in {"Ar","Jo","Kl","Öv"} and max(row["start"],lock["start"])<min(row["end"],lock["end"]):
                errors.append({"rule":"work_during_confirmed_absence","person":row["person"],"segment":row["id"],"absence":lock["id"]})
    for person, p in staff.items():
        rows = [r for r in segments if r["person"] == person]
        ar = union([(r["start"], r["end"]) for r in rows if r["code"] == "Ar"])
        for i, left in enumerate(rows):
            if left["code"] not in {"Ar", "Jo", "Kl", "Öv"}:
                continue
            for right in rows[i+1:]:
                if right["code"] not in {"Ar", "Jo", "Kl", "Öv"}:
                    continue
                if max(left["start"], right["start"]) < min(left["end"], right["end"]):
                    errors.append({"rule": "same_person_overlapping_Ar_Jo_segments", "person": person, "left": left["id"], "right": right["id"]})
        pb = sorted((b["start"], b["end"]) for b in solution.get("breaks", []) if b["person"] == person)
        for index, (a, b) in enumerate(pb):
            if b - a != case["config"]["break_length"] or a >= b:
                errors.append({"rule": "break_length", "person": person, "start": a, "end": b})
            if not any(x <= a and b <= y for x, y in ar):
                errors.append({"rule": "break_outside_contiguous_Ar", "person": person, "start": a, "end": b})
            if index and a < pb[index - 1][1]:
                errors.append({"rule": "overlapping_breaks", "person": person, "start": a})
        for b in solution.get("breaks", []):
            if b["person"] == person and b.get("frozen_chain"):
                if not (b["chain_start"] <= b["start"] < b["end"] <= b["chain_end"]):
                    errors.append({"rule": "fixed_break_chain_membership", "person": person, "break": b})
        active = subtract(ar, pb)
        bad_active = [(a, b) for a, b in active if b > 0 and a < H and b - a > case["config"]["max_continuous_active"]]
        if bad_active and WITH_BREAKS:
            errors.append({"rule": "active_continuous_over5h", "person": person, "intervals": bad_active})
        elif bad_active:
            omitted_break_rule_violations.append({"person": person, "intervals": [{"start": stamp(a), "end": stamp(b), "minutes": b-a} for a,b in bad_active]})
        gm = mask(ar)
        av = mask(active)
        available[person] = av
        gross_masks[person] = gm
        if p["ordinary"] and sum(av) != p["target_net"]:
            errors.append({"rule": "retained_original_worked_net", "person": person, "target": p["target_net"], "actual": sum(av)})
        if not p["all_task_skills"]:
            errors.append({"rule": "uniform_skills_unconfirmed", "person": person})
        groups = defaultdict(list)
        for r in rows:
            if r["code"] in {"Ar", "Jo", "Kl", "Öv"}:
                groups[whole_duty_ids.get(r["id"]) or (r["id"].rsplit("-", 1)[0] if r["id"] in source_ids else r["id"])].append(r)
        occasions = sorted([{"id": id, "start": min(r["start"] for r in rr), "end": max(r["end"] for r in rr), "rows": rr} for id, rr in groups.items()], key=lambda occasion: (occasion["start"], occasion["end"]))
        all_occasions[person] = occasions
        short = [o for o in occasions if 0 <= o["start"] < H and o["end"] - o["start"] < case["config"]["min_shift"]]
        if short:
            errors.append({"rule": "whole_occasion_under4h", "person": person, "ids": [o["id"] for o in short]})
        maximum=case['config'].get('max_whole_duty_minutes')
        if maximum is not None:
            for o in occasions:
                if 0<=o['start']<H and o['end']-o['start']>maximum:
                    errors.append(dict(rule='whole_duty_over_selected_limit',person=person,
                                       occasion=o['id'],actual_minutes=o['end']-o['start'],limit_minutes=maximum))
        gaps = [right["start"] - left["end"] for left, right in zip(occasions, occasions[1:]) if 0 <= right["start"] < H]
        if any(g < case["config"]["min_daily_rest"] for g in gaps):
            errors.append({"rule": "daily_rest11h", "person": person, "gaps": [g for g in gaps if g < case["config"]["min_daily_rest"]]})
        occupied = {d for d in range(-H//1440,H//1440) if any(r["start"] < (d + 1) * 1440 and r["end"] > d * 1440 for r in rows)}
        free = [d for d in range(H//1440) if d not in occupied]
        rolling_free = min(H//1440 - len(occupied & set(range(end - H//1440,end))) for end in range(1,H//1440+1))
        if len(free) < case["config"]["min_free_days"] or (CALENDAR_MODE=="rolling" and rolling_free < case["config"]["min_free_days"]):
            errors.append({"rule": "free_calendar_days9", "person": person, "p2_free": len(free), "rolling_min": rolling_free})
        work = union([(r["start"], r["end"]) for r in rows if r["code"] in {"Ar", "Jo", "Kl", "Öv"}])
        weeks = []
        for week in range(H//10080):
            lo, hi = week * 10080, (week + 1) * 10080
            pos, best = lo, 0
            for a, b in union([(max(lo, a), min(hi, b)) for a, b in work if b > lo and a < hi]):
                best = max(best, a - pos)
                pos = max(pos, b)
            weeks.append(max(best, hi - pos))
        if any(v < case["config"]["min_weekly_rest"] for v in weeks):
            errors.append({"rule": "fixed_Monday_weekly_rest36h", "person": person, "weeks": weeks})
        for o in occasions:
            if not (o["end"] > 0 and o["start"] < H and profile["long_jour_min_minutes"] <= o["end"] - o["start"] <= profile["max_reassigned_minutes"]):
                continue
            best = 0
            jo = union([(r["start"], r["end"]) for r in o["rows"] if r["code"] == "Jo"])
            for day in range(o["start"] // 1440 - 1, o["end"] // 1440 + 1):
                for a, b in jo:
                    best = max(best, max(0, min(b, (day + 1) * 1440 + profile["night_end_minute"]) - max(a, day * 1440 + profile["night_start_minute"])))
            if best < profile["night_jour_min_minutes"]:
                record = {"rule": "night_Jo_contiguous5h", "person": person, "occasion": o["id"], "actual_minutes": best, "start": stamp(o["start"]), "end": stamp(o["end"])}
                original_unit = units.get(o["id"])
                if original_unit and recipient_by_unit.get(o["id"]) != original_unit["original_person"]:
                    errors.append(record)
                else:
                    inherited.append(record)
        people[person] = {"ordinary": p["ordinary"], "target_minutes": p["target_net"], "gross_Ar_minutes": sum(gm), "break_minutes": sum(gm) - sum(av), "worked_net_minutes": sum(av), "maximum_continuous_active_minutes_P2": max((b - a for a, b in active if b > 0 and a < H), default=0), "free_days": len(free), "free_dates": [(ORIGIN + timedelta(days=d)).date().isoformat() for d in free], "rolling_free_min": rolling_free, "known_fixed_P1_free_calendar_days": H//1440-len(occupied & set(range(-H//1440,0))), "weekly_rest_minutes": weeks, "minimum_daily_gap": min(gaps, default=None), "whole_source_envelope_count_P2": sum(o["start"] < H and o["end"] > 0 for o in occasions), "jour_P2_minutes": sum(mask([(r["start"], r["end"]) for r in rows if r["code"] == "Jo"]))}
    
    max_active_gross = max((sum(v[t] for v in gross_masks.values()) for t in range(H)), default=0)
    if max_active_gross > case["config"]["max_staff_on_duty"]:
        errors.append({"rule": "max2_active_staff", "actual": max_active_gross})
    jo_end = max([H] + [r["end"] for r in segments if r["code"] == "Jo"])
    for person in staff:
        jo = bytearray(H + jo_end)
        for r in segments:
            if r["person"] == person and r["code"] == "Jo":
                a, b = max(-H, r["start"]) + H, min(jo_end, r["end"]) + H
                if a < b:
                    jo[a:b] = b"\1" * (b - a)
        total = sum(jo[:H])
        maximum, where = total, 0
        for t in range(H, len(jo)):
            total += jo[t] - jo[t - H]
            if total > maximum:
                maximum, where = total, t - H + 1
        people[person]["rolling_Jo_max_minutes"] = maximum
        people[person]["rolling_Jo_max_window_end"] = stamp(where)
        if maximum > case["config"]["oncall_cap_28d"]:
            errors.append({"rule": "rolling28day_Jo48h", "person": person, "actual": maximum})
    
    placed = {p["id"]: p for p in solution.get("placements", [])}
    if len(placed) != len(solution.get("placements", [])):
        errors.append({"rule": "duplicate_need_id"})
    at = defaultdict(list)
    for id, placement in placed.items():
        if id not in needs:
            errors.append({"rule": "unknown_placed_need", "id": id})
            continue
        n = needs[id]
        if not any(a <= placement["start"] <= b for a, b in n["domains"]):
            errors.append({"rule": "need_window", "id": id})
        if placement["start"] < 0 or placement["start"] + n["duration"] > H:
            errors.append({"rule": "need_outside_period", "id": id})
            continue
        for t in range(placement["start"], placement["start"] + n["duration"]):
            at[t].append(id)
    failures = defaultdict(list)
    executor_rows = []
    overlaps = []
    open_execution = {}
    open_overlaps = {}
    previous = {}
    hist = Counter()
    deficit = 0
    for t in range(H):
        ids = at[t]
        free = {p for p, av in available.items() if av[t]}
        demand = sum(needs[id]["count"] for id in ids if needs[id]["exclusive"]) + max((needs[id]["count"] for id in ids if not needs[id]["exclusive"]), default=0)
        if demand > len(free):
            deficit += 1
        assigned = {}
        load = Counter()
        for id in sorted(ids, key=lambda n: (not needs[n]["exclusive"], n)):
            chosen = sorted(free, key=lambda p: (load[p], p not in previous.get(id, []), p))[:needs[id]["count"]]
            assigned[id] = chosen
            if len(chosen) < needs[id]["count"]:
                failures[id].append(t)
            for p in chosen:
                load[p] += 1
            if needs[id]["exclusive"]:
                free.difference_update(chosen)
        per_person = defaultdict(list)
        for id, pp in assigned.items():
            for p in pp:
                per_person[p].append(id)
        for p, ids_for_p in per_person.items():
            hist[len(ids_for_p)] += 1
            if len(ids_for_p) > 1 and any(needs[id]["exclusive"] for id in ids_for_p):
                errors.append({"rule": "shopping_overlap", "person": p, "minute": t, "ids": ids_for_p})
        keys_now = {(id, p) for id, pp in assigned.items() for p in pp}
        for key in list(open_execution):
            if key not in keys_now:
                id, p = key
                executor_rows.append({"id": id, "person": p, "customer": needs[id]["customer"], "title": needs[id]["title"], "start": stamp(open_execution.pop(key)), "end": stamp(t)})
        for key in keys_now:
            if key not in open_execution:
                open_execution[key] = t
        overlap_keys = {(p, tuple(sorted(ids))) for p, ids in per_person.items() if len(ids) > 1}
        for key in list(open_overlaps):
            if key not in overlap_keys:
                overlaps.append({"person": key[0], "start": stamp(open_overlaps.pop(key)), "end": stamp(t), "count": len(key[1]), "tasks": [{"id": id, "customer": needs[id]["customer"], "title": needs[id]["title"]} for id in key[1]]})
        for key in overlap_keys:
            if key not in open_overlaps:
                open_overlaps[key] = t
        previous = assigned
    for (id, p), t in open_execution.items():
        executor_rows.append({"id": id, "person": p, "customer": needs[id]["customer"], "title": needs[id]["title"], "start": stamp(t), "end": stamp(H)})
    for (p, ids), t in open_overlaps.items():
        overlaps.append({"person": p, "start": stamp(t), "end": stamp(H), "count": len(ids), "tasks": [{"id": id, "customer": needs[id]["customer"], "title": needs[id]["title"]} for id in ids]})
    if failures:
        errors.append({"rule": "executor_coverage", "failed_needs": len(failures), "deficit_clock_minutes": deficit})
    
    compensation = []
    comp_unknown = []
    long_25 = []
    checked_compensation = []
    for person, occasions in all_occasions.items():
        for index, o in enumerate(occasions):
            span = o["end"] - o["start"]
            if not (o["end"] + span > 0 and o["start"] < H and {r["code"] for r in o["rows"]} == {"Ar", "Jo"}):
                continue
            record = {"person": person, "occasion": o["id"], "start": stamp(o["start"]), "end": stamp(o["end"]), "span_minutes": span}
            if span > profile["max_reassigned_minutes"]:
                long_25.append(record)
            if span > profile["compensation_trigger_minutes"]:
                if index + 1 < len(occasions):
                    nxt = occasions[index + 1]
                    gap = nxt["start"] - o["end"]
                    checked_compensation.append(dict(record, next_occasion=nxt["id"], next_start=stamp(nxt["start"]), actual_rest_minutes=gap, reference_required_minutes=span, margin_minutes=gap-span))
                    if gap < span:
                        compensation.append(dict(record, next_occasion=nxt["id"], next_start=stamp(nxt["start"]), actual_rest_minutes=gap, reference_required_minutes=span, shortfall_minutes=span-gap))
                elif o["end"] + span > H:
                    comp_unknown.append(dict(record, required_until=stamp(o["end"] + span)))
    save("reference_profile_diagnostic.json", {"status": "REFERENCE_DEFAULT_DIAGNOSIS_NOT_APPLICABLE_RULE_CONFIRMATION", "default": "combined/extended rest >= whole duty span immediately after, for span >12h; domain.py428–450,537–550", "known_reference_default_rest_shortfalls": compensation, "known_reference_default_checked_gaps_including_P1_edge": checked_compensation, "unknown_boundary_compensation": comp_unknown, "inherited_over24h_occasions": long_25, "limitations": ["The reference profile's applicability and individual exception approval remain unconfirmed.", "This diagnosis does not turn a missing business check into approval or rejection under an assumed agreement."]})
    
    weekly_active_net = {
        person: [sum(available[person][week*10080:(week+1)*10080]) for week in range(H//10080)]
        for person in staff
    }
    independent_peak = max(max(values) for values in weekly_active_net.values())
    workload_export = solution.get('workload_objectives')
    if workload_export:
        if workload_export.get('active_net_week_minutes_by_person') != weekly_active_net:
            errors.append({'rule': 'exported_weekly_workload_not_independently_reproduced',
                           'independent': weekly_active_net,
                           'exported': workload_export.get('active_net_week_minutes_by_person')})
        if workload_export.get('highest_active_net_week_minutes') != independent_peak:
            errors.append({'rule': 'exported_highest_active_week_incorrect',
                           'independent': independent_peak,
                           'exported': workload_export.get('highest_active_net_week_minutes')})
    known_P3_overhang = [dict(r, start_iso=stamp(r['start']), end_iso=stamp(r['end']))
                        for r in solution['segments']
                        if r['code'] in {'Ar','Jo','Kl','Öv'} and r['end'] > H]
    save('independent_workload.json', {
        'status': 'DESCRIPTIVE_MODEL_WORKLOAD_NOT_LEGAL_APPROVAL',
        'definition': 'Ar availability after explicit breaks, minute-counted independently; all9staff, four Monday-Sunday P2 weeks',
        'weekly_active_net_minutes': weekly_active_net,
        'highest_active_net_week_minutes': independent_peak,
        'known_overhang_after_P2': known_P3_overhang,
        'post_period_breaks_or_complete_P3_duties': 'UNKNOWN_NO_ZERO_ASSUMPTION',
        'additional_hard_weekly_limit': False,
    })
    summary = {
        "status": "WORKLOAD_BALANCE_LIMITED_SCENARIO_NOT_APPROVED",
        "calendar_mode_assumption": CALENDAR_MODE,
        "source_cell_grouping_status": "EXPLICIT_UNVERIFIED_ENVELOPE_ASSUMPTION",
        "source_file": "computed_result",
        "source_sha256": hashlib.sha256(json.dumps(solution,sort_keys=True).encode()).hexdigest(),
        "scope_check_pass": not errors,
        "scope_errors": errors,
        "inherited_conditional_Jo_issues": inherited,
        "original_work_reference_by_person": source_work_reference,
        "target_definition": "Known imported Ar, after this variant's break rule; not contractual SSG or a verified original planned schedule",
        "contract_capacity_claim": "NOT_MADE",
        "break_rule_status": "CHECKED_IN_SCOPE" if WITH_BREAKS else "BROKEN_INTENTIONALLY_OMITTED_TEST",
        "omitted_break_rule_violations": omitted_break_rule_violations,
        "ordinary_net_minutes": sum(p["worked_net_minutes"] for p in people.values() if p["ordinary"]),
        "temporary_net_minutes": sum(p["worked_net_minutes"] for p in people.values() if not p["ordinary"]),
        "ordinary_gross_minutes": sum(p["gross_Ar_minutes"] for p in people.values() if p["ordinary"]),
        "temporary_gross_minutes": sum(p["gross_Ar_minutes"] for p in people.values() if not p["ordinary"]),
        "break_minutes": sum(p["break_minutes"] for p in people.values()),
        "jour_P2_minutes": sum(p["jour_P2_minutes"] for p in people.values()),
        "people": people,
        "source_needs": len(needs),
        "placed_needs": len(placed),
        "fully_covered_needs": len(placed) - len(failures),
        "unplaced_needs": sorted(set(needs) - set(placed)),
        "failed_needs": [{"id": id, "missing_minutes": len(ts), "first_time": stamp(ts[0])} for id, ts in sorted(failures.items())],
        "deficit_clock_minutes": deficit,
        "maximum_active_gross_presence": max_active_gross,
        "maximum_parallel_tasks": max(hist, default=0),
        "parallel_person_minutes_histogram": dict(hist),
        "break_count": len(solution.get("breaks", [])),
        "lost_vs_comparison_reference": sorted({p["id"] for p in case.get("comparison_reference",{}).get("placements",[])} - set(placed)),
        "jour_compensation": {"status": "UNKNOWN_APPLICABLE_RULE_NOT_CONFIRMED", "reference_default_shortfalls": len(compensation), "unknown_boundary_intervals": len(comp_unknown)},
        "absence_credit": {"status": "PRESERVED_LOCK_ACCOUNTING_UNKNOWN" if case.get("integration",{}).get("absence_mode")=="preserve" else "EXCLUDED_BY_USER_AUTHORIZED_GROUND_SCENARIO", "p2_SeTi_worked_credit_minutes": None},
        "limitations": [
            "Checks apply only to the explicit input scenario, not a complete approved staffing plan.",
            "Source-cell envelopes are not verified whole-duty identifiers; no work is reconstructed from absence/outcome codes.",
            "Known timed history is retained; missing/untimed history and unknown future edges are not treated as zero or rest.",
            "The compensation profile and practical concurrent active participation remain unverified.",
            "Untimed support duties and contractual accounting are not inferred from numerical capacity differences.",
        ],
        "seconds": time.monotonic() - started,
    }
    save("independent_check.json", summary)
    save("overlaps.json", overlaps)
    exports["executors"] = executor_rows
    return {"summary":summary, "exports":exports}
