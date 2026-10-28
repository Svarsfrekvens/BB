"""Source-bound, reviewed availability cases. No IO, search, or client profiles.

This development adapter deliberately accepts only the reviewed input version.
Changed workspaces need a new explicit review, never a fallback to another unit.
The private case contains domains and decisions, never a saved solver result.
"""
from copy import deepcopy
from . import need_windows
from datetime import datetime, timedelta
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

from .flora_import import _workspace
from .concurrency_policy import reviewed_modes, source_row_digest

STRATEGY = 'reviewed-availability/1.0'
SOURCE_LISTS = {'staff': 'person_id', 'customers': 'customer_id',
                'schedule_segments': 'segment_id', 'customer_needs': 'need_id',
                'business_rules': None, 'vc_answers': None}
SOURCE_METADATA = ('schema_version', 'dataset_id', 'timezone', 'periods',
                   'planning_period_id', 'history_period_id', 'source_layout',
                   'source_file_sha256')
FORBIDDEN_CASE_KEYS = {'solution', 'raw_solution', 'result', 'selected_duties',
                       'selected_candidate_ids', 'assignments', 'search_hint',
                       'warm_start', 'solver_status', 'coverage_floor'}


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def source_identity(raw):
    """Ignore only authenticated routing and presentation metadata; retain facts."""
    md = raw.get('metadata', {})
    source = {'metadata': {key: md.get(key) for key in SOURCE_METADATA}}
    for name, key in SOURCE_LISTS.items():
        rows = raw.get(name)
        if not isinstance(rows, list):
            raise ValueError('Underlaget saknar listan ' + name + '.')
        if key:
            if any(not isinstance(r, dict) or not isinstance(r.get(key), str) for r in rows):
                raise ValueError(name + ': stabila käll-ID krävs.')
            if len({r[key] for r in rows}) != len(rows):
                raise ValueError(name + ': dubblerade käll-ID.')
            rows = sorted(rows, key=lambda r: r[key])
        source[name] = rows
    return _digest(source)


def minute(value, zone):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(zone))
    if dt.second or dt.microsecond:
        raise ValueError('Källtider måste vara hela minuter.')
    return int(dt.timestamp() // 60)


def _effective_needs(rows, ledger, zone):
    """Rebuild operative times from this request plus explicit reviewed overlays."""
    result = {r['need_id']: dict(earliest=minute(r['window_start'], zone),
        latest_end=minute(r['window_end'], zone), duration=r.get('duration_minutes'),
        count=r.get('personnel_count_candidate'), customer_id=r.get('customer_id')) for r in rows}
    fields = {'window_start':'earliest', 'Intervallstart':'earliest',
        'window_end':'latest_end', 'Intervall änden':'latest_end',
        'duration_minutes':'duration', 'Förväntad genomförandetid (min)':'duration',
        'personnel_count_candidate':'count', 'antal_personer_original':'count',
        'customer_id':'customer_id', 'kund_id':'customer_id'}
    derived = {'start_iso', 'slut_iso', 'fonster_min', 'fonsterkontroll', 'p2_overlapp_min'}
    def value(key, raw):
        if key not in ('earliest', 'latest_end'):
            return raw
        if isinstance(raw, str) and len(raw)>9 and raw[2:3]=='-' and raw[5:6]=='-':
            raw=datetime.strptime(raw,'%d-%m-%Y %H:%M').isoformat(timespec='minutes')
        return minute(raw, zone)
    for record in ledger:
        identity=record.get('need_id')
        if (identity not in result or record.get('status') not in ('CONFIRMED_BY_USER', 'SCENARIO')
                or not record.get('decision_id') or not record.get('source')
                or not isinstance(record.get('changes'), list)):
            raise ValueError('En rättning saknar källa, status eller säker behovskoppling.')
        before=deepcopy(result[identity])
        for change in record['changes']:
            field=change.get('field')
            if field in derived:
                # These explain a source check. Only the actual dated primary
                # fields affect the solver; original display cells stay intact.
                continue
            if field not in fields:
                raise ValueError('Beslutsprofilens rättningsfält saknar uttrycklig mappning: '+str(field))
            key=fields[field]
            if value(key, change.get('before'))!=before[key]:
                raise ValueError('Rättningens Före-värde stämmer inte med uppladdningen: '+identity)
            result[identity][key]=value(key,change.get('after'))
    return result


def check_case(case):
    """Validate supported decisions without constructing CP-SAT in HTTP preflight."""
    if case.get('schema_version') != 'bb-availability-case/1.0':
        raise ValueError('Okänt format för granskat tillgänglighetsunderlag.')
    if FORBIDDEN_CASE_KEYS.intersection(case):
        raise ValueError('Beslutsprofilen får inte innehålla ett sparat motorresultat eller en sökstart.')
    for name in ('employees', 'needs', 'candidates', 'frozen_duties', 'vacancy_duties'):
        rows = case.get(name)
        if not isinstance(rows, list) or any(not isinstance(r, dict) or not isinstance(r.get('id'), str) for r in rows):
            raise ValueError('Beslutsprofilen saknar spårbara ' + name + '.')
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Beslutsprofilen har dubblerade ' + name + '.')
    people = {p['id']: p for p in case['employees']}
    if not people or len(people) > 80 or len(case['needs']) > 4000:
        raise ValueError('Underlagets storlek stöds inte av tillgänglighetsmetoden.')
    rules = case.get('rules', {})
    anchor = rules.get('daily_rest_anchor_decision')
    if anchor and (not isinstance(anchor, dict) or not isinstance(anchor.get('employee_ids'), list)
                   or set(people) - set(anchor['employee_ids'])):
        raise ValueError('Testbeslutet om dygnsbryt omfattar inte alla personer i denna profil.')
    for key, lower in (('min_duty_minutes', 240), ('min_free_days', 9),
                       ('daily_rest_minutes', 660), ('weekly_rest_minutes', 2160)):
        if type(rules.get(key)) is not int or rules[key] < lower:
            raise ValueError('En uttrycklig regelprofil krävs för ' + key + '.')
    if rules.get('breaks') != 'OMITTED_SCENARIO':
        raise ValueError('Rastmodellen stöds inte av denna version. Betald nettotid får inte antas.')
    compensation = rules.get('jour_compensation')
    if (not isinstance(compensation, dict) or not compensation.get('source_ref')
            or not ((compensation.get('mode') == 'IMMEDIATE_REST_MINUTES' and compensation.get('status') == 'CONFIRMED'
                     and type(compensation.get('rest_minutes')) is int and compensation['rest_minutes'] >= 660)
                    or (compensation.get('mode') == 'PLANNED_AR_JO_REST_AT_LEAST_DUTY_SPAN'
                        and compensation.get('source_status') == 'VERIFIED'))):
        raise ValueError('En källbelagd och stödd kompensationsmodell krävs; lokal tillämpning förblir en separat kontroll.')
    if (rules.get('free_days_mode') != 'rolling28' or rules.get('jour_window_minutes') != 40320
            or type(rules.get('jour_cap_minutes')) is not int or not 0 < rules['jour_cap_minutes'] <= 2880):
        raise ValueError('Uttryckliga gränser för rullande fridagar och jour krävs.')
    for person in people.values():
        if person.get('availability_status') != 'VERIFIED' or not isinstance(person.get('allowed_presence_windows'), list):
            raise ValueError('Verifierad tillgänglighet saknas för ' + person['id'] + '.')
        if person.get('staffing_type') not in ('ORDINARY_SOURCE', 'TEMPORARY_VERIFIED') or person.get('vacant'):
            raise ValueError('Vakans eller okänd personaltyp får inte bli tillgänglig kapacitet.')
        if type(person.get('planned_Ar_target_minutes')) is not int or person['planned_Ar_target_minutes'] < 0:
            raise ValueError('Personens bevarade ordinarie Ar-tid saknas.')
    for candidate in case['candidates']:
        if candidate.get('employee_id') not in people:
            raise ValueError('En passdomän saknar verifierad personkoppling.')
        if candidate.get('staffing_type') != people[candidate['employee_id']]['staffing_type']:
            raise ValueError('Passdomänens personaltyp stämmer inte med personen.')
    need_windows.complete(case['needs'])
    for need in case['needs']:
        if (type(need.get('duration')) is not int or need['duration'] <= 0
                or type(need.get('count')) is not int or need['count'] < 1
                or need.get('count_confirmed') is None
                or type(need.get('earliest')) is not int or type(need.get('latest_end')) is not int
                or need['earliest'] >= need['latest_end']
                or (need.get('window_semantics') != 'START_WINDOW' and need['earliest'] + need['duration'] > need['latest_end'])):
            raise ValueError('Behovets varaktighet, antal eller effektiva tidsfönster är inte granskat: ' + need['id'])
        if need.get('window_semantics') is not None:
            need_windows.bounds(need['window_semantics'], need['earliest'], need['latest_end'], need['duration'], case['period']['lo'], case['period']['hi'])
        eligible = need.get('eligible_employee_ids')
        if not isinstance(eligible, list) or set(eligible) - set(people):
            raise ValueError('Behovet har en okänd utförarkoppling: ' + need['id'])
        if need.get('blockers') and eligible:
            raise ValueError('Ett olöst behörighetsvillkor får inte samtidigt tillåta tilldelning.')
    reviewed_modes(case)
    return case


def prepare_case(raw, profile, scenario=None):
    if profile.get('engine_strategy') != STRATEGY or profile.get('data_use') != 'development':
        raise ValueError('Tillgänglighetsmetoden kräver en uttrycklig utvecklingsprofil.')
    identity = source_identity(raw)
    if not isinstance(profile.get('source_identity'), str) or identity != profile['source_identity']:
        raise ValueError('Det uppladdade underlaget eller arbetskopian skiljer sig från denna granskade indataversion. '
                         'Profilens beslut måste stämmas av mot ändringarna före körning; inget äldre resultat används.')
    scenario = scenario or {}
    if scenario.get('absence_mode', 'preserve') != 'preserve':
        raise ValueError('Frånvaro får inte tas bort i denna beslutsprofil.')
    _workspace(scenario, raw, profile)
    rules = (scenario.get('workspace') or {}).get('unit_rules') or {}
    supported = {'default_form', 'person_forms', 'freeday', 'day_boundaries', 'p1_jour_history'}
    if set(rules) - supported:
        raise ValueError('Arbetskopian innehåller nya regelbeslut som måste mappas före körning.')
    if rules.get('default_form') or rules.get('person_forms') or rules.get('day_boundaries') or rules.get('p1_jour_history'):
        raise ValueError('Nya arbetstids- eller vilobeslut måste stämmas av med profilens beslut före körning.')
    if profile.get('partial_input_policy') != 'KEEP_ALL_NEEDS_BLOCK_UNVERIFIED_ASSIGNMENTS':
        raise ValueError('Ofullständiga utföraruppgifter saknar en uttrycklig granskningspolicy.')
    case = deepcopy(profile.get('reviewed_case'))
    if not isinstance(case, dict):
        raise ValueError('Den privata profilen saknar ett granskat tillgänglighetsunderlag.')
    source_needs = {r['need_id']: r for r in raw['customer_needs']}
    for need in case['needs']:
        semantics = need_windows.resolve(source_needs.get(need['id'], {}).get('window_semantics'), need.get('window_semantics'))
        if semantics is not None:
            need['window_semantics'] = semantics
    check_case(case)
    policy = case.get('concurrency_policy')
    if policy and (policy['business_id'] != profile.get('business_id')
                   or policy['source_identity'] != identity):
        raise ValueError('Samplaneringsbeslutet tillhör ett annat underlag eller en annan verksamhet.')
    md = raw['metadata']
    reviewed_sha=(case.get('metadata') or {}).get('source_workbook_sha256')
    if reviewed_sha is not None and reviewed_sha != md.get('source_file_sha256'):
        raise ValueError('Det granskade underlaget är inte avstämt mot denna originalfils kontrollsumma.')
    periods = {p['id']: p for p in md['periods']}
    period = periods[md['planning_period_id']]
    if (case['period']['start'][:10] != period['start']
            or case['period']['end_exclusive'][:10] != (datetime.fromisoformat(period['end'])+timedelta(days=1)).date().isoformat()):
        raise ValueError('Beslutsprofilen avser en annan period än den uppladdade filen.')
    zone = md['timezone']
    source = {r['segment_id']: r for r in raw['schedule_segments']}
    if set(source) != {r['segment_id'] for r in case['source_schedule_segments']}:
        raise ValueError('Profilens källrader stämmer inte med uppladdningen.')
    # Re-read current submitted rows, not a prior schedule or an inferred vacancy employee.
    for record in case['source_schedule_segments']:
        row = source[record['segment_id']]
        record.update(person_id=row.get('person_id'), source_code=row['source_code'],
                      start=row['start'], end=row['end'],
                      is_vacant=row.get('staffing_status') == 'VACANT',
                      source_ref=row.get('source_ref'), source_fields=deepcopy(row.get('source_fields', {})))
    lo, hi = case['period']['lo'], case['period']['hi']
    staff = {r['person_id']: r for r in raw['staff']}
    for person in case['employees']:
        if person['id'] not in staff:
            raise ValueError('En granskad person saknas i uppladdningen.')
        person['alias'] = staff[person['id']].get('alias')
        target = sum(max(0, min(hi, minute(r['end'], zone))-max(lo, minute(r['start'], zone)))
                     for r in raw['schedule_segments']
                     if r.get('person_id') == person['id'] and r['source_code'] == 'Ar')
        if person['staffing_type'] == 'ORDINARY_SOURCE' and target != person['planned_Ar_target_minutes']:
            raise ValueError('Ordinarie Ar-målet stämmer inte med personens uppladdade originalrader.')
    needs = {r['need_id']: r for r in raw['customer_needs']}
    planning_ids = {n['need_id'] for n in raw['customer_needs'] if period['start'] <= n['date'] <= period['end']}
    if planning_ids != {n['id'] for n in case['needs']}:
        raise ValueError('Alla periodens behov måste finnas i den nya körningen.')
    effective=_effective_needs([r for r in raw['customer_needs'] if r['need_id'] in planning_ids],
                               profile.get('decision_ledger', []), zone)
    for need in case['needs']:
        row = needs[need['id']]
        current=effective[need['id']]
        if any(need.get(key)!=value for key,value in current.items()):
            raise ValueError('Behovets granskade modell skiljer sig från uppladdningen och beslutade rättningar: '+need['id'])
        if need.get('required_profession_source') != row.get('profession_raw'):
            raise ValueError('Behovets källbelagda yrkeskrav har ändrats: '+need['id'])
        if need.get('window_semantics') is not None:
            left, right = minute(row['window_start'], zone), minute(row['window_end'], zone)
            # v1 exports exact source bounds/duration/count, not hidden temporal overlays.
            if (current['earliest'] != left or current['latest_end'] != right
                    or current['duration'] != row['duration_minutes'] or current['count'] != row['personnel_count_candidate']):
                raise ValueError('Typade behovsfönster med ändrade källvärden kräver ett annat uttryckligt kontrakt.')
            if case['period'].get('timezone') != zone:
                raise ValueError('Tidszon i profilen och det typade underlaget skiljer sig.')
            need.update(source_window_start=left, source_window_end=right)
        need.update(current)
        need['source_ref'] = row.get('source_ref')
        need['original_submitted_row'] = deepcopy(row)
        if policy and need['concurrency']['source_row_sha256'] != source_row_digest(row):
            raise ValueError('Samplaneringsbeslutet måste granskas mot den aktuella källraden: '+need['id'])
    case['integration'] = dict(profile_id=profile['profile_id'], business_id=profile.get('business_id'),
        data_use=profile['data_use'], source_identity=identity,
        source_file_sha256=md.get('source_file_sha256'),
        period={**period, 'timezone': zone}, profile_source=deepcopy(profile['review_provenance']),
        decisions=deepcopy(profile.get('decision_ledger', [])),
        exact_reviewed_input_only=True, old_solver_result_reused=False)
    return case
