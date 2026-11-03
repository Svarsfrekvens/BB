"""Audit all Vintergatan Medvind rows without exposing source names or IDs.

This reports source totals and a transparent *provisional* vacancy complement.
It never marks a comparable before basis locked when paid break placement or a
complete Medvind category total is not independently evidenced.
"""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import openpyxl

START = datetime(2026, 12, 2, tzinfo=ZoneInfo("Europe/Stockholm"))
END = datetime(2026, 12, 30, tzinfo=ZoneInfo("Europe/Stockholm"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def d(value):
    return Decimal(str(value))


def audit(medvind, workbook):
    raw = list(openpyxl.load_workbook(medvind, read_only=True, data_only=True)["Medvind"].values)
    w = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    rows = list(w["SCHEMA_DEC"].values)
    columns = {name: i for i, name in enumerate(rows[0])}
    people = list(w["PERSONAL"].values)
    pc = {name: i for i, name in enumerate(people[0])}
    employment = {r[pc["person_id"]]: r[pc["anstallning"]] for r in people[1:] if r[pc["person_id"]]}
    problems = Counter()
    category = Counter()
    raw_sum = Decimal(0)
    period_sum = Decimal(0)
    unique_people = set()
    seen_source_rows = set()
    long_without_reported_break = 0
    boundary_rows = 0
    boundary_paid_unknown = 0
    for row in rows[1:]:
        source_no = row[columns["source_excel_row"]]
        pid = row[columns["person_id"]]
        if not isinstance(source_no, int) or source_no < 2 or source_no > len(raw) or source_no in seen_source_rows:
            problems["SOURCE_ROW_BINDING"] += 1
            continue
        seen_source_rows.add(source_no)
        hours = d(row[columns["netto_timmar"]])
        if hours != d(raw[source_no - 1][9]):
            problems["SOURCE_SUMMA_MISMATCH"] += 1
        kind = employment.get(pid)
        if kind == "Tillsvidareanställd":
            category["ordinary_rows"] += 1
        elif kind == "Vikarie (historiskt identifierad)":
            category["substitute_rows"] += 1
        else:
            problems["UNKNOWN_STAFF_TYPE"] += 1
        unique_people.add(pid)
        a = datetime.fromisoformat(row[columns["start_lokal"]])
        b = datetime.fromisoformat(row[columns["slut_lokal"]])
        if a.tzinfo is None:
            a = a.replace(tzinfo=START.tzinfo)
        if b.tzinfo is None:
            b = b.replace(tzinfo=START.tzinfo)
        if b <= a or a >= END or b <= START:
            problems["SOURCE_TIME_OR_PERIOD"] += 1
            continue
        raw_sum += hours
        gross = d(row[columns["brutto_minuter"]])
        deducted = gross - hours * 60
        if gross > 300 and deducted < d("29.5"):
            long_without_reported_break += 1
        if a >= START and b <= END:
            period_sum += hours
        else:
            boundary_rows += 1
            if abs(deducted) <= d("0.5"):
                seconds = d((min(b, END) - max(a, START)).total_seconds())
                period_sum += seconds / 3600
            else:
                boundary_paid_unknown += 1
    if len(seen_source_rows) != len(raw) - 1 or len(rows) != len(raw):
        problems["SOURCE_ROW_COVERAGE"] += 1
    vacancy = d("0.6537") * 148 + d("6.5")
    return {
        "status": "SOURCE_RECONCILED_COMPARISON_NOT_LOCKED" if not problems else "SOURCE_RECONCILIATION_FAILED",
        "medvind_source_sha256": digest(medvind),
        "transformed_workbook_sha256": digest(workbook),
        "source_sheet_and_cells": f"Medvind!A2:J{len(raw)}",
        "transformed_sheet_and_cells": f"SCHEMA_DEC!A2:N{len(rows)}",
        "period": "2026-12-02..2026-12-29",
        "source_rows": len(raw) - 1,
        "bound_rows": len(seen_source_rows),
        "unique_staff": len(unique_people),
        "rows_by_type": dict(category),
        "medvind_reported_row_sum_hours": str(raw_sum),
        "medvind_period_clipped_as_reported_hours": str(period_sum),
        "boundary_rows": boundary_rows,
        "boundary_paid_location_unknown_rows": boundary_paid_unknown,
        "long_rows_without_30min_reported_deduction": long_without_reported_break,
        "booked_substitute_hours_in_this_extract": "0",
        "booked_substitute_total_is_complete": False,
        "vacancy_complement_assumption_hours": str(vacancy),
        "vacancy_complement_basis": "65.37% x 148h + 6.5h; untimed assumption, not Medvind booked time",
        "source_problems": dict(problems),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("medvind", type=Path)
    p.add_argument("workbook", type=Path)
    args = p.parse_args()
    print(json.dumps(audit(args.medvind, args.workbook), ensure_ascii=False, sort_keys=True))
