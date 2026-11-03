"""Fail closed before presenting a Vintergatan candidate as an optimized proposal.

The ordinary rule validator proves feasibility only. This gate additionally binds a
complete Medvind time ledger, a locked reconciliation and a solver objective proof
to the *exact bytes* of the candidate. Source names never enter its output.
"""

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from vg_validate_candidate import validate

ORG = "6d0002a5-c34f-4709-af13-c04f96786e8c"
PERIOD = {"start": "2026-12-02", "end": "2026-12-29", "timezone": "Europe/Stockholm"}
END_MINUTE = 28 * 1440
KINDS = {"ORDINARY": "ordinary", "SYNTHETIC_SUBSTITUTE": "substitute"}
HEX64 = re.compile(r"^[a-f0-9]{64}$")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def interval_minutes(start, end, lo=0, hi=END_MINUTE):
    return max(0, min(end, hi) - max(start, lo))


def candidate_paid_minutes(candidate):
    """Count each person's paid duty time exactly once, clipped to the 28 days."""
    staff = {s["id"]: s["type"] for s in candidate.get("staff", [])}
    totals = {"ordinary": 0, "substitute": 0}
    whole = {"ordinary": 0, "substitute": 0}
    errors = []
    seen = set()
    for duty in candidate.get("duties", []):
        did, pid = duty.get("id"), duty.get("person_id")
        if did in seen or pid not in staff or staff[pid] not in KINDS:
            errors.append("DUTY_ID_OR_STAFF_TYPE")
            continue
        seen.add(did)
        start, end = duty.get("start"), duty.get("end")
        breaks = duty.get("breaks")
        if not isinstance(start, int) or not isinstance(end, int) or end <= start or not isinstance(breaks, list):
            errors.append("DUTY_INTERVAL")
            continue
        if start >= END_MINUTE or end <= 0:
            errors.append("DUTY_OUTSIDE_COMPARISON_PERIOD")
        paid = interval_minutes(start, end)
        full = end - start
        for pair in breaks:
            if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(x, int) for x in pair) or not start <= pair[0] < pair[1] <= end:
                errors.append("BREAK_INTERVAL")
                continue
            paid -= interval_minutes(pair[0], pair[1])
            full -= pair[1] - pair[0]
        if paid < 0 or full != duty.get("net_minutes"):
            errors.append("NET_DUTY_TIME")
        kind = KINDS[staff[pid]]
        totals[kind] += paid
        whole[kind] += full
    return totals, whole, sorted(set(errors))


def _ledger_minutes(ledger):
    """Recompute both raw and period net from individual paid intervals."""
    zone = ZoneInfo("Europe/Stockholm")
    start = datetime(2026, 12, 2, tzinfo=zone)
    end = datetime(2026, 12, 30, tzinfo=zone)
    raw = {"ordinary": 0, "substitute": 0}
    clipped = dict(raw)
    errors = []
    refs = set()
    vacancy_ids = set()
    by_person = {}
    for row in ledger.get("rows", []):
        ref, kind, pid = row.get("source_ref"), row.get("staff_type"), row.get("person_id")
        if not isinstance(ref, str) or not ref or ref in refs or kind not in KINDS or not isinstance(pid, str) or not pid:
            errors.append("MEDVIND_ROW_ID_OR_TYPE")
            continue
        refs.add(ref)
        if row.get("vacancy_id"):
            vacancy_ids.add(row["vacancy_id"])
        intervals = row.get("paid_intervals")
        if not isinstance(intervals, list) or not intervals:
            errors.append("MEDVIND_PAID_INTERVALS_MISSING")
            continue
        for interval in intervals:
            try:
                a = datetime.fromisoformat(interval["start"])
                b = datetime.fromisoformat(interval["end"])
                if a.tzinfo is None or b.tzinfo is None or b <= a or (b-a).total_seconds() % 60:
                    raise ValueError("invalid interval")
                minutes = int((b-a).total_seconds() / 60)
                period_minutes = max(0, int((min(b, end)-max(a, start)).total_seconds() / 60))
            except (KeyError, TypeError, ValueError):
                errors.append("MEDVIND_PAID_INTERVAL_INVALID")
                continue
            key = KINDS[kind]
            by_person.setdefault(pid, []).append((a, b))
            raw[key] += minutes
            clipped[key] += period_minutes
    for intervals in by_person.values():
        intervals.sort()
        if any(b > next_a for (_, b), (next_a, _) in zip(intervals, intervals[1:])):
            errors.append("MEDVIND_PERSON_TIME_OVERLAP")
    return raw, clipped, vacancy_ids, sorted(set(errors))


def check(candidate, candidate_hash, candidate_bytes, manifest, ledger, ledger_hash,
          baseline, baseline_hash, proof, source_report_hash=None, source_workbook_hash=None):
    errors = []
    if candidate.get("period") != PERIOD:
        errors.append("CANDIDATE_ORG_OR_PERIOD")
    if (manifest is None or manifest.get("schema") != "bb-vg-single-manifest/1.0" or
            manifest.get("organization_id") != ORG or manifest.get("period_id") != "2026-12-02..2026-12-29" or
            manifest.get("candidate_id") != candidate.get("candidate_id") or
            manifest.get("sha256") != candidate_hash or manifest.get("bytes") != candidate_bytes or
            manifest.get("engine_commit") != candidate.get("engine_commit")):
        errors.append("MANIFEST_CANDIDATE_BINDING")
    period, full, duty_errors = candidate_paid_minutes(candidate)
    errors.extend(duty_errors)
    rules = validate(candidate)
    if rules["failed"]:
        errors.append("CANDIDATE_RULE_FAIL")
    workload = candidate.get("validation", {}).get("workload", {})
    if workload.get("ordinary_minutes") != period["ordinary"] or workload.get("temporary_minutes") != period["substitute"]:
        errors.append("AFTER_NOT_PERIOD_CLIPPED")
    expected_cost = round(sum(period.values()) * 293 / 60, 2)
    if workload.get("model_cost_sek") != expected_cost:
        errors.append("AFTER_COST_NOT_PERIOD_CLIPPED")
    if ledger is None or baseline is None:
        errors.append("LOCKED_MEDVIND_BASELINE_MISSING")
    else:
        if ledger.get("schema") != "bb-vg-medvind-paid-ledger/1.0" or ledger.get("organization_id") != ORG or ledger.get("period") != PERIOD:
            errors.append("MEDVIND_LEDGER_SCOPE")
        raw, clipped, existing_vacancies, ledger_errors = _ledger_minutes(ledger)
        errors.extend(ledger_errors)
        report_hash = ledger.get("source_report_sha256")
        if (not ledger.get("complete_tv_and_vik_source") or not isinstance(report_hash, str) or
                not HEX64.fullmatch(report_hash) or report_hash != source_report_hash):
            errors.append("MEDVIND_TOTAL_SOURCE_NOT_ATTESTED")
        if baseline.get("schema") != "bb-vg-locked-baseline/1.0" or baseline.get("ledger_sha256") != ledger_hash:
            errors.append("BASELINE_SOURCE_BINDING")
        if baseline.get("source_report_sha256") != source_report_hash:
            errors.append("BASELINE_SOURCE_REPORT_BINDING")
        if (source_workbook_hash is None or
                baseline.get("source_workbook_sha256") != source_workbook_hash or
                manifest is None or manifest.get("input_sha256") != source_workbook_hash):
            errors.append("BASELINE_SOURCE_WORKBOOK_BINDING")
        if baseline.get("organization_id") != ORG or baseline.get("period") != PERIOD:
            errors.append("BASELINE_SCOPE")
        if baseline.get("reported_minutes") != raw or baseline.get("period_clipped_minutes") != clipped:
            errors.append("BASELINE_RECONCILIATION")
        adjusted = dict(clipped)
        seen_vacancies = set()
        for row in baseline.get("vacancy_complements", []):
            vacancy = row.get("vacancy_id")
            minutes = row.get("minutes")
            if (not vacancy or vacancy in seen_vacancies or vacancy in existing_vacancies or
                    row.get("already_in_medvind") is not False or not row.get("evidence_sha256") or
                    not isinstance(minutes, int) or minutes < 0):
                errors.append("VACANCY_COMPLEMENT_UNVERIFIED_OR_DUPLICATE")
                continue
            seen_vacancies.add(vacancy)
            adjusted["substitute"] += minutes
        if baseline.get("comparison_minutes") != adjusted:
            errors.append("BASELINE_COMPARISON_TOTAL")
    if proof is None:
        errors.append("JOINT_OPTIMIZATION_PROOF_MISSING")
    else:
        if (proof.get("schema") != "bb-vg-optimization-proof/1.0" or
                proof.get("candidate_sha256") != candidate_hash or
                proof.get("baseline_sha256") != baseline_hash or
                proof.get("objective") != "MIN_SUBSTITUTE_NET_MINUTES" or
                proof.get("model_scope") != "JOINT_STAFF_SHIFTS_AND_NEEDS" or
                proof.get("status") not in ("OPTIMAL", "FEASIBLE_WITH_BOUND") or
                not proof.get("model_sha256") or not proof.get("solver_log_sha256") or
                proof.get("achieved_substitute_minutes") != period["substitute"] or
                not isinstance(proof.get("lower_bound_minutes"), int) or
                proof["lower_bound_minutes"] < 0 or
                proof["lower_bound_minutes"] > period["substitute"]):
            errors.append("OPTIMIZATION_PROOF_INVALID")
    return {"status": "BLOCKED" if errors else "READY_FOR_REVIEW", "errors": sorted(set(errors)),
            "after_period_minutes": period, "after_whole_duty_minutes": full,
            "after_period_cost_sek": expected_cost, "candidate_sha256": candidate_hash,
            "primary_objective_bound_minutes": proof.get("lower_bound_minutes") if proof else None,
            "primary_objective_gap_minutes": period["substitute"] - proof["lower_bound_minutes"]
            if proof and isinstance(proof.get("lower_bound_minutes"), int) else None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("candidate", type=Path)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--medvind-ledger", type=Path)
    p.add_argument("--source-report", type=Path)
    p.add_argument("--source-workbook", type=Path)
    p.add_argument("--baseline", type=Path)
    p.add_argument("--optimization-proof", type=Path)
    args = p.parse_args()
    candidate = json.loads(args.candidate.read_text())
    manifest = json.loads(args.manifest.read_text()) if args.manifest else None
    ledger = json.loads(args.medvind_ledger.read_text()) if args.medvind_ledger else None
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    proof = json.loads(args.optimization_proof.read_text()) if args.optimization_proof else None
    result = check(candidate, sha256(args.candidate), args.candidate.stat().st_size, manifest, ledger,
                   sha256(args.medvind_ledger) if args.medvind_ledger else None,
                   baseline, sha256(args.baseline) if args.baseline else None, proof,
                   sha256(args.source_report) if args.source_report else None,
                   sha256(args.source_workbook) if args.source_workbook else None)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(result["status"] != "READY_FOR_REVIEW")


if __name__ == "__main__":
    main()
