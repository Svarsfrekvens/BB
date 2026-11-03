"""Independent, privacy-safe structural validator for a Vintergatan C proposal.

Inputs stay local. Output contains aggregate rule counts only, never source rows.
This is a candidate validator; unknown historical boundary/skill facts remain unknown.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

SOURCE_SHA = "ea7e653895c17b8a2328853125dc47094e229725e91bb5eae7f0568c93b0aad8"
ORIGINAL_SHA = "fd682cf2bfba4d81904d382c3115b12a0dc390da925388a5ca6f14efa7d2952f"
DEC_END = 28 * 1440


def stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def validate(candidate):
    problems = Counter()

    def check(rule, ok):
        if not ok:
            problems[rule] += 1

    needs = [n for n in candidate.get("needs", []) if n.get("period") == "DECEMBER"]
    need_by_id = {n.get("id"): n for n in needs}
    duties = [d for d in candidate.get("duties", []) if d.get("start", DEC_END) < DEC_END]
    duty_by_id = {d.get("id"): d for d in duties}
    admin = {n.get("id"): n for n in candidate.get("administration_requirements", []) if n.get("period") == "DECEMBER"}
    assignments = [a for a in candidate.get("assignments", []) if a.get("need_id") in need_by_id or a.get("need_id") in admin]
    originals = candidate.get("original_source_segments_145", [])
    shared_pairs = set()
    for group in candidate.get("shared_meal_groups", []):
        ids = group.get("need_ids", [])
        shared_pairs.update((a, b) for a in ids for b in ids if a != b)
    check("NATIVE_FORMAT", candidate.get("schema_version") == "bb-vintergatan-forecast-package/2")
    check("PERIOD_AND_NEED_COUNT", len(needs) == len(need_by_id) == 3286 and sum(n.get("count", 0) for n in needs) == 3614)
    check("ORIGINAL_145_HASH", len(originals) == 145 and hashlib.sha256(stable(originals)).hexdigest() == ORIGINAL_SHA)
    check("NO_SLEEPING_JOUR", all(d.get("segment_type") != "SOVANDE_JOUR" for d in duties))

    by_need = defaultdict(list)
    by_duty = defaultdict(list)
    for a in assignments:
        by_need[a.get("need_id")].append(a)
        by_duty[a.get("duty_id")].append(a)

    for n in needs:
        rows = by_need[n["id"]]
        check("NEED_STAFF_COUNT", len(rows) == n.get("count"))
        check("NEED_WINDOW", isinstance(n.get("earliest"), int) and isinstance(n.get("latest_end"), int)
              and n["earliest"] < n["latest_end"] and n.get("duration", 0) > 0
              and n["earliest"] + n["duration"] <= n["latest_end"])
        if len(rows) > 1:
            check("DISTINCT_STAFF_PER_NEED", len({a.get("person_id") or a.get("position_id") for a in rows}) == len(rows))
        for a in rows:
            check("ASSIGNMENT_DURATION", (a.get("end", 0) - a.get("start", 0)) * 60 == n.get("duration"))
            check("ASSIGNMENT_WINDOW", a.get("start", -1) * 60 >= n.get("earliest", 0)
                  and a.get("end", 0) * 60 <= n.get("latest_end", -1))

    for n in admin.values():
        rows = by_need[n["id"]]
        check("ADMIN_STAFF_COUNT", len(rows) == n.get("count"))
        for a in rows:
            check("ADMIN_PERSON", a.get("person_id") == n.get("required_employee_id"))
            check("ADMIN_DURATION", (a.get("end", 0) - a.get("start", 0)) * 60 == n.get("duration"))
    check("ADMIN_30H", sum(n.get("duration", 0) * n.get("count", 0) for n in admin.values()) == 30 * 3600)

    by_person = defaultdict(list)
    for d in duties:
        start, end = d.get("start"), d.get("end")
        if not isinstance(start, int) or not isinstance(end, int) or end <= start:
            problems["DUTY_TIME"] += 1
            continue
        check("FIVE_MINUTE_BOUNDARIES", start % 5 == end % 5 == 0)
        check("DUTY_LENGTH_4_TO_13_H", 240 <= end - start <= 780)
        if d.get("segment_type") != "VAKEN_NATT":
            check("DAY_EVENING_WINDOW", start // 1440 == end // 1440
                  and start % 1440 >= 390 and end % 1440 <= 1320)
        breaks = d.get("breaks", [])
        check("UNPAID_BREAK_FOR_LONG_DUTY", end - start <= 300 or sum(b[1] - b[0] for b in breaks) >= 30)
        last = start
        for b in sorted(breaks):
            check("BREAK_INTERVAL", len(b) == 2 and last <= b[0] < b[1] <= end)
            check("MAX_FIVE_HOURS_ACTIVE", b[0] - last <= 300)
            last = b[1]
        check("MAX_FIVE_HOURS_ACTIVE", end - last <= 300)
        check("NET_TIME", d.get("net_minutes") == end - start - sum(b[1] - b[0] for b in breaks))
        pid = d.get("person_id")
        check("PERSON_OR_POSITION", (pid is None) != (d.get("position_id") is None))
        if pid is not None:
            by_person[pid].append(d)
        for a in by_duty[d["id"]]:
            check("ASSIGNMENT_DUTY_LINK", a.get("person_id") == pid and a.get("position_id") == d.get("position_id")
                  and start <= a.get("start", -1) < a.get("end", -1) <= end)
            check("NO_WORK_DURING_BREAK", all(a["end"] <= b[0] or a["start"] >= b[1] for b in breaks))
        events = by_duty[d["id"]]
        for i, a in enumerate(events):
            for b in events[i + 1:]:
                if max(a["start"], b["start"]) < min(a["end"], b["end"]):
                    check("NO_TASK_OVERLAP_WITHIN_DUTY", (a["need_id"], b["need_id"]) in shared_pairs)

    for shifts in by_person.values():
        shifts.sort(key=lambda d: d["start"])
        for prev, nxt in zip(shifts, shifts[1:]):
            check("ELEVEN_HOURS_REST", nxt["start"] - prev["end"] >= 660)
        worked = {day for day in range(28) for d in shifts if d["start"] < (day + 1) * 1440 and d["end"] > day * 1440}
        check("NINE_FREE_DAYS", 28 - len(worked) >= 9)
        for day in range(22):
            lo, hi = day * 1440, (day + 7) * 1440
            busy = [(max(lo, d["start"]), min(hi, d["end"])) for d in shifts if d["end"] > lo and d["start"] < hi]
            last = lo
            gaps = []
            for a, b in busy:
                gaps.append(a - last)
                last = max(last, b)
            gaps.append(hi - last)
            check("ROLLING_36H_REST", max(gaps) >= 2160)

    staff = {s.get("id"): s for s in candidate.get("staff", [])}
    for pid, shifts in by_person.items():
        s = staff.get(pid)
        check("STAFF_ID", s is not None)
        if s and s.get("type") != "SYNTHETIC_SUBSTITUTE" and s.get("contract_seconds") is not None:
            check("SSG_PERIOD_CAP", sum(d.get("net_minutes", 0) * 60 for d in shifts) <= float(s["contract_seconds"]) + 0.01)
    for day in range(28):
        for minute in range(day * 1440 + 1320, (day + 1) * 1440 + 390, 5):
            check("AWAKE_NIGHT_COVERAGE", any(d.get("segment_type") == "VAKEN_NATT"
                  and d["start"] <= minute < d["end"]
                  and all(not (a <= minute < b) for a, b in d["breaks"]) for d in duties))
    for a in assignments:
        check("ALL_ASSIGNMENTS_HAVE_DUTY", a.get("duty_id") in duty_by_id)

    tv = sum(d.get("net_minutes", 0) for d in duties if staff.get(d.get("person_id"), {}).get("type") != "SYNTHETIC_SUBSTITUTE" and d.get("person_id"))
    vik = sum(d.get("net_minutes", 0) for d in duties if staff.get(d.get("person_id"), {}).get("type") == "SYNTHETIC_SUBSTITUTE")
    return {"passed": sorted(set(["NATIVE_FORMAT", "PERIOD_AND_NEED_COUNT", "ORIGINAL_145_HASH", "NO_SLEEPING_JOUR",
                            "NEED_STAFF_COUNT", "NEED_WINDOW", "DISTINCT_STAFF_PER_NEED", "ASSIGNMENT_DURATION", "ASSIGNMENT_WINDOW",
                            "ADMIN_STAFF_COUNT", "ADMIN_PERSON", "ADMIN_DURATION", "ADMIN_30H", "FIVE_MINUTE_BOUNDARIES",
                            "DUTY_LENGTH_4_TO_13_H", "DAY_EVENING_WINDOW", "UNPAID_BREAK_FOR_LONG_DUTY", "BREAK_INTERVAL",
                            "MAX_FIVE_HOURS_ACTIVE", "NET_TIME", "PERSON_OR_POSITION", "ASSIGNMENT_DUTY_LINK", "NO_WORK_DURING_BREAK",
                            "NO_TASK_OVERLAP_WITHIN_DUTY", "ELEVEN_HOURS_REST", "NINE_FREE_DAYS", "ROLLING_36H_REST",
                            "STAFF_ID", "SSG_PERIOD_CAP", "AWAKE_NIGHT_COVERAGE", "ALL_ASSIGNMENTS_HAVE_DUTY"]) - set(problems)),
            "failed": dict(sorted(problems.items())), "ordinary_minutes": tv, "substitute_minutes": vik,
            "model_cost_sek": round((tv + vik) * 293 / 60, 2), "needs": len(needs), "duties": len(duties)}


def source_projection(candidate, workbook):
    """Bind retained forecast IDs; name no omitted private row in the report."""
    import openpyxl

    sheet = openpyxl.load_workbook(workbook, read_only=True, data_only=True)["DEC_BEHOV_UTKAST"]
    rows = iter(sheet.values)
    headers = next(rows)
    source = {r[0]: dict(zip(headers, r)) for r in rows if r[0]}
    forecast = {n["id"] for n in candidate.get("needs", []) if n.get("period") == "DECEMBER" and n["id"].startswith("AX-")}
    omitted = [source[k] for k in source.keys() - forecast]
    reasons = Counter(r["insats"] for r in omitted)
    expected = reasons == Counter({"Tillsyn": 109, "Rörelselarm": 6})
    return {"status": "PASS" if expected and not forecast.difference(source) else "FAIL",
            "source_forecast_ids": len(source), "retained_ax_ids": len(forecast),
            "superseded_historical_supervision": reasons.get("Tillsyn", 0),
            "nonfixed_alarm_rows": reasons.get("Rörelselarm", 0),
            "unexpected_omissions": len(omitted) - reasons.get("Tillsyn", 0) - reasons.get("Rörelselarm", 0),
            "unbound_candidate_ids": len(forecast.difference(source))}


def name_free(candidate, workbook):
    import openpyxl
    import re

    book = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    names = {str(row[1]).strip() for row in list(book["PERSONAL"].values)[1:] if row[1]}
    names.update(str(row[4]).strip() for row in list(book["KUNDER"].values)[1:] if row[4])
    patterns = [re.compile(r"(?i)(?<!\w)" + re.escape(n) + r"(?!\w)") for n in names if len(n) > 2]
    hits = 0

    def walk(value):
        nonlocal hits
        if isinstance(value, dict):
            for key, child in value.items():
                hits += any(p.search(key) for p in patterns)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str):
            hits += any(p.search(value) for p in patterns)

    walk(candidate)
    hits += sum(n.get("source_ref") != "VC-beslut 2026-11-02; skyddad källa"
                for n in candidate.get("administration_requirements", []) if n.get("period") == "DECEMBER")
    return {"status": "PASS" if hits == 0 else "FAIL", "private_name_matches": hits}


def night_eligibility(candidate, workbook):
    import openpyxl

    sheet = openpyxl.load_workbook(workbook, read_only=True, data_only=True)["Villkor"]
    rows = list(sheet.values)
    explicit = {str(r[0]) for r in rows[4:] if r and r[0] and str(r[5]).strip() == "JA"}
    staff = {s["id"]: s for s in candidate.get("staff", [])}
    ordinary_nights = [d for d in candidate.get("duties", []) if d.get("segment_type") == "VAKEN_NATT"
                       and staff.get(d.get("person_id"), {}).get("type") != "SYNTHETIC_SUBSTITUTE"]
    not_confirmed = sum(staff.get(d.get("person_id"), {}).get("alias") not in explicit for d in ordinary_nights)
    return {"status": "PASS" if not_confirmed == 0 else "FAIL", "ordinary_night_duties": len(ordinary_nights),
            "without_explicit_night_permission": not_confirmed}


def external_work_rest(candidate, workbook):
    import openpyxl
    from datetime import datetime

    book = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    sheet = next(book[name] for name in book.sheetnames if name.startswith("VASTERMALM_"))
    origin = datetime(2026, 12, 2)
    external = defaultdict(list)
    external_net = defaultdict(float)
    for row in list(sheet.values)[1:]:
        try:
            a = int((datetime.fromisoformat(row[5]) - origin).total_seconds() / 60)
            b = int((datetime.fromisoformat(row[6]) - origin).total_seconds() / 60)
        except (TypeError, ValueError):
            continue
        if b > 0 and a < DEC_END:
            external[row[1]].append((a, b))
            if isinstance(row[7], (int, float)):
                external_net[row[1]] += float(row[7])
    violations = 0
    weekly_violations = 0
    for pid, spans in external.items():
        own = [(d["start"], d["end"]) for d in candidate.get("duties", []) if d.get("person_id") == pid]
        for a, b in own:
            violations += sum(not (b + 660 <= u or v + 660 <= a) for u, v in spans)
        combined = sorted(own + spans)
        for day in range(22):
            lo, hi = day * 1440, (day + 7) * 1440
            busy = [(max(lo, a), min(hi, b)) for a, b in combined if b > lo and a < hi]
            last, best = lo, 0
            for a, b in busy:
                best = max(best, a - last)
                last = max(last, b)
            best = max(best, hi - last)
            weekly_violations += best < 2160
    personnel = {row[3]: row for row in list(book["PERSONAL"].values)[1:] if row[3]}
    cap_excess = 0
    for pid in external:
        person = personnel.get(pid)
        if person and isinstance(person[6], (int, float)) and isinstance(person[8], (int, float)):
            own_hours = sum(d.get("net_minutes", 0) / 60 for d in candidate.get("duties", []) if d.get("person_id") == pid)
            cap_excess += own_hours + external_net[pid] > float(person[8]) * float(person[6]) / 100 + 0.001
    return {"status": "PASS" if violations == weekly_violations == cap_excess == 0 else "FAIL",
            "external_source_intervals": sum(map(len, external.values())),
            "combined_rest_or_overlap_violations": violations, "combined_rolling_36h_violations": weekly_violations,
            "combined_contract_cap_violations": cap_excess}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("candidate", type=Path)
    p.add_argument("--source-workbook", type=Path)
    p.add_argument("--conditions-workbook", type=Path)
    args = p.parse_args()
    candidate = json.loads(args.candidate.read_text())
    report = validate(candidate)
    if args.source_workbook:
        report["source_projection"] = source_projection(candidate, args.source_workbook)
        report["external_work_rest"] = external_work_rest(candidate, args.source_workbook)
        report["name_free"] = name_free(candidate, args.source_workbook)
    if args.conditions_workbook:
        report["night_eligibility"] = night_eligibility(candidate, args.conditions_workbook)
    print(json.dumps(report, ensure_ascii=False, indent=2))
