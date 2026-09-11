"""Pure domain/time helpers. No solver or web-framework dependency.

All instants are integer UTC minutes. Ambiguous/nonexistent wall times are
rejected explicitly; night shifts across a DST change keep their real duration.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from math import isfinite

TZ = ZoneInfo('Europe/Stockholm')


def add_days(day, n):
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def days(start, end):
    if (date.fromisoformat(end) - date.fromisoformat(start)).days > 100:
        raise ValueError('För lång period.')
    while start <= end:
        yield start
        start = add_days(start, 1)


def instant(day, clock):
    naive = datetime.fromisoformat(f'{day}T{clock}:00')
    found = set()
    for fold in (0, 1):
        aware = naive.replace(tzinfo=TZ, fold=fold)
        utc = aware.astimezone(timezone.utc)
        if utc.astimezone(TZ).replace(tzinfo=None) == naive:
            found.add(int(utc.timestamp() // 60))
    if len(found) != 1:
        raise ValueError(f'{day} {clock}: tiden saknas eller är tvetydig vid sommartidsomställningen.')
    return found.pop()


def parts(t):
    value = datetime.fromtimestamp(t * 60, TZ)
    return value.date().isoformat(), value.strftime('%H:%M')


def span(shift):
    day, start, end = shift['date'], shift['start'], shift['end']
    return instant(day, start), instant(add_days(day, 1) if end <= start else day, end)


def intersect(a, b, c, d):
    return max(0, min(b, d) - max(a, c))


def overlap(a, b, c, d):
    return a < d and c < b


def paid(shift):
    # Sovande jour är inte arbetstid: den ingår inte i SSG, veckotimmar,
    # kostnad eller insatsbemanning. Spännvidden (span) används fortfarande
    # så att jour inte kan överlappa ett arbetspass.
    if shift.get('type') == 'jour':
        span(shift)
        return []
    a, b = span(shift)
    cursor, result = a, []
    for br in sorted(shift['breaks'], key=lambda x: x['offset']):
        x, y = a + br['offset'], a + br['offset'] + br['minutes']
        if x < cursor or y > b or br['minutes'] <= 0:
            raise ValueError('Ogiltig eller överlappande rast.')
        if cursor < x:
            result.append((cursor, x))
        cursor = y
    if cursor < b:
        result.append((cursor, b))
    return result


def night_intervals(start, end):
    for day in days(add_days(start, -1), end):
        yield instant(day, '22:00'), instant(add_days(day, 1), '06:00')


def jour_spec(rules=None):
    """Sovande jour: 23:00–06:30 alla veckodagar om inget annat anges."""
    spec = ((rules or {}).get('jour') or {})
    start = spec.get('start') or '23:00'
    end = spec.get('end') or '06:30'
    weekdays = spec.get('weekdays') or [1, 2, 3, 4, 5, 6, 7]
    return start, end, weekdays


def jour_intervals(start, end, rules=None):
    clock_start, clock_end, weekdays = jour_spec(rules)
    for day in days(add_days(start, -1), end):
        if date.fromisoformat(day).isoweekday() not in weekdays:
            continue
        stop = instant(add_days(day, 1) if clock_end <= clock_start else day, clock_end)
        yield instant(day, clock_start), stop


def is_night(a, b):
    return any(overlap(a, b, x, y) for x, y in night_intervals(parts(a)[0], parts(b)[0]))


def monday(day):
    return add_days(day, -date.fromisoformat(day).weekday())


def ssg_for_day(e, day):
    ssg = e['ssg']
    for w in e.get('ssgWindows') or []:
        if w['start'] <= day <= w['end']:
            ssg = w['ssg']
    return ssg


def _model_by_id(workplace):
    return {m['id']: m for m in (workplace or {}).get('workTimeModels') or [] if isinstance(m, dict) and m.get('id')}


def _model_covers(model, day):
    if not model:
        return False
    start = model.get('validFrom')
    end = model.get('validTo')
    if start and day < start:
        return False
    if end and day > end:
        return False
    return True


def weekly_minutes_for_day(e, day, rules, workplace=None):
    """Arbetstidsmått för en kalenderdag: fönster → person → verksamhet → rules."""
    models = _model_by_id(workplace)
    for w in e.get('workTimeWindows') or []:
        if not (w.get('start') <= day <= w.get('end')):
            continue
        if w.get('weeklyMinutes') is not None:
            return w['weeklyMinutes']
        model = models.get(w.get('modelId'))
        if _model_covers(model, day):
            return model['weeklyMinutes']
    person_model = models.get(e.get('workTimeModelId'))
    if _model_covers(person_model, day):
        return person_model['weeklyMinutes']
    default_model = models.get((workplace or {}).get('defaultWorkTimeModelId'))
    if _model_covers(default_model, day):
        return default_model['weeklyMinutes']
    return rules['fullTimeWeeklyHours'] * 60


def ssg_cap_minutes(e, period_days, rules, workplace=None):
    return sum(
        ssg_for_day(e, day) / 100 * weekly_minutes_for_day(e, day, rules, workplace) / 7
        for day in period_days
    )


def skills_on_day(e, day):
    base = set(e.get('skills') or [])
    windows = e.get('skillWindows') or []
    if not windows:
        return base
    dated = {}
    for w in windows:
        dated.setdefault(w['skill'], []).append(w)
    out = set()
    for s in base:
        if s not in dated:
            out.add(s)
        elif any(w['start'] <= day <= w['end'] for w in dated[s]):
            out.add(s)
    return out


def hard_constraints(e):
    return ((e.get('constraints') or {}).get('hard') or {})


def soft_constraints(e):
    return ((e.get('constraints') or {}).get('soft') or {})


def calendar_work_days(shifts, start, end):
    """Kalenderdagar i [start, end] med betald arbetstid (ej sovande jour)."""
    out = []
    for day in days(start, end):
        a, b = instant(day, '00:00'), instant(add_days(day, 1), '00:00')
        worked = False
        for s in shifts:
            work = s.get('work')
            if work is None:
                work = paid(s)
            if any(overlap(x, y, a, b) for x, y in work):
                worked = True
                break
        out.append(worked)
    return out


def consecutive_six_seven_counts(worked):
    """Antal 6- respektive 7-dagarsfönster där alla dagar är arbete (A-02/A-03)."""
    n6 = n7 = 0
    for i in range(len(worked) - 5):
        if all(worked[i:i + 6]):
            n6 += 1
    for i in range(len(worked) - 6):
        if all(worked[i:i + 7]):
            n7 += 1
    return n6, n7


def longest_work_run(worked):
    run = best = 0
    for w in worked:
        run = run + 1 if w else 0
        best = max(best, run)
    return best


def rest_days_in_window(worked_slice):
    return sum(1 for w in worked_slice if not w)


def rest_days_missing_in_windows(worked, window=28, target=9):
    """Antal 28-dagarsfönster (eller window) som underskrider F-01. 0 om regeln är av."""
    if target <= 0 or len(worked) < window:
        return 0
    missing = 0
    for i in range(len(worked) - window + 1):
        rest = sum(1 for w in worked[i:i + window] if not w)
        missing += max(0, target - rest)
    return missing


def has_consecutive_off(worked, need=2):
    if need <= 0 or len(worked) < need:
        return True
    run = 0
    for w in worked:
        if w:
            run = 0
        else:
            run += 1
            if run >= need:
                return True
    return False


def weekend_allowed(e, day):
    wd = date.fromisoformat(day).isoweekday()
    if wd < 6:
        return True
    mode = hard_constraints(e).get('weekendMode') or 'all'
    if mode == 'all':
        return True
    if mode == 'none':
        return False
    week = date.fromisoformat(day).isocalendar()[1]
    offset = int(hard_constraints(e).get('weekendOffset') or 0)
    if mode == 'every_other':
        return (week + offset) % 2 == 0
    if mode == 'every_third':
        return (week + offset) % 3 == 0
    return True


def clock_minutes(clock):
    h, m = clock.split(':')
    return int(h) * 60 + int(m)


def shift_allowed(e, template, day, a, b, rules):
    hard = hard_constraints(e)
    types = hard.get('allowedTypes')
    if types and template.get('type') not in types:
        return False
    weekdays = hard.get('weekdays')
    if weekdays and date.fromisoformat(day).isoweekday() not in weekdays:
        return False
    if not weekend_allowed(e, day):
        return False
    start_m = clock_minutes(template['start'])
    end_m = clock_minutes(template['end'])
    earliest = hard.get('earliestStart')
    latest = hard.get('latestEnd')
    if earliest and start_m < clock_minutes(earliest):
        return False
    if latest:
        lim = clock_minutes(latest)
        if end_m > start_m and end_m > lim:
            return False
        if end_m <= start_m and lim < 24 * 60 and end_m > lim:
            return False
    hours = (b - a) / 60
    min_h = hard.get('minShiftHours')
    max_h = hard.get('maxShiftHours')
    if min_h is not None and template.get('type') != 'jour' and hours + 1e-9 < float(min_h):
        return False
    if max_h is not None and hours > float(max_h) + 1e-9:
        return False
    if not set(template.get('skills') or []) <= skills_on_day(e, day):
        return False
    return True


def rolling_week_windows(period_start, period_end):
    """Alla 7×24 h-fönster med start vid midnatt, inkl. sex dagar före perioden."""
    for day in days(add_days(period_start, -6), period_end):
        yield day, instant(day, '00:00'), instant(add_days(day, 7), '00:00')


def duty_week_windows(period_start, period_end, duties):
    """Veckovila enligt 14 § ATL, förankrad i arbetsdygn.

    För varje kalenderdygn med tjänstgöring ska de följande sju dygnen innehålla
    minst 36 timmars sammanhängande ledighet. Det fångar rullande sjudagarsblock
    över söndag–måndag, utan att kräva 36 h i *varje* fasförskjuten kalendervecka
    (vilket skulle underkänna vanliga må–fre-scheman).
    """
    for day, wa, wb in rolling_week_windows(period_start, period_end):
        a, b = instant(day, '00:00'), instant(add_days(day, 1), '00:00')
        if any(overlap(x, y, a, b) for x, y in duties):
            yield day, wa, wb


def longest_rest_minutes(duties, window_a, window_b):
    """Longest consecutive off-duty stretch inside [window_a, window_b). Duties are (start, end)."""
    if window_b <= window_a:
        return 0
    blocked = []
    for a, b in duties:
        x, y = max(a, window_a), min(b, window_b)
        if x < y:
            blocked.append((x, y))
    blocked.sort()
    merged = []
    for a, b in blocked:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    rest = 0
    cursor = window_a
    for a, b in merged:
        rest = max(rest, a - cursor)
        cursor = b
    rest = max(rest, window_b - cursor)
    return rest


def occurrences(data):
    active = {c['id'] for c in data['customers'] if c['active']}
    lo, hi = instant(data['workplace']['start'], '00:00'), instant(add_days(data['workplace']['end'], 1), '00:00')
    out = []
    for day in days(add_days(data['workplace']['start'], -1), data['workplace']['end']):
        wd = date.fromisoformat(day).isoweekday()
        for task in data['interventions']:
            if task['customerId'] not in active or (task['date'] != day if task['date'] else wd not in task['weekdays']):
                continue
            earliest = instant(day, task['start'])
            latest = earliest if task['type'] == 'fixed' else instant(add_days(day, 1) if task['latestEnd'] <= task['start'] else day, task['latestEnd']) - task['minutes']
            if latest < earliest:
                raise ValueError(f"{task['name']}: insatsen ryms inte i tidsfönstret.")
            if overlap(earliest, latest + task['minutes'], lo, hi):
                out.append(dict(id=task['id']+'@'+day, task=task, date=day, earliest=earliest, latest=latest, count=2 if task['doubleStaff'] else 1))
    return out


def check_input(d):
    """Fail closed on malformed data, supported size limits and rule values."""
    def require(ok, message):
        if not ok:
            raise ValueError(message)

    def numeric(value, lo, hi, integer=False):
        return type(value) in (int, float) and isfinite(value) and lo <= value <= hi and (not integer or int(value) == value)

    import re
    try:
        require(d['schemaVersion'] == 1, 'Okänd dataversion.')
        wp = d['workplace']
        require(wp['timezone'] == 'Europe/Stockholm', 'Använd svensk tidszon.')
        n = (date.fromisoformat(wp['end']) - date.fromisoformat(wp['start'])).days + 1
        require(1 <= n <= 42, 'Perioden ska vara 1–42 dagar.')
        models = wp.get('workTimeModels')
        if models is not None:
            require(isinstance(models, list), 'Ogiltiga arbetstidsmodeller.')
            ids = []
            for m in models:
                require(isinstance(m, dict), 'Ogiltig arbetstidsmodell.')
                require(isinstance(m.get('id'), str) and m['id'], 'Arbetstidsmodell saknar id.')
                require(isinstance(m.get('name'), str) and m['name'], 'Arbetstidsmodell saknar namn.')
                require(numeric(m.get('weeklyMinutes'), 60, 3600), 'Ogiltigt veckomått i arbetstidsmodell.')
                if m.get('validFrom'):
                    date.fromisoformat(m['validFrom'])
                if m.get('validTo'):
                    date.fromisoformat(m['validTo'])
                    if m.get('validFrom'):
                        require(m['validFrom'] <= m['validTo'], 'Ogiltig giltighet för arbetstidsmodell.')
                if m.get('reductionRuleId') is not None:
                    require(isinstance(m['reductionRuleId'], str), 'Ogiltig reduceringsregel.')
                ids.append(m['id'])
            require(len(ids) == len(set(ids)), 'Dubbla id i arbetstidsmodeller.')
        default_model = wp.get('defaultWorkTimeModelId')
        if default_model is not None:
            require(isinstance(default_model, str) and default_model, 'Ogiltig default-arbetstidsmodell.')
            if models:
                require(default_model in {m['id'] for m in models}, 'Okänd default-arbetstidsmodell.')
        require(numeric(d['inputRevision'], 0, 10**10, True), 'Ogiltig revision.')
        for key, limit in [('customers',100),('employees',80),('interventions',4000),('templates',12),('boundaryShifts',2000),('absences',2000)]:
            require(isinstance(d[key], list) and len(d[key]) <= limit, f'Ogiltig storlek: {key}.')
            require(len({x['id'] for x in d[key]}) == len(d[key]), f'Dubbla id i {key}.')
        require(1 <= len(d['templates']) <= 12, 'Passmallar saknas.')
        customers = {c['id'] for c in d['customers']}
        employees = {e['id'] for e in d['employees']}
        profiles = {p['id'] for p in d['templates']}
        require(len({c['code'] for c in d['customers']}) == len(customers), 'Dubbla kundkoder.')
        require(len({e['code'] for e in d['employees']}) == len(employees), 'Dubbla medarbetarkoder.')
        for c in d['customers']:
            require(bool(re.fullmatch(r'Kund \d+', c['code'])) and type(c['active']) is bool, 'Ogiltig kundkod/status.')
        for e in d['employees']:
            require(bool(re.fullmatch(r'[A-ZÅÄÖ0-9-]{1,8}', e['code'])), 'Använd medarbetarkoder.')
            require(numeric(e['ssg'],0,100) and type(e['night']) is bool, 'Ogiltig SSG/nattbehörighet.')
            require(e['status'] in ['active','vacant','inactive'], 'Ogiltig personalstatus.')
            require(e['profiles'] and set(e['profiles']) <= profiles, 'Ogiltiga passprofiler.')
            require(e['hourlyCost'] is None or numeric(e['hourlyCost'],0,100000), 'Ogiltig timkostnad.')
            require(isinstance(e['skills'],list) and all(isinstance(k,str) for k in e['skills']), 'Ogiltig kompetens.')
            if e.get('ssgWindows') is not None:
                require(isinstance(e['ssgWindows'], list), 'Ogiltiga SSG-fönster.')
                for w in e['ssgWindows']:
                    require(isinstance(w, dict) and w.get('start') <= w.get('end'), 'Ogiltigt SSG-fönster.')
                    date.fromisoformat(w['start']); date.fromisoformat(w['end'])
                    require(numeric(w['ssg'], 0, 100), 'Ogiltig SSG i fönster.')
            if e.get('workTimeModelId') is not None:
                require(isinstance(e['workTimeModelId'], str) and e['workTimeModelId'], 'Ogiltig arbetstidsmodell.')
            if e.get('workTimeWindows') is not None:
                require(isinstance(e['workTimeWindows'], list), 'Ogiltiga arbetstidsfönster.')
                for w in e['workTimeWindows']:
                    require(isinstance(w, dict) and w.get('start') <= w.get('end'), 'Ogiltigt arbetstidsfönster.')
                    date.fromisoformat(w['start']); date.fromisoformat(w['end'])
                    has_model = isinstance(w.get('modelId'), str) and w.get('modelId')
                    has_minutes = w.get('weeklyMinutes') is not None
                    require(has_model or has_minutes, 'Arbetstidsfönster saknar modell eller veckomått.')
                    if has_minutes:
                        require(numeric(w['weeklyMinutes'], 60, 3600), 'Ogiltigt veckomått i fönster.')
        for t in d['interventions']:
            require(t['customerId'] in customers and t['type'] in ['fixed','flexible'], 'Ogiltig insats/kund.')
            require(numeric(t['minutes'],1,480,True) and type(t['doubleStaff']) is bool, 'Ogiltig insatslängd eller dubbelbemanning.')
            require(t['weekdays'] and set(t['weekdays']) <= set(range(1,8)), 'Ogiltiga veckodagar.')
            require(all(isinstance(k,str) for k in t['skills']), 'Ogiltig kompetens.')
            if t['date']:
                date.fromisoformat(t['date'])
            for value in [t['start'],t['latestEnd']]:
                require(bool(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value)), 'Ogiltig tid.')
            if t.get('requiredEmployeeId') is not None:
                require(t['requiredEmployeeId'] in employees, 'Insatsen kräver en okänd medarbetare.')
        for a in d['absences']:
            require(a['employeeId'] in employees and a['start'] <= a['end'], 'Ogiltig frånvaro.')
            instant(a['start'],'00:00'); instant(a['end'],'00:00')
        for key, lo, hi, integer in [('minRestHours',11,48,False),('fullTimeWeeklyHours',1,60,False),('maxWeeklyHours',1,60,False),('maxShiftHours',1,16,False),('maxConsecutiveDays',1,7,True),('nightFloor',0,10,True),('flexibilityStep',1,60,True)]:
            require(numeric(d['rules'][key],lo,hi,integer), f'Ogiltig regel: {key}.')
        if 'jourFloor' in d['rules']:
            require(numeric(d['rules']['jourFloor'], 0, 10, True), 'Ogiltig regel: jourFloor.')
        jour = d['rules'].get('jour')
        if jour is not None:
            require(isinstance(jour, dict), 'Ogiltig regel: jour.')
            for key in ('start', 'end'):
                if key in jour:
                    require(bool(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', jour[key])), f'Ogiltig jourtid: {key}.')
            if 'weekdays' in jour:
                require(
                    isinstance(jour['weekdays'], list)
                    and jour['weekdays']
                    and all(type(x) is int for x in jour['weekdays'])
                    and set(jour['weekdays']) <= set(range(1, 8)),
                    'Ogiltiga jour-veckodagar.',
                )
        if 'minWeeklyRestHours' in d['rules']:
            require(numeric(d['rules']['minWeeklyRestHours'], 0, 72, False), 'Ogiltig regel: minWeeklyRestHours.')
        if 'minRestDaysInFourWeeks' in d['rules']:
            require(numeric(d['rules']['minRestDaysInFourWeeks'], 0, 28, True), 'Ogiltig regel: minRestDaysInFourWeeks.')
        if 'hardMaxConsecutiveDays' in d['rules']:
            require(numeric(d['rules']['hardMaxConsecutiveDays'], 1, 14, True), 'Ogiltig regel: hardMaxConsecutiveDays.')
        if 'withinPassMinutesPerShift' in d['rules']:
            require(numeric(d['rules']['withinPassMinutesPerShift'], 0, 180, True), 'Ogiltig regel: withinPassMinutesPerShift.')
        for e in d['employees']:
            if e.get('skillWindows') is not None:
                require(isinstance(e['skillWindows'], list), 'Ogiltiga kompetensfönster.')
                for w in e['skillWindows']:
                    require(isinstance(w, dict) and w.get('start') <= w.get('end'), 'Ogiltigt kompetensfönster.')
                    date.fromisoformat(w['start']); date.fromisoformat(w['end'])
                    require(isinstance(w.get('skill'), str) and w['skill'], 'Ogiltig kompetens i fönster.')
            cons = e.get('constraints')
            if cons is not None:
                require(isinstance(cons, dict), 'Ogiltiga individvillkor.')
                hard = cons.get('hard') or {}
                require(isinstance(hard, dict), 'Ogiltiga hårda individvillkor.')
                if 'allowedTypes' in hard:
                    require(isinstance(hard['allowedTypes'], list) and set(hard['allowedTypes']) <= {'day', 'evening', 'night', 'jour'}, 'Ogiltiga tillåtna passtyper.')
                if 'weekdays' in hard:
                    require(isinstance(hard['weekdays'], list) and set(hard['weekdays']) <= set(range(1, 8)), 'Ogiltiga veckodagar i individvillkor.')
                if 'weekendMode' in hard:
                    require(hard['weekendMode'] in ('all', 'none', 'every_other', 'every_third'), 'Ogiltigt helgmönster.')
                if 'weekendOffset' in hard:
                    require(type(hard['weekendOffset']) is int, 'Ogiltig helgförskjutning.')
                for key in ('earliestStart', 'latestEnd'):
                    if key in hard and hard[key]:
                        require(bool(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', hard[key])), f'Ogiltig tid: {key}.')
                for key, lo, hi in (('minShiftHours', 1, 16), ('maxShiftHours', 1, 16), ('maxConsecutiveDays', 1, 7), ('maxNightConsecutive', 1, 14), ('maxJourConsecutive', 1, 14), ('minConsecutiveOffDays', 1, 14)):
                    if key in hard:
                        require(numeric(hard[key], lo, hi, False if 'Hours' in key else True), f'Ogiltigt individtak: {key}.')
                soft = cons.get('soft') or {}
                require(isinstance(soft, dict), 'Ogiltiga mjuka individvillkor.')
                if 'preferredTypes' in soft:
                    require(isinstance(soft['preferredTypes'], list) and set(soft['preferredTypes']) <= {'day', 'evening', 'night', 'jour'}, 'Ogiltiga önskade passtyper.')
                for key, lo, hi in (('maxConsecutiveDays', 1, 14), ('minConsecutiveOffDays', 1, 14)):
                    if key in soft:
                        require(numeric(soft[key], lo, hi, True), f'Ogiltigt mjukt individvillkor: {key}.')
                for key in ('forbiddenCustomerIds', 'requiredCustomerIds', 'preferredCustomerIds'):
                    if key in hard or key in soft:
                        src = hard if key in hard else soft
                        require(isinstance(src[key], list), f'Ogiltig lista: {key}.')
        require(numeric(d['economy']['hourlyCost'],0,100000), 'Ogiltig timkostnad.')
        ow = d.get('objectiveWeights') or {}
        require(isinstance(ow, dict), 'Ogiltiga målviktningar.')
        for key in ('continuitySek', 'spreadSekPerPermille', 'uncoveredSekPerMinute', 'preferredMissSek',
                    'consecutive6Sek', 'consecutive7Sek', 'missingRestDaySek', 'missingPairOffSek', 'missingMinOffSek'):
            if key in ow:
                require(numeric(ow[key], 0, 10000), f'Ogiltig målvikt: {key}.')
        require(type(d['boundaryAcknowledged']) is bool,'Periodgränser måste bekräftas explicit.')
        for s in d['boundaryShifts']:
            require(s['employeeId'] in employees, 'Gränspass saknar medarbetare.')
            paid(s)
        for t in d['templates']:
            require(t['type'] in ['day','evening','night','jour'], 'Ogiltig passtyp.')
            require(isinstance(t['skills'],list), 'Passkompetens saknas.')
            for day in days(wp['start'],wp['end']):
                paid({**t,'date':day})
        require(len(occurrences(d)) <= 1600, 'Högst 1 600 insatstillfällen per beräkning. Förkorta perioden.')
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('Grunduppgifter saknas eller har fel format.') from exc
    return d
