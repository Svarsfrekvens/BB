"""Import an uploaded browser contract using a separately configured input profile.

Profiles contain reviewed input decisions, never a schedule, solution or warm
start. This module deliberately has no IO or solver dependency. Unknown or
changed business constraints fail explicitly rather than inheriting a result
from an older workbook.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
from math import isfinite
import re
from typing import Any
from zoneinfo import ZoneInfo
from . import need_windows


class FloraImportError(ValueError):
    def __init__(self, message: str, issues: list[dict] | None = None):
        super().__init__(message)
        self.issues = issues or [{"code": "INPUT_REVIEW_REQUIRED", "message": message}]


def _fail(message: str) -> None:
    raise FloraImportError(message)


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode()).hexdigest()


def _index(rows: Any, key: str, label: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        _fail(f"{label}: listan saknas.")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(key), str) or not row[key]:
            _fail(f"{label}: varje rad måste ha ett stabilt {key}.")
        if row[key] in result:
            _fail(f"{label}: dubblerat ID {row[key]}.")
        result[row[key]] = row
    return result


def _integer(value: Any, label: str, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        _fail(f"{label}: ett känt helt antal minuter krävs.")
    result = int(value)
    if minimum is not None and result < minimum:
        _fail(f"{label}: värdet måste vara minst {minimum}.")
    return result


def _time(value: Any, timezone: str) -> datetime:
    if not isinstance(value, str):
        _fail("Datum eller klockslag saknas; okänd tid får inte bli noll.")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(ZoneInfo(timezone)).replace(tzinfo=None)
        if dt.second or dt.microsecond:
            _fail(f"Tiden {value} måste anges med hela minuter.")
        return dt
    except (ValueError, TypeError, KeyError):
        _fail(f"Ogiltigt datum eller klockslag: {value}.")


def _match(row: dict, expected: dict, label: str) -> None:
    for key, value in expected.items():
        if row.get(key) != value:
            _fail(f"{label}: {key} har ändrats eller saknas. Profilens tidigare beslut "
                  "kan inte överföras utan en uttrycklig uppdatering av denna uppgift.")


def _workspace(scenario: dict, raw: dict, profile: dict) -> None:
    """Accept source-equal drafts/default UI state, reject unmodelled decisions."""
    if not isinstance(scenario, dict):
        _fail("Scenarioinställningarna måste vara ett objekt.")
    unknown = set(scenario)-{"workspace","drafts","absence_mode"}
    if unknown:
        _fail("Scenarioinställningar utan motorstöd: "+", ".join(sorted(unknown))+".")
    workspace = scenario.get("workspace") or {}
    if not isinstance(workspace, dict):
        _fail("workspace måste vara ett objekt.")
    unknown = set(workspace)-{"unit_rules","competence","people","activities","contacts","drafts","templates","finance"}
    if unknown:
        _fail("Arbetskopian har inställningar utan motorstöd: "+", ".join(sorted(unknown))+".")
    if workspace.get("templates"):
        _fail("Nya passmallar behöver mappas till kandidatregler före körning; de ignoreras inte.")
    people = {r["person_id"]: r for r in raw.get("staff", [])}
    draft_map = {
        "ssg_pct": "ssg_pct", "fulltime_hours_28d": "fulltime_hours_28d",
        "sleeping_oncall_allowed": "sleeping_oncall_allowed",
        "awake_night_allowed": "awake_night_allowed",
        "competence_delegation": "individual_delegations",
        "hard_conditions": "hard_individual_condition", "soft_preferences": "soft_preference",
    }
    for pid, draft in (scenario.get("drafts") or workspace.get("drafts") or {}).items():
        if pid not in people or not isinstance(draft, dict):
            _fail(f"Personutkastet {pid} saknar en verifierad personkoppling.")
        for key, field in draft.items():
            if key == "reviewed_by_vc":
                continue
            if not isinstance(field, dict) or "value" not in field:
                _fail(f"Personutkast {pid}: {key} saknar tydligt värde och källa.")
            expected = people[pid].get(draft_map[key]) if key in draft_map else None
            if field["value"] != expected:
                _fail(f"Personutkast {pid}: ändringen av {key} behöver motorstöd/profilbeslut "
                      "innan körning. Uppgiften ignoreras inte.")
    rules = workspace.get("unit_rules") or {}
    if not isinstance(rules, dict):
        _fail("Verksamhetens regelinställningar måste vara ett objekt.")
    freeday = rules.get("freeday")
    if freeday and freeday.get("mode") != "rullande":
        _fail("Arbetskopians fridagsregel avviker från beslutad rullande tillämpning.")
    # Contract form is retained for accounting, but never substitutes for the
    # explicitly preserved ordinary work target in this scenario.
    competence = workspace.get("competence") or {}
    if competence.get("codes") or any(competence.get("persons", {}).values()):
        _fail("Arbetskopian har nya kompetensbeslut. Dessa måste mappas innan denna profil kan köras.")
    for pid, person in (workspace.get("people") or {}).items():
        if (person.get("availability") or person.get("absences") or
                person.get("admin_hours_per_week") not in (None, 0)):
            _fail(f"{pid}: nya tillgänglighets-/frånvaro-/stödtidsuppgifter behöver "
                  "tidsatt mappning före körning; de får inte ignoreras.")
    for activity in workspace.get("activities") or []:
        if activity.get("on") or activity.get("slots"):
            _fail(f"Aktiviteten {activity.get('name', activity.get('id'))} är aktiverad. "
                  "Den behöver importeras och kontrolleras före körning.")
    for customer, contact in (workspace.get("contacts") or {}).items():
        if contact.get("kp") or contact.get("vice") or contact.get("check") or contact.get("minutes") is not None:
            _fail(f"{customer}: nya kontaktpersonsbeslut behöver motorstöd före körning.")


def _day_boundary_parameters(scenario: dict, periods: dict[str, dict],
                             person_ids: set[str], period_id: str, timezone: str) -> dict:
    """Record fixed individual boundaries for the separate result-level check.

    Omitted boundaries remain unknown. Dates and timezone belong to the verified
    uploaded periods; a scenario cannot introduce a floating or daily boundary.
    """
    rules = (scenario.get("workspace") or {}).get("unit_rules") or {}
    values = rules.get("day_boundaries", {})
    if not isinstance(values, dict):
        _fail("Dygnsbryt ska anges som ett objekt med kända period- och person-ID.")
    records = []
    for key, persons in values.items():
        if key not in periods:
            _fail(f"Dygnsbrytet avser okänd period {key}; datum får inte gissas.")
        if not isinstance(persons, dict):
            _fail(f"Dygnsbryt {key}: personkopplingarna måste vara ett objekt.")
        for person_id, value in persons.items():
            label = f"Dygnsbryt {key}/{person_id}"
            if person_id not in person_ids:
                _fail(f"{label}: personen saknar en verifierad personkoppling.")
            if not isinstance(value, dict) or set(value) != {"time", "confirmed_at", "source"}:
                _fail(f"{label}: ange endast time, confirmed_at och source för ett fast dygnsbryt.")
            clock = value["time"]
            if not isinstance(clock, str) or re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", clock) is None:
                _fail(f"{label}: tiden ska anges som HH:MM mellan 00:00 och 23:59.")
            confirmed = value["confirmed_at"]
            if not isinstance(confirmed, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", confirmed) is None:
                _fail(f"{label}: bekräftelsedatum ska anges som ÅÅÅÅ-MM-DD.")
            try:
                date.fromisoformat(confirmed)
            except ValueError:
                _fail(f"{label}: bekräftelsedatumet finns inte i kalendern.")
            source = value["source"]
            if not isinstance(source, str) or not source.strip():
                _fail(f"{label}: en uttrycklig källa krävs.")
            records.append(dict(period_id=key, person_id=person_id, time=clock,
                                minute_of_day=int(clock[:2])*60+int(clock[3:]),
                                confirmed_at=confirmed, source=source,
                                period_start=periods[key]["start"], period_end=periods[key]["end"],
                                timezone=timezone))
    order = {key: index for index, key in enumerate(periods)}
    records.sort(key=lambda row: (order[row["period_id"]], row["person_id"]))
    known = {row["person_id"] for row in records if row["period_id"] == period_id}
    missing = sorted(person_ids-known)
    return dict(mode="FIXED_PER_PERSON_AND_PERIOD", period_id=period_id, timezone=timezone,
                boundaries=records, missing_person_ids=missing,
                status="MISSING_BOUNDARIES" if missing else "BOUNDARIES_RECORDED_PENDING_RESULT_CHECK",
                validation_status="UNKNOWN")


def _economic_parameters(scenario: dict, person_ids: set[str]) -> dict:
    """Project explicit UI kr/h rates; never infer a rate from model hours."""
    workspace = scenario.get("workspace") or {}
    finance = workspace.get("finance") or {}
    if not isinstance(finance, dict):
        _fail("Ekonomiska parametrar måste vara ett objekt med uttrycklig timkostnad.")
    if set(finance)-{"values"}:
        _fail("Ekonomiska parametrar utan beräkningsstöd: "+
              ", ".join(sorted(set(finance)-{"values"}))+". Endast timkostnad används i denna kostnadsjämförelse.")
    values = finance.get("values") or {}
    if not isinstance(values, dict) or set(values)-{"hourly_cost"}:
        _fail("Endast finance.values.hourly_cost stöds i kostnadsjämförelsen. "
              "Andra ekonomi-/bemanningsantaganden får inte ignoreras.")
    def rate(value: Any, field: str) -> int | float | None:
        if value is None:
            return None
        if type(value) not in (int,float) or not isfinite(value) or value<0:
            _fail(f"{field}: timkostnaden måste vara ett ändligt tal ≥ 0 kr/h; tomt är okänt.")
        return value
    global_rate = rate(values.get("hourly_cost"),"finance.values.hourly_cost")
    individuals = workspace.get("people") or {}
    if not isinstance(individuals, dict):
        _fail("Personernas ekonomiparametrar måste vara kopplade till person-ID.")
    for pid, row in individuals.items():
        if pid not in person_ids:
            _fail(f"Timkostnaden avser okänd person {pid}; den får inte kopplas automatiskt.")
        if not isinstance(row, dict):
            _fail(f"{pid}: personuppgifterna har fel format.")
    parameters = {}
    for pid in sorted(person_ids):
        individual_rate = rate(individuals.get(pid,{}).get("hourly_cost"),f"people.{pid}.hourly_cost")
        if individual_rate is not None:
            value = individual_rate
            source = f"BB arbetskopia: settings.people.{pid}.hourly_cost (kr/h)"
        elif global_rate is not None:
            value = global_rate
            source = "BB arbetskopia: settings.finance.values.hourly_cost (kr/h), globalt uttryckligt antagande"
        else:
            continue
        parameters[pid] = dict(value=value,source=source,currency="SEK")
    return dict(hourly_cost_by_person=parameters,
                calculation_scope="TEMPORARY_PAID_NET_AR_ONLY",
                source="Uttryckliga kr/h-parametrar från BB-arbetskopian; ingen standardkostnad",
                missing_person_ids=sorted(person_ids-set(parameters)))


def _verified_source_basis(raw: dict, profile: dict) -> dict | None:
    """Certify only an exact server-pinned upload, never a mutable workspace.

    Legacy semantic profiles may accept changed source times/durations. Their
    name and workbook checksum alone cannot establish this stronger claim.
    The pin uses the shared source_identity projection, including explicit null
    for absent legacy metadata. Routing is checked separately against the server
    profile. integration.input_sha256 still binds the complete received snapshot.
    """
    expected = profile.get("source_identity")
    expected_file = profile.get("source_file_sha256")
    if expected is None and expected_file is None:
        return None
    from .availability_import import source_identity
    from re import fullmatch
    valid_hash = lambda value: isinstance(value, str) and fullmatch(r"[a-f0-9]{64}", value) is not None
    if not valid_hash(expected) or source_identity(raw) != expected:
        _fail("Underlaget matchar inte serverprofilens exakt granskade indataversion.")
    metadata = raw.get("metadata") or {}
    if any(metadata.get(k) != profile.get(k) or not profile.get(k) for k in ('business_id','data_use')):
        _fail("Underlagets verksamhet eller användning matchar inte serverprofilens källbevis.")
    file_hash = metadata.get("source_file_sha256")
    if not valid_hash(file_hash) or not valid_hash(expected_file) or file_hash != expected_file:
        _fail("Originalfilens SHA-256 saknas eller matchar inte serverprofilens källbevis.")
    return dict(kind="VERIFIED_UPLOADED_ORIGINAL", verification="EXACT_SERVER_REVIEWED_INPUT",
                source_identity=expected, source_file_sha256=file_hash,
                segments=[dict(segment_id=r["segment_id"], person_id=r.get("person_id"),
                               start=r["start"], end=r["end"], code=r["source_code"])
                          for r in raw["schedule_segments"]])


def prepare_case(raw_input: dict, profile: dict, scenario: dict | None = None) -> dict:
    """Build a runnable case from *this upload*, with explicit decision provenance.

    Ordinary targets, candidate availability and reviewed semantic decisions
    come from the profile. All actual source intervals, durations, people,
    source text and customer identities come from the uploaded contract.
    """
    if not isinstance(raw_input, dict) or not isinstance(profile, dict):
        _fail("Både uppladdat underlag och en beslutad indataprofil krävs.")
    if profile.get("schema_version") != "bb-analysis-input-profile/1.0":
        _fail("Backend saknar en kompatibel indataprofil.")
    if any(k in profile for k in ("solution", "search_hint", "warm_start", "assignments", "placements")):
        _fail("En indataprofil får inte innehålla sparade solverresultat eller startlösningar.")
    raw = deepcopy({k: v for k, v in raw_input.items() if k != "source_archive"})
    from .flora_window_binding import verify_input
    verify_input(raw, profile)
    md = raw.get("metadata") or {}
    if md.get("schema_version") not in ("flora-bb-input/1.0", "bb-input/1.0"):
        _fail("Underlaget måste vara bb-input/1.0 eller flora-bb-input/1.0 från appens import.")
    timezone = md.get("timezone")
    if not timezone:
        _fail("metadata.timezone saknas. Tidszon får inte gissas.")
    periods = _index(md.get("periods"), "id", "Perioder")
    for expected in profile.get("applicable_periods", []):
        if periods.get(expected["id"]) != expected:
            _fail(f"Profilen gäller inte de uppladdade datumen för {expected['id']}.")
    pid = profile.get("period_id")
    history_id = profile.get("history_period_id")
    if pid not in periods or history_id not in periods:
        _fail("Profilens optimeringsperiod och frysta historik måste finnas i underlaget.")
    period, history_period = periods[pid], periods[history_id]
    origin = _time(period["start"], timezone)
    end = _time(period["end"], timezone) + timedelta(days=1)
    history_start = _time(history_period["start"], timezone)
    history_end = _time(history_period["end"], timezone) + timedelta(days=1)
    if end-origin != timedelta(days=28) or history_end-history_start != timedelta(days=28) or history_end != origin:
        _fail("P1 och P2 ska vara angränsande 28-dagarsperioder; motsägande datum måste rättas.")
    minute = lambda value: int((_time(value, timezone)-origin).total_seconds()//60)
    horizon = int((end-origin).total_seconds()//60)
    scenario = scenario or {}
    if profile.get('reviewed_day_boundaries') is not None:
        # Reuse previously reviewed, business-specific decisions when a fresh
        # file import has no local overrides. An explicit empty value remains
        # empty; neither a missing fact nor a user's override is concealed.
        scenario = deepcopy(scenario)
        workspace = scenario.setdefault('workspace', {})
        if isinstance(workspace, dict):
            rules = workspace.setdefault('unit_rules', {})
            if isinstance(rules, dict) and 'day_boundaries' not in rules:
                rules['day_boundaries'] = deepcopy(profile['reviewed_day_boundaries'])
    _workspace(scenario, raw, profile)
    absence_mode = scenario.get("absence_mode", profile.get("absence_mode"))
    if absence_mode not in profile.get("allowed_absence_modes", []):
        _fail("Scenariots frånvarohantering saknar ett uttryckligt profilbeslut.")
    staff_raw = _index(raw.get("staff"), "person_id", "Personal")
    if set(staff_raw) != set(profile.get("staff", {})):
        _fail("Personregistret skiljer sig från profilens verifierade personkopplingar.")
    daily_rest_parameters = _day_boundary_parameters(scenario, periods, set(staff_raw), pid, timezone)
    economic_parameters = _economic_parameters(scenario,set(staff_raw))
    staff = []
    for person_id, decision in profile["staff"].items():
        row = staff_raw[person_id]
        _match(row, decision["expected"], f"Personal {person_id}")
        skills = row.get("individual_delegations")
        if skills != "ALLA_BEFINTLIGA_INSATSKRAV":
            _fail(f"{person_id}: denna metod kräver bekräftad behörighet för befintliga insatskrav.")
        target = decision.get("target_net")
        if decision["ordinary"]:
            target = _integer(target, f"{person_id} ordinarie nettoreferens", 0)
        elif target is not None:
            _fail(f"{person_id}: timvikarie får inte automatiskt bli avtalad kapacitet.")
        staff.append(dict(id=person_id, name=row.get("alias") or person_id,
                          ordinary=decision["ordinary"], target_net=target,
                          all_task_skills=True,
                          **{key: "JA" if row.get(source) is True else "NEJ" if row.get(source) is False else None
                             for key, source in (("day","day_allowed"),("evening","evening_allowed"),
                                                 ("sleeping_oncall","sleeping_oncall_allowed"),("awake_night","awake_night_allowed"))}))
    segments_raw = _index(raw.get("schedule_segments"), "segment_id", "Schema")
    decisions = profile.get("segment_decisions", {})
    if set(segments_raw) != set(decisions):
        _fail("Schemarader har tillkommit eller försvunnit. Beslutsprofilens passkopplingar behöver uppdateras.")
    segments, fixed, imported, excluded, absence_locks = {}, [], [], [], []
    adjustments = _index(profile.get("segment_adjustments",[]),"segment_id","Scenariojusteringar")
    applied_adjustments = []
    for sid, row in segments_raw.items():
        decision = decisions[sid]
        _match(row, decision["expected"], f"Schemarad {sid}")
        if row["person_id"] not in staff_raw:
            _fail(f"Schemarad {sid}: okänd person; vakans får inte bli personal.")
        a, b = minute(row.get("start")), minute(row.get("end"))
        if b <= a:
            _fail(f"Schemarad {sid}: sluttiden måste vara efter starttiden.")
        segment = dict(id=sid,person=row["person_id"],start=a,end=b,
                       type=row.get("category"),code=row.get("source_code"),
                       locked_reason=decision.get("locked_reason"))
        # Reviewed source categories describe activity, not a day/night function.
        # Preserve the source row while mapping its explicit code for the solver.
        if "model_type" in decision:
            allowed = {"Ar": ("AKTIVT_ARBETE", {"AKTIVT_ARBETE", "ARBETE_BRUTTO"}),
                       "Jo": ("SOVANDE_JOUR", {"SOVANDE_JOUR", "JOUR"})}
            rule = allowed.get(segment["code"])
            if not rule or decision["model_type"] != rule[0] or row.get("category") not in rule[1]:
                _fail(f"Schemarad {sid}: modelltypen saknar stöd i källans tidskod och kategori.")
            segment["type"] = decision["model_type"]
        if "whole_duty_id" in decision:
            duty = decision["whole_duty_id"]
            if not isinstance(duty, str) or not duty or row.get("sequence_id") != duty:
                _fail(f"Schemarad {sid}: hela passets källkoppling har ändrats.")
            segment["whole_duty_id"] = duty
        is_absence = segment["code"] in ("Se","Ti") and a < horizon and b > 0
        if decision.get("reference_import"):
            imported.append(deepcopy(segment))
        if sid in adjustments:
            adjustment = adjustments[sid]
            if adjustment.get("status") != "SCENARIO" or not adjustment.get("source"):
                _fail(f"Passjusteringen {sid} saknar tydlig SCENARIO-status och källa.")
            if row["start"] != adjustment.get("expected_start") or row["end"] != adjustment.get("expected_end"):
                _fail(f"{sid}: originaltiden avviker från den tidigare testförkortningen. "
                      "Justeringen kan inte flyttas automatiskt till ett annat pass.")
            a,b = minute(adjustment["model_start"]),minute(adjustment["model_end"])
            if b<=a or not 0<=a<horizon or segment["code"]!="Ar":
                _fail(f"{sid}: ogiltig uttrycklig testförkortning.")
            segment.update(start=a,end=b)
            applied_adjustments.append(deepcopy(adjustment))
        segments[sid] = segment
        if is_absence and absence_mode == "preserve":
            segment["locked_reason"] = "CONFIRMED_ABSENCE"
            fixed.append(segment)
            absence_locks.append(dict(id=sid,person=segment["person"],start=a,end=b,
                                      code=segment["code"],source_ref=row.get("source_ref")))
        elif decision["mode"] == "fixed":
            fixed.append(segment)
        elif decision["mode"] == "excluded":
            excluded.append(dict(segment=deepcopy(segment),reason=decision.get("locked_reason"),
                                 absence_omitted=is_absence))
        elif decision["mode"] != "mutable":
            _fail(f"Schemarad {sid}: okänd beslutad hantering.")
    duty_groups = {}
    for segment in segments.values():
        if segment.get("whole_duty_id"):
            duty_groups.setdefault(segment["whole_duty_id"], []).append(segment)
    for duty, duty_rows in duty_groups.items():
        ordered = sorted(duty_rows, key=lambda row: row["start"])
        if len({row["person"] for row in ordered}) != 1 or any(
                left["end"] != right["start"] for left, right in zip(ordered, ordered[1:])):
            _fail(f"Hela passet {duty}: person eller sammanhängande passgränser måste granskas.")
    # Explicit reviewed future-plan decisions only. Never rewrite a source
    # outcome, infer capacity from sickness, or apply a P2 decision to P1.
    planned_oncall, planned_active = [], []
    planned_rows = [(p, "Jo") for p in profile.get("planned_oncall_replacements", [])]
    planned_rows += [(p, "Ar") for p in profile.get("planned_active_replacements", [])]
    for plan, code in planned_rows:
        sid = plan.get("source_segment_id")
        row = segments_raw.get(sid)
        if not row or row.get("source_code") != "St" or decisions[sid]["mode"] != "excluded":
            _fail("Planerad aktivitet kräver en uttryckligt undantagen St-källrad.")
        if plan.get("status") != "SCENARIO" or not plan.get("source"):
            _fail("Planerad aktivitet saknar SCENARIO-status eller beslutsreferens.")
        if (row["start"], row["end"]) != (plan.get("expected_start"), plan.get("expected_end")):
            _fail("Sjuktidens källtider har ändrats; aktivitetsbeslutet måste granskas igen.")
        a, b = minute(plan.get("start")), minute(plan.get("end"))
        if not 0 <= a < b <= horizon or not minute(row["start"]) <= a < b <= minute(row["end"]):
            _fail("Planerad aktivitet måste ligga inom beslutad P2-sjuktid.")
        person_id = row["person_id"]
        group = sid.rsplit("-", 1)[0]
        new_id = plan.get("id")
        if not isinstance(new_id, str) or new_id in segments or new_id.rsplit("-", 1)[0] != group:
            _fail("Planerad aktivitet saknar unik koppling till källpasset.")
        siblings = [r for key, r in segments.items() if r["person"] == person_id and
                    key.rsplit("-", 1)[0] == group and r["code"] in ({"Jo"} if code == "Jo" else {"Ar", "Jo"})]
        if not siblings or not any(r["end"] == a or r["start"] == b for r in siblings):
            _fail("Planerad aktivitet måste ansluta till källpassets befintliga arbete eller jour.")
        if any(r["person"] == person_id and r["code"] in {"Ar", "Jo", "Kl", "Öv", "Se", "Ti"}
               and max(a, r["start"]) < min(b, r["end"]) for r in segments.values()):
            _fail("Planerad aktivitet överlappar arbete, jour eller spärrad frånvaro.")
        segment = dict(id=new_id, person=person_id, start=a, end=b, code=code,
                       type="SOVANDE_JOUR" if code == "Jo" else "AKTIVT_ARBETE",
                       locked_reason="EXPLICIT_PLANNED_ACTIVITY_SCENARIO")
        segments[new_id] = segment
        fixed.append(segment)
        (planned_oncall if code == "Jo" else planned_active).append(deepcopy(plan))
    candidates = []
    for window in profile.get("candidate_windows", []):
        person_id = window["person_id"]
        if person_id not in staff_raw:
            _fail(f"Arbetsfönstret avser okänd person {person_id}.")
        day = minute(window["date"])/1440
        if not day.is_integer() or not 0 <= day < horizon/1440:
            _fail(f"Arbetsfönstret {window['date']} ligger utanför optimeringsperioden.")
        day = int(day)
        old_id = window.get("source_segment_id")
        old = segments.get(old_id) if old_id else None
        if old_id and (not old or decisions[old_id]["mode"] != "mutable"):
            _fail(f"Arbetsfönstrets källpass {old_id} är inte verifierat ändringsbart.")
        candidates.append(dict(id=old_id or f"NEW-{person_id}-{window['date']}",person=person_id,day=day,
                               lo=day*1440+_integer(window["earliest"],"Tidigaste arbetstid",0),
                               hi=day*1440+_integer(window["latest"],"Senaste arbetstid",1),
                               min_length=_integer(window["min_length"],"Minsta hela pass",240),
                               max_length=_integer(window["max_length"],"Längsta kandidatpass",240),
                               original_start=old["start"] if old else None,
                               original_end=old["end"] if old else None))
    needs_raw = _index(raw.get("customer_needs"), "need_id", "Kundbehov")
    p2_needs = {nid: row for nid, row in needs_raw.items()
                if 0 <= minute(row.get("date")) < horizon}
    if set(p2_needs) != set(profile.get("need_decisions", {})):
        _fail("P2-behov har tillkommit eller försvunnit. Beslutsmappningen måste uppdateras; inget behov får tappas.")
    customers = _index(raw.get("customers"), "customer_id", "Kunder")
    needs, source_needs, need_ids = [], [], {}
    for nid, decision in profile["need_decisions"].items():
        row = p2_needs[nid]
        _match(row, decision["expected"], f"Behov {nid}")
        desc = row.get("source_fields", {}).get("Beskrivning")
        if desc != decision.get("description"):
            _fail(f"Behov {nid}: insatsbeskrivningen har ändrats; samplanering/flyttbarhet måste granskas igen.")
        if row.get("required_codes"):
            _fail(f"Behov {nid}: nya manuella kompetenskoder behöver explicit mappning.")
        if row.get("customer_id") not in customers:
            _fail(f"Behov {nid}: kundkoppling saknas.")
        date = row["date"][:10]
        def need_time(value: Any) -> int:
            if not isinstance(value, str):
                _fail(f"Behov {nid}: tidsfönstret är okänt.")
            return minute(date+"T"+value if "T" not in value and len(value)<=8 else value)
        a, b = need_time(row.get("window_start")), need_time(row.get("window_end"))
        if b == a:
            _fail(f"Behov {nid}: identiska start- och sluttider får inte automatiskt bli ett dygn.")
        if b < a:
            b += 1440
        duration = _integer(row.get("duration_minutes"),f"Behov {nid} duration",1)
        flag = row.get("source_two_person_flag")
        count = row.get("personnel_count_candidate")
        if count is None:
            count = 2 if flag is True else 1 if flag is False else None
        count = _integer(count,f"Behov {nid} antal personer",1)
        if flag is not None and count != (2 if flag is True else 1):
            _fail(f"Behov {nid}: antal personer motsäger originalets dubbelbemanningsfält.")
        try:
            semantics = need_windows.resolve(row.get("window_semantics"), decision.get("window_semantics"))
        except ValueError as exc:
            _fail(str(exc))
        if semantics != "START_WINDOW" and duration > b-a:
            _fail(f"Behov {nid}: hela durationen ryms inte i originalfönstret; ingen automatisk korrigering görs.")
        flex = decision["flex"]
        if row.get("fixed_or_flexible") not in (None,"flexible" if flex else "fixed"):
            _fail(f"Behov {nid}: ny fast/flyttbar-markering motsäger granskad profil.")
        lo = (a//1440)*1440+decision["flex_start_minute"] if flex else a
        hi = (a//1440)*1440+decision["flex_end_minute"] if flex else b
        if semantics is None:
            # Unchanged numerical legacy interpretation; no typed contract asserted.
            domains = [[lo, hi-duration]]
            if flex and decision.get("retain_original_start") and not lo <= a <= hi-duration:
                domains.append([a, a])
        else:
            try:
                first, last = need_windows.bounds(semantics, a, b, duration, 0, horizon)
            except ValueError as exc:
                _fail(str(exc))
            # Existing profile restrictions may narrow, never widen a typed source window.
            profile_last = hi if semantics == "START_WINDOW" else hi-duration
            domains = [[max(lo, first), min(profile_last, last)]]
            if domains[0][0] > domains[0][1]:
                domains = []
            if flex and decision.get("retain_original_start") and first <= a <= last and not any(x <= a <= y for x,y in domains):
                domains.append([a,a])
            if not domains:
                _fail(f"Behov {nid}: profilens tillåtna starttider ryms inte i det typade källfönstret.")
        if any(y<x for x,y in domains):
            _fail(f"Behov {nid}: durationen ryms inte i profilens beslutade arbetsfönster.")
        engine_id = decision.get("engine_id",nid)
        if engine_id in need_ids:
            _fail(f"Behov {nid}: dubblerad motorkoppling {engine_id}.")
        need_ids[engine_id] = nid
        source = dict(id=engine_id,source_row=nid,customer=row["customer_id"],title=row.get("activity"),
                      duration=duration,count=count,domains=domains,original=a,original_window_end=b,
                      flex=flex,previous_class=decision.get("previous_class"),
                      historical_status=row.get("status_raw"),
                      required_skills=", ".join(dict.fromkeys(value for value in (row.get("profession_raw"),row.get("delegated_profession_raw")) if value)),
                      description_present=bool(desc),description_review=decision.get("description_review"),
                      review_reason=decision.get("review_reason"))
        if semantics is not None:
            source.update(window_semantics=semantics, source_window_start=a, source_window_end=b)
        source_needs.append(deepcopy(source))
        source.update(members=[engine_id],weight=1,exclusive=decision["exclusive"],
                      parallel_permission=decision["parallel_permission"])
        needs.append(source)
    if "business_rules_expected" in profile and raw.get("business_rules") != profile["business_rules_expected"]:
        _fail("Verksamhetsbesluten har ändrats. Den nya regeln behöver mappas; tidigare regler återanvänds inte tyst.")
    breaks = []
    for rule in profile.get("reference_breaks", []):
        original_row = segments_raw[rule["segment_id"]]
        source = dict(id=rule["segment_id"],person=original_row["person_id"],
                      start=minute(original_row["start"]),end=minute(original_row["end"]))
        a = source["start"]+rule["offset"]
        b = a+rule["length"]
        if a<source["start"] or b>source["end"]:
            _fail(f"Referensrasten för {source['id']} ryms inte i det uppladdade passet.")
        breaks.append(dict(person=source["person"],start=a,end=b))
    units = []
    for unit in profile.get("reassignable_units", []):
        ids = list(unit["segment_ids"])
        ids.extend(p["id"] for p in planned_oncall + planned_active
                   if p["source_segment_id"].rsplit("-", 1)[0] == unit["id"])
        rows = [segments[sid] for sid in ids]
        persons = {r["person"] for r in rows}
        if len(persons)!=1:
            _fail(f"Passgruppen {unit['id']} innehåller flera personer.")
        units.append(dict(id=unit["id"],original_person=rows[0]["person"],
                          start=min(r["start"] for r in rows),end=max(r["end"] for r in rows),
                          segment_ids=ids,rows=deepcopy(rows),
                          ar_p2_minutes=sum(max(0,min(horizon,r["end"])-max(0,r["start"])) for r in rows if r["code"]=="Ar")))
    config = deepcopy(profile["config"])
    config.update(known_from=int((history_start-origin).total_seconds()//60),known_to=horizon,day_end=horizon//1440)
    if config.get("min_shift")!=240 or config.get("min_free_days")!=9 or config.get("calendar_mode")!="rolling":
        _fail("Profilen saknar beslutade minimi- och rullande fridagsregler.")
    from .rule_policy import resolve_policy
    try:
        rule_policy=resolve_policy(profile,scenario,config,daily_rest_parameters)
    except ValueError as exc:
        _fail(str(exc))
    override = deepcopy(profile.get("scenario_override",{}))
    override["absence"] = ("P2 Se/Ti omitted ONLY in previously authorized ground-scenario scope"
                           if absence_mode=="omit_p2" else "Confirmed P2 Se/Ti preserved as hard absence locks")
    for adjustment in applied_adjustments:
        override["segment_scenario_"+adjustment["segment_id"]] = (
            adjustment["message"]+" Källa: "+adjustment["source"])
    for label, plans in (("planned_oncall", planned_oncall), ("planned_active", planned_active)):
        if plans:
            override[label] = dict(status="SCENARIO", decisions=plans,
                original_outcomes="UNCHANGED", ordinary_net_targets="UNCHANGED")
    integration = dict(profile_id=profile["profile_id"],input_sha256=_digest(raw),profile_sha256=_digest(profile),
                       person_id_map={key:key for key in staff_raw},
                       person_aliases={key:value.get("alias") for key,value in staff_raw.items()},
                       need_id_map=need_ids,customer_id_map={key:key for key in customers},
                       segment_source_refs={key:row.get("source_ref") for key,row in segments_raw.items()},
                       need_source_refs={key:p2_needs[value].get("source_ref") for key,value in need_ids.items()},
                       period=dict(id=pid,start=period["start"],end=period["end"],timezone=timezone),
                       absence_mode=absence_mode,review_required=True,business_schedule_approved=False,
                       time_type_codes=deepcopy(profile.get("time_type_codes",{})),
                       unknown_time_types=[deepcopy(row) for row in raw.get("untimed_codes",[])
                                           if row.get("date") and 0<=minute(row["date"])<horizon],
                       source_segment_count=len(segments_raw),source_need_count=len(needs_raw),
                       scenario_adjustments=applied_adjustments,
                       planned_oncall_replacements=planned_oncall,
                       planned_active_replacements=planned_active,
                       scenario=deepcopy(scenario))
    if 'window_binding' in profile:
        # A window-type decision is not permission to reschedule an intervention.
        integration['original_window_binding'] = {
            'binding_id': profile['window_binding']['binding_id'],
            'locked_by_default': True,
        }
    need_windows.complete(source_needs)
    source_basis = _verified_source_basis(raw, profile)
    if source_basis is not None:
        integration["source_basis"] = source_basis
    return dict(origin=origin.isoformat(timespec="minutes"),end=end.isoformat(timespec="minutes"),horizon=horizon,
                staff=staff,fixed_segments=sorted(fixed,key=lambda row:(row["person"],row["start"],row["end"],row["id"])),
                candidates=candidates,needs=needs,source_needs=source_needs,
                references={"import":dict(segments=sorted(imported,key=lambda row:(row["person"],row["start"],row["end"],row["id"])),breaks=breaks,placements=[])},
                config=config,issues=deepcopy(profile.get("issues",[])),
                sources=[deepcopy(profile.get("source",{}))],scenario_override=override,
                parallel_decision=deepcopy(profile.get("parallel_decision",{})),
                workflow_decision=deepcopy(profile.get("workflow_decision",{})),
                reassignable_temporary_units=units,confirmed_absence_locks=absence_locks,
                integration=integration,
                daily_rest_parameters=daily_rest_parameters,
                rule_policy=rule_policy,
                economic_parameters=economic_parameters,
                import_provenance=dict(upload=raw,excluded_segments=excluded,
                                       all_timed_history=[deepcopy(row) for row in segments_raw.values() if minute(row["start"])<0],
                                       unknown_values_preserved=True))


build_case = prepare_case
