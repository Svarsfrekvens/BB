"""Compute one Vintergatan C proposal from verified needs and original evidence.

The retained A/B file supplies exact need windows and a warm start for individual
placements. Its constructed duties are discarded. The model chooses new legal
five-minute shift templates, retains valid person-linked work when feasible,
and assigns remaining work to explicit synthetic substitute schedules.

This is an isolated local calculation. It never contacts an app or repository.
"""

import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from ortools.sat.python import cp_model

from vg_validate_candidate import validate, stable

DEC_END = 28 * 1440


def template(start, end, night=False):
    if end - start <= 300:
        return [(start, end, [], night)]
    options = []
    if end - start <= 600:
        for b in range(start + 180, min(start + 300, end - 30) + 1, 30):
            if end - (b + 30) <= 300:
                options.append((start, end, [[b, b + 30]], night))
    else:
        for a in range(start + 180, start + 301, 30):
            for b in range(a + 180, min(a + 330, end - 30) + 1, 30):
                if b - (a + 30) <= 300 and end - (b + 30) <= 300:
                    options.append((start, end, [[a, a + 30], [b, b + 30]], night))
    return options


def shifts():
    result = []
    day_variants = [(390, 870), (420, 900), (480, 960), (780, 1290), (840, 1320),
                    (390, 1170), (540, 1320),
                    (390, 630), (630, 870), (840, 1080), (1080, 1320)]
    for day in range(28):
        base = day * 1440
        for a, b in day_variants:
            result.extend(template(base + a, base + b))
        result.extend(template(base + 1285, base + 1440 + 435, True))
        result.extend(template(base + 1260, base + 1440 + 495, True))
    result.extend(template(0, 435, True))  # known-period part of the incoming night
    result.extend(template(0, 495, True))
    return result


def covered(shift, start, end):
    a, b, breaks, _ = shift
    return a <= start and end <= b and all(end <= x or start >= y for x, y in breaks)


def groups_from(old):
    need_ids = {n["id"] for n in old["needs"] if n["period"] == "DECEMBER"}
    by_duty = defaultdict(list)
    for a in old["assignments"]:
        if a["need_id"] in need_ids:
            by_duty[a["duty_id"]].append(a)
    old_duty = {d["id"]: d for d in old["duties"]}
    groups = []
    for duty_id, rows in by_duty.items():
        remaining = set(range(len(rows)))
        while remaining:
            component = {remaining.pop()}
            changed = True
            while changed:
                changed = False
                for j in list(remaining):
                    if any(max(rows[i]["start"], rows[j]["start"]) < min(rows[i]["end"], rows[j]["end"]) for i in component):
                        remaining.remove(j)
                        component.add(j)
                        changed = True
            members = [rows[i] for i in sorted(component)]
            groups.append({"start": min(r["start"] for r in members), "end": max(r["end"] for r in members),
                           "rows": members, "person": old_duty[duty_id]["person_id"],
                           "admin": False})
    return groups


def solve_ordinary(groups, templates, staff, seconds, admin_person, night_allowed, external):
    chosen = []
    kept = set()
    for person_index, person in enumerate(staff):
        own = [(i, g) for i, g in enumerate(groups) if g["person"] == person["id"]]
        if not own:
            continue
        eligible = [(j, t) for j, t in enumerate(templates) if (not t[3] or person["id"] in night_allowed)
                    and all(t[1] + 660 <= a or b + 660 <= t[0] for a, b in external.get(person["id"], []))
                    and (any(covered(t, g["start"], g["end"]) for _, g in own)
                    or (person["id"] == admin_person and t[0] % 1440 == 480 and t[1] - t[0] == 480))]
        model = cp_model.CpModel()
        x = {j: model.new_bool_var(f"s{j}") for j, _ in eligible}
        keep = {i: model.new_bool_var(f"g{i}") for i, _ in own}
        for i, g in own:
            possible = [x[j] for j, t in eligible if covered(t, g["start"], g["end"])]
            if possible:
                model.add(sum(possible) >= keep[i])
            else:
                model.add(keep[i] == 0)
        for at, (j, a) in enumerate(eligible):
            for k, b in eligible[at + 1:]:
                if b[0] < a[1] + 660 and a[0] < b[1] + 660:
                    model.add(x[j] + x[k] <= 1)
        model.add(sum((t[1] - t[0] - sum(b - a for a, b in t[2])) * x[j] for j, t in eligible)
                  <= int(float(person["contract_seconds"]) / 60 + 0.001))
        if person["id"] == admin_person:
            model.add(sum((t[1] - t[0] - sum(b - a for a, b in t[2])) * x[j] for j, t in eligible)
                      - sum((g["end"] - g["start"]) * keep[i] for i, g in own) >= 1800)
        worked = []
        for day in range(28):
            w = model.new_bool_var(f"w{day}")
            xs = [x[j] for j, t in eligible if t[0] < (day + 1) * 1440 and t[1] > day * 1440]
            for v in xs:
                model.add(w >= v)
            model.add(w <= sum(xs))
            worked.append(w)
        model.add(sum(worked) <= 19)
        # Two successive wholly free calendar days give at least 48 h between
        # paid duties even when surrounding shifts cross midnight. This is a
        # conservative sufficient condition for each rolling seven-day window.
        offpair = []
        for day in range(27):
            z = model.new_bool_var(f"off{day}")
            model.add(z + worked[day] <= 1)
            model.add(z + worked[day + 1] <= 1)
            model.add(z >= 1 - worked[day] - worked[day + 1])
            offpair.append(z)
        for day in range(22):
            model.add(sum(offpair[day:day + 6]) >= 1)
        # Keep exact customer placements first; choose shorter legal duties second.
        model.maximize(sum((10_000 + 100 * (g["end"] - g["start"])) * keep[i] for i, g in own)
                       - sum((t[1] - t[0] - sum(b - a for a, b in t[2])) * x[j] for j, t in eligible))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = seconds
        solver.parameters.num_search_workers = 4
        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(f"No feasible ordinary schedule for staff index {person_index}; status {solver.status_name(status)}")
        selected = [(j, t) for j, t in eligible if solver.value(x[j])]
        for j, t in selected:
            chosen.append((person["id"], t))
        for i, _ in own:
            if solver.value(keep[i]):
                kept.add(i)
    return chosen, kept


def schedule_substitutes(groups, templates, pending, seconds=30):
    """Bounded greedy packing of residual tasks into legal substitute shifts."""
    remaining = set(pending)
    created = []
    while remaining:
        best = None
        for t in templates:
            fitting = sorted((i for i in remaining if covered(t, groups[i]["start"], groups[i]["end"])),
                             key=lambda i: (groups[i]["end"], groups[i]["start"]))
            accepted = []
            last = -1
            for i in fitting:
                if groups[i]["start"] >= last:
                    accepted.append(i)
                    last = groups[i]["end"]
            if not accepted:
                continue
            net = t[1] - t[0] - sum(b - a for a, b in t[2])
            score = len(accepted) * 1000 + sum(groups[i]["end"] - groups[i]["start"] for i in accepted) - net
            if best is None or score > best[0]:
                best = (score, t, accepted)
        if best is None:
            raise RuntimeError("At least one preserved placement has no legal pass template")
        _, t, ids = best
        created.append((t, ids))
        remaining.difference_update(ids)
    return created


def assign_substitute_people(created):
    people = []
    result = []
    for shift, ids in sorted(created, key=lambda x: x[0][0]):
        selected = None
        for idx, history in enumerate(people):
            if history[-1][1] + 660 > shift[0]:
                continue
            all_shifts = history + [shift]
            days = {day for day in range(28) for t in all_shifts if t[0] < (day + 1) * 1440 and t[1] > day * 1440}
            if len(days) > 19:
                continue
            if any(not any(d not in days and d + 1 not in days for d in range(start, start + 6)) for start in range(22)):
                continue
            selected = idx
            break
        if selected is None:
            selected = len(people)
            people.append([])
        people[selected].append(shift)
        result.append((f"VIK-{selected + 1}", shift, ids))
    return result, len(people)


def calculate(old, engine_commit, seconds, night_allowed, external):
    templates = shifts()
    groups = groups_from(old)
    ordinary_staff = [s for s in old["staff"] if s["type"] == "ORDINARY"]
    admin_reqs = [n for n in old["administration_requirements"] if n["period"] == "DECEMBER"]
    admin_person = admin_reqs[0]["required_employee_id"]
    if len(admin_reqs) != 60 or any(n["required_employee_id"] != admin_person for n in admin_reqs):
        raise RuntimeError("Unexpected administration source contract")
    chosen, kept = solve_ordinary(groups, templates, ordinary_staff, seconds, admin_person, night_allowed, external)
    pending = set(range(len(groups))) - kept
    temporary, n_vik = assign_substitute_people(schedule_substitutes(groups, templates, pending))
    duties = []
    assignment_rows = []

    def add_duty(person, shift, ids):
        a, b, breaks, night = shift
        did = f"C-DUTY-{len(duties) + 1:04d}"
        sub = person.startswith("VIK-")
        duties.append({"id": did, "slot": len(duties), "day": a // 1440, "start": a, "end": b,
                       "breaks": breaks, "net_minutes": b - a - sum(y - x for x, y in breaks),
                       "person_id": person, "position_id": None,
                       "staffing_status": "SYNTHETIC_SUBSTITUTE" if sub else "ASSIGNED_ORDINARY_FORECAST",
                       "segment_type": "VAKEN_NATT" if night else "AKTIVT_ARBETE"})
        for i in ids:
            for original in groups[i]["rows"]:
                row = copy.deepcopy(original)
                row.update(duty_id=did, person_id=person, position_id=None,
                           staffing_status="SYNTHETIC_SUBSTITUTE" if sub else "ASSIGNED_ORDINARY_FORECAST")
                assignment_rows.append(row)

    for person, t in chosen:
        ids = [i for i in kept if groups[i]["person"] == person and covered(t, groups[i]["start"], groups[i]["end"])]
        if ids:
            add_duty(person, t, ids)
    for person, t, ids in temporary:
        add_duty(person, t, ids)
    admin_duties = [d for d in duties if d["person_id"] == admin_person]
    occupied = defaultdict(list)
    for a in assignment_rows:
        if a["person_id"] == admin_person:
            occupied[a["duty_id"]].append((a["start"], a["end"]))
    free_admin_slots = []
    for d in admin_duties:
        for start in range(d["start"], d["end"] - 29, 5):
            end = start + 30
            if all(end <= a or start >= b for a, b in occupied[d["id"]]) and all(end <= a or start >= b for a, b in d["breaks"]):
                free_admin_slots.append((start, end, d["id"]))
    used_admin = []
    for req in admin_reqs:
        slot = next(((a, b, did) for a, b, did in free_admin_slots if all(b <= u or a >= v for u, v in used_admin)), None)
        if slot is None:
            raise RuntimeError("No 30-minute administration placement remains inside ordinary duties")
        a, b, did = slot
        used_admin.append((a, b))
        assignment_rows.append({"need_id": req["id"], "slot": len(assignment_rows), "duty_id": did,
                                "start": a, "end": b, "required_employee_id": admin_person, "kind": "ADMIN",
                                "person_id": admin_person, "position_id": None, "staffing_status": "ASSIGNED_ORDINARY_FORECAST"})
    if len(assignment_rows) != 3614 + 60:
        raise RuntimeError("Assignment count changed during rebuild")
    candidate = {k: copy.deepcopy(old[k]) for k in ("schema_version", "business_alias", "business_id", "workspace_id", "time_unit", "units",
                "original_source_segments_145", "shared_meal_groups")}
    candidate.update({"candidate_id": "", "mode": "SINGLE_RECOMPUTED", "review_required": True,
                      "business_schedule_approved": False, "production_ready": False, "engine_commit": engine_commit,
                      "period": {"start": "2026-12-02", "end": "2026-12-29", "timezone": "Europe/Stockholm"},
                      "staff": ordinary_staff + [{"id": f"VIK-{i}", "alias": f"Vikarie {i}", "type": "SYNTHETIC_SUBSTITUTE"} for i in range(1, n_vik + 1)],
                      "needs": [copy.deepcopy(n) for n in old["needs"] if n["period"] == "DECEMBER"],
                      "administration_requirements": [copy.deepcopy(n) for n in old["administration_requirements"] if n["period"] == "DECEMBER"],
                      "duties": sorted(duties, key=lambda d: (d["start"], d["id"])), "assignments": assignment_rows,
                      "engine": {"name": "vintergatan-c", "profile": "v16.29-fixed-need-windows"},
                      "dashboard_basis": {"frame_version": "vg-frame-2026-11-03", "hourly_cost_sek": 293, "night_kind": "VAKEN"}})
    for n in candidate["needs"]:
        if n["id"].startswith("V6-"):
            n["activity"] = "VC:s tillsyn"
            n["source_ref"] = "VC-beslut 2026-11-02; skyddad källa"
    for requirement in candidate["administration_requirements"]:
        requirement["source_ref"] = "VC-beslut 2026-11-02; skyddad källa"
    candidate["shared_meal_groups"] = [g for g in candidate["shared_meal_groups"] if all(i in {n["id"] for n in candidate["needs"]} for i in g["need_ids"])]
    candidate["candidate_id"] = "VG-20261202-" + hashlib.sha256(stable({"duties": candidate["duties"], "assignments": assignment_rows})).hexdigest()[:12]
    result = validate(candidate)
    historical = [dict(id=c["id"], status=c["status"], scope=c.get("scope", "SOURCE"), details="Historiskt källfynd; ingen ny verifiering")
                  for c in old["validation"]["checks"] if c["status"] in ("FAIL", "UNKNOWN")]
    checks = [dict(id=k, status="FAIL" if k in result["failed"] else "PASS", scope="CANDIDATE",
                   violations=result["failed"].get(k, 0)) for k in sorted(set(result["passed"]) | set(result["failed"]))]
    candidate["validation"] = {"scope": "DECEMBER", "validator": "vg_validate_candidate.py", "checks": checks + historical,
                               "summary": dict(Counter(c["status"] for c in checks + historical)), "workload": {
                                   "ordinary_minutes": result["ordinary_minutes"], "temporary_minutes": result["substitute_minutes"],
                                   "model_cost_sek": result["model_cost_sek"]}}
    return candidate, result, {"groups": len(groups), "retained_ordinary_groups": len(kept), "substitute_groups": len(pending), "substitute_people": n_vik}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("warm_start", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--engine-commit", required=True)
    p.add_argument("--seconds-per-person", type=float, default=15)
    p.add_argument("--conditions-workbook", type=Path, required=True)
    p.add_argument("--source-workbook", type=Path, required=True)
    args = p.parse_args()
    source = json.loads(args.warm_start.read_text())
    import openpyxl
    workbook = openpyxl.load_workbook(args.conditions_workbook, read_only=True, data_only=True)
    rows = list(workbook["Villkor"].values)
    allowed_aliases = {str(row[0]) for row in rows[4:] if row and row[0] and str(row[5]).strip() == "JA"}
    night_allowed = {person["id"] for person in source["staff"] if person.get("alias") in allowed_aliases}
    from datetime import datetime
    source_book = openpyxl.load_workbook(args.source_workbook, read_only=True, data_only=True)
    origin = datetime(2026, 12, 2)
    external = defaultdict(list)
    external_sheet = next(source_book[name] for name in source_book.sheetnames if name.startswith("VASTERMALM_"))
    for row in list(external_sheet.values)[1:]:
        try:
            a = int((datetime.fromisoformat(row[5]) - origin).total_seconds() / 60)
            b = int((datetime.fromisoformat(row[6]) - origin).total_seconds() / 60)
        except (TypeError, ValueError):
            continue
        if b > 0 and a < DEC_END:
            external[row[1]].append((a, b))
    candidate, report, stats = calculate(source, args.engine_commit, args.seconds_per_person, night_allowed, external)
    args.output.write_bytes(stable(candidate))
    print(json.dumps({"candidate_id": candidate["candidate_id"], "bytes": args.output.stat().st_size,
                      "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "model": stats,
                      "validator": report}, ensure_ascii=False))
