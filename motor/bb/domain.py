"""Pure domain/time helpers. No solver or web-framework dependency.

All instants are integer UTC minutes. Ambiguous/nonexistent wall times are
rejected explicitly; night shifts across a DST change keep their real duration.
"""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from math import isfinite
from .limits import effective_max_occurrences, validate_limits_block

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
    """KPI/dimensionering: tiden överlappar nattintervallet 22:00–06:00.

    Detta är inte definitionen av nattbehörighet. Använd
    ``pass_requires_night_eligibility`` för employee.night.
    """
    return time_overlaps_night_interval(a, b)


def time_overlaps_night_interval(a, b):
    return any(overlap(a, b, x, y) for x, y in night_intervals(parts(a)[0], parts(b)[0]))


def pass_requires_night_eligibility(shift_or_template):
    """Vaken natt kräver employee.night. Kväll och jour gör det inte."""
    return (shift_or_template or {}).get('type') == 'night'


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


DUTY_MERGE_GAP_MINUTES = 3 * 60


def minutes_on_calendar_days(a, b):
    """Tjänstgöringsminuter per kalenderdag för intervallet [a, b)."""
    out = {}
    t = a
    while t < b:
        day, _ = parts(t)
        nxt = instant(add_days(day, 1), '00:00')
        chunk = min(b, nxt) - t
        if chunk > 0:
            out[day] = out.get(day, 0) + chunk
        t = min(b, nxt)
    return out


def work_day_date(a, b, fallback=None):
    """Schemadatum: dagen med störst andel av passets tjänstgöringstid.

    Vid exakt lika fördelning används startkalenderdagen (samma bokning som
    Medvind-kolumnen / shift['date'] när passet skrivs på startdygnet).
    """
    by_day = minutes_on_calendar_days(a, b)
    if not by_day:
        return fallback or parts(a)[0]
    best = max(by_day.values())
    winners = [day for day, minutes in by_day.items() if minutes == best]
    if len(winners) == 1:
        return winners[0]
    start_day = parts(a)[0]
    if fallback and fallback in winners:
        return fallback
    if start_day in winners:
        return start_day
    return min(winners)


def _shift_span(s):
    if s.get('a') is not None and s.get('b') is not None:
        return s['a'], s['b']
    return span(s)


def _crosses_midnight(a, b):
    return parts(a)[0] != parts(b)[0] if b > a else False


def shifts_mergeable(prev, nxt):
    """Kedja arbete/jour/natt till ett tjänstgöringstillfälle vid kort lucka."""
    a1, b1 = _shift_span(prev)
    a2, b2 = _shift_span(nxt)
    gap = a2 - b1
    if gap < 0:
        return False
    types = {prev.get('type'), nxt.get('type')}
    if 'jour' in types:
        return gap <= DUTY_MERGE_GAP_MINUTES
    if _crosses_midnight(a1, b1) or _crosses_midnight(a2, b2):
        return gap == 0
    return False


def duty_occasions(shifts):
    """Tjänstgöringstillfällen från *valda* pass, tidsordnade.

    Samma merge-regel som ``iter_mergeable_chains``: konsekutiva par enligt
    ``shifts_mergeable``. Validatorn anropar denna på det faktiska urvalet.
    """
    rows = sorted(shifts, key=lambda s: (_shift_span(s)[0], _shift_span(s)[1], str(s.get('id') or '')))
    groups = []
    for s in rows:
        if groups and shifts_mergeable(groups[-1][-1], s):
            groups[-1].append(s)
        else:
            groups.append([s])
    return groups


def iter_mergeable_chains(items, max_len=12):
    """Alla ko-selektbara kedjor som skulle bilda ett tillfälle om de valdes.

    Konkurrerande mallar med samma start (t.ex. 06:30–10:00 och 06:30–15:00)
    analyseras som separata val. Ordningen bland icke-mergeable mellanliggande
    mallar får inte klippa kedjan.
    """
    seq = sorted(
        items,
        key=lambda c: (_shift_span(c)[0], _shift_span(c)[1], str((c.get('shift') or c).get('id') or '')),
    )
    n = len(seq)

    def rec(idxs):
        chain = [seq[i] for i in idxs]
        yield chain
        if len(idxs) >= max_len:
            return
        last = seq[idxs[-1]]
        last_s = candidate_as_shift(last)
        for j in range(idxs[-1] + 1, n):
            nxt = seq[j]
            a1, b1 = _shift_span(last)
            a2, b2 = _shift_span(nxt)
            if overlap(a1, b1, a2, b2):
                continue
            if not shifts_mergeable(last_s, candidate_as_shift(nxt)):
                continue
            yield from rec(idxs + [j])

    for i in range(n):
        yield from rec([i])


def occasion_work_day_date(group):
    a = min(_shift_span(s)[0] for s in group)
    b = max(_shift_span(s)[1] for s in group)
    return work_day_date(a, b, group[0].get('date') or parts(a)[0])


def occasion_work_day_dates(shifts):
    return {occasion_work_day_date(g) for g in duty_occasions(shifts)}


def occasion_span(group):
    return min(_shift_span(s)[0] for s in group), max(_shift_span(s)[1] for s in group)


def candidate_as_shift(row):
    shift = dict(row.get('shift') or row)
    if row.get('a') is not None:
        shift['a'] = row['a']
        shift['b'] = row['b']
    return shift


EXTENDED_PROFILE_IDS = {'extendedCombinedWorkJour', 'EXTENDED_COMBINED_WORK_JOUR', 'longException'}
COMBINED_PROFILE_IDS = {'combinedWorkJour', 'COMBINED_WORK_JOUR'}


def _seg_type(s):
    return s.get('type') or (s.get('shift') or {}).get('type')


def _seg_profile(s):
    return s.get('dutyProfile') or (s.get('shift') or {}).get('dutyProfile')


def default_shift_profiles():
    """Passprofiler. maxShiftHours gäller per segment, inte som globalt 24 h-tak."""
    combined = dict(
        maxSpanHours=19,
        minJourMinutesInNightWindow=5 * 60,
        nightWindowStart='22:00',
        nightWindowEnd='08:00',
        requiredRestMode='at_least_duty_length',
        compensatoryRestEqualToSpan=True,
        compensatoryMustFollowImmediately=True,
        requiresException=False,
    )
    extended = dict(combined)
    extended.update(maxSpanHours=24, requiresException=True)
    normal = dict(maxSpanHours=None, requiredRestMode=None, compensatoryRestEqualToSpan=False, requiresException=False)
    return dict(
        normal=normal,
        NORMAL=dict(normal),
        combinedWorkJour=dict(combined),
        COMBINED_WORK_JOUR=dict(combined),
        extendedCombinedWorkJour=dict(extended),
        EXTENDED_COMBINED_WORK_JOUR=dict(extended),
        longException=dict(extended),
    )


def shift_profiles(rules=None):
    out = default_shift_profiles()
    extra = ((rules or {}).get('shiftProfiles') or {})
    if isinstance(extra, dict):
        for key, spec in extra.items():
            if not isinstance(spec, dict):
                continue
            base = dict(out.get(key) or {})
            base.update(spec)
            out[key] = base
    return out


def occasion_profile_id(group, rules=None):
    tags = {_seg_profile(s) for s in group}
    if tags & EXTENDED_PROFILE_IDS:
        return 'extendedCombinedWorkJour'
    if tags & COMBINED_PROFILE_IDS:
        return 'combinedWorkJour'
    types = {_seg_type(s) for s in group}
    paid_types = types - {'jour', None}
    if 'jour' in types and paid_types:
        return 'combinedWorkJour'
    return 'normal'


def occasion_max_span_limit_minutes(group, rules=None):
    """Samma tak som validatorn: profile.maxSpanHours från rules.shiftProfiles."""
    spec = shift_profiles(rules).get(occasion_profile_id(group, rules)) or {}
    max_span = spec.get('maxSpanHours')
    if max_span is None:
        return None
    return float(max_span) * 60


def occasion_exceeds_max_span(group, rules=None):
    limit = occasion_max_span_limit_minutes(group, rules)
    if limit is None:
        return False
    a, b = occasion_span(group)
    return (b - a) > limit + 1e-9


def segment_minutes(s):
    a, b = _shift_span(s)
    if s.get('work') is not None:
        paid_m = sum(y - x for x, y in s['work'])
    else:
        raw = s.get('shift') or s
        paid_m = 0 if _seg_type(s) == 'jour' else sum(y - x for x, y in paid({**raw, 'breaks': raw.get('breaks') or []}))
    jour_m = (b - a) if _seg_type(s) == 'jour' else 0
    return dict(
        type=_seg_type(s),
        start=a,
        end=b,
        paidMinutes=paid_m,
        jourMinutes=jour_m,
        ssgMinutes=paid_m,
        coverageMinutes=paid_m,
        costMinutes=paid_m,
    )


def build_duty_occasion(group, rules=None):
    """Ett tjänstgöringstillfälle: ett eller flera segment med särhållna minuter."""
    segs = [segment_minutes(s) for s in group]
    a, b = occasion_span(group)
    return dict(
        segments=segs,
        start=a,
        end=b,
        spanMinutes=b - a,
        paidMinutes=sum(s['paidMinutes'] for s in segs),
        jourMinutes=sum(s['jourMinutes'] for s in segs),
        ssgMinutes=sum(s['ssgMinutes'] for s in segs),
        coverageMinutes=sum(s['coverageMinutes'] for s in segs),
        costMinutes=sum(s['costMinutes'] for s in segs),
        workDayDate=occasion_work_day_date(group),
        shiftIds=[s.get('id') for s in group if s.get('id')],
        profile=occasion_profile_id(group, rules),
    )


def required_rest_after_minutes(group, rules):
    spec = shift_profiles(rules).get(occasion_profile_id(group, rules)) or {}
    if spec.get('requiredRestAfterMinutes') is not None:
        return max(0, int(spec['requiredRestAfterMinutes']))
    mode = spec.get('requiredRestMode')
    if not mode and spec.get('compensatoryRestEqualToSpan'):
        mode = 'at_least_duty_length'
    if mode != 'at_least_duty_length':
        return 0
    a, b = occasion_span(group)
    cap = float((rules or {}).get('maxShiftHours') or 12) * 60
    if (b - a) <= cap + 1e-9:
        return 0
    return int(b - a)


def jour_eligible(e):
    return bool(e.get('jour'))


def night_eligible(e):
    return bool(e.get('night'))


def consecutive_pass_run(shifts, typ):
    """Längsta följd av unika pass av en typ. Datum avgör bara om de ligger i följd.

    Två separata pass med samma startdatum räknas som två, inte som en bool per dag.
    """
    units = sorted(
        (s for s in shifts if s.get('type') == typ),
        key=lambda s: (_shift_span(s)[0], str(s.get('id') or '')),
    )
    if not units:
        return 0
    best = run = 1
    prev = units[0]['date']
    for s in units[1:]:
        delta = (date.fromisoformat(s['date']) - date.fromisoformat(prev)).days
        run = run + 1 if 0 <= delta <= 1 else 1
        best = max(best, run)
        prev = s['date']
    return best


def type_start_date_flags(shifts, typ, start, end):
    """Har minst ett pass av typen detta startdatum. Kvalitet 2/3/4 använder följd av datum."""
    marked = {s['date'] for s in shifts if s.get('type') == typ}
    return [day in marked for day in days(start, end)]


def longest_true_run(flags):
    run = best = 0
    for w in flags:
        run = run + 1 if w else 0
        best = max(best, run)
    return best


def count_true_windows(flags, width):
    if width <= 0 or len(flags) < width:
        return 0
    return sum(1 for i in range(len(flags) - width + 1) if all(flags[i:i + width]))


def consecutive_jour_minutes_in_window(group, win_a, win_b):
    blocked = []
    for s in group:
        typ = s.get('type') or (s.get('shift') or {}).get('type')
        if typ != 'jour':
            continue
        a, b = _shift_span(s)
        x, y = max(a, win_a), min(b, win_b)
        if x < y:
            blocked.append((x, y))
    blocked.sort()
    merged = []
    for a, b in blocked:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return max((b - a for a, b in merged), default=0)


def night_windows_overlapping(a, b, start_clock='22:00', end_clock='08:00'):
    start_day = add_days(parts(a)[0], -1)
    end_day = parts(b)[0]
    for day in days(start_day, end_day):
        wa = instant(day, start_clock)
        wb = instant(add_days(day, 1) if end_clock <= start_clock else day, end_clock)
        if overlap(a, b, wa, wb):
            yield wa, wb


def max_jour_in_night_windows(group, rules=None, profile=None):
    spec = profile or shift_profiles(rules).get(occasion_profile_id(group, rules)) or {}
    start_clock = spec.get('nightWindowStart') or '22:00'
    end_clock = spec.get('nightWindowEnd') or '08:00'
    a, b = occasion_span(group)
    best = 0
    for wa, wb in night_windows_overlapping(a, b, start_clock, end_clock):
        best = max(best, consecutive_jour_minutes_in_window(group, wa, wb))
    return best


def compensatory_from_occasion(group, employee_id, rules):
    """Efterföljande vila för definierad composite-profil. Inte ett intjäningskonto."""
    minutes = required_rest_after_minutes(group, rules)
    if minutes <= 0:
        return None
    a, b = occasion_span(group)
    spec = shift_profiles(rules).get(occasion_profile_id(group, rules)) or {}
    return dict(
        employeeId=employee_id,
        sourceDutyOccasionIds=[s.get('id') for s in group if s.get('id')],
        earnedFrom=parts(b)[0],
        minutesOwed=minutes,
        mustFollowImmediately=bool(spec.get('compensatoryMustFollowImmediately', True)),
        consumeBy=None,
        status='owed',
        requiredRestMode=spec.get('requiredRestMode') or 'at_least_duty_length',
    )


def calendar_work_days(shifts, start, end):
    """Kalenderdagar i [start, end] som är workDayDate för ett tjänstgöringstillfälle.

    Ett pass över midnatt ger en arbetsdag, inte två. Sovande jour räknas som
    ett passdatum. Flera pass med samma workDayDate ger fortfarande en dag.
    """
    marked = occasion_work_day_dates(shifts)
    return [day in marked for day in days(start, end)]


def consecutive_six_seven_counts(worked):
    """Antal 6- respektive 7-dagarsfönster av workDayDate-flaggor (A-02/A-03)."""
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


def rest_days_target(rules):
    """F-01: saknad nyckel = 9. 0 stänger inte av regeln."""
    rules = rules or {}
    if 'minRestDaysInFourWeeks' not in rules:
        return 9
    v = int(rules['minRestDaysInFourWeeks'])
    return 9 if v < 1 else v


def f01_known_span(data):
    """Kända kalenderdagar för F-01: schemaperioden plus deklarerat boundary-horisont."""
    wp = data['workplace']
    lo, hi = wp['start'], wp['end']
    a, b = data.get('boundaryKnownFrom'), data.get('boundaryKnownTo')
    if a and a < lo:
        lo = a
    if b and b > hi:
        hi = b
    return lo, hi


def f01_window_known(start_w, end_w, known_from, known_to):
    return start_w >= known_from and end_w <= known_to


def is_fixed_choice(x):
    """True när passvalet redan är låst (boundary/locked), inte en CP-SAT-variabel."""
    return isinstance(x, int)


def remaining_capacity(limit, fixed_used):
    """Kvarvarande utrymme för beslut. Negativ historik ger 0, inte en osan constraint."""
    return max(0, int(limit) - int(fixed_used))


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


def dates_allowed(e, day):
    """Tillfällig resurs bara på uttryckligen registrerade datum. Tom lista = ingen dag."""
    hard = hard_constraints(e)
    if 'dates' in hard:
        return day in (hard.get('dates') or [])
    if e.get('resourceType') == 'temporary':
        return False
    return True


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
    if not dates_allowed(e, day):
        return False
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


def active_employees(data):
    """Registrerade personer som motorn får schemalägga. Öppna pass och temp_pool ingår inte."""
    return [
        e for e in data['employees']
        if e['status'] == 'active' and e.get('resourceType', 'employee') in ('employee', 'temporary')
    ]


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
        mode = d.get('planningMode') or 'optimizeExisting'
        require(mode in ('optimizeExisting', 'generateFromNeeds'), 'Ogiltigt planeringsläge.')
        if d.get('planningRange') is not None:
            require(isinstance(d['planningRange'], dict), 'Ogiltigt planeringsintervall.')
            for key in ('start', 'end'):
                if d['planningRange'].get(key):
                    date.fromisoformat(d['planningRange'][key])
        if 'existingSchedule' in d and d['existingSchedule'] is not None:
            require(isinstance(d['existingSchedule'], dict), 'Ogiltigt befintligt schema.')
            if d['existingSchedule'].get('shifts') is not None:
                require(isinstance(d['existingSchedule']['shifts'], list), 'Ogiltiga låsta pass.')
        if d.get('lockedShiftIds') is not None:
            require(isinstance(d['lockedShiftIds'], list) and len(d['lockedShiftIds']) <= 8000, 'Ogiltiga låsta pass-id.')
            require(all(isinstance(x, str) and x for x in d['lockedShiftIds']), 'Ogiltiga låsta pass-id.')
        if 'lockedOutsidePlanningRange' in d and d['lockedOutsidePlanningRange'] is not None:
            require(type(d['lockedOutsidePlanningRange']) is bool, 'Ogiltig låsning utanför planeringsintervall.')
        for key, limit in [('customers',100),('employees',80),('interventions',4000),('templates',12),('boundaryShifts',8000),('absences',2000)]:
            require(isinstance(d[key], list) and len(d[key]) <= limit, f'Ogiltig storlek: {key}.')
            require(len({x['id'] for x in d[key]}) == len(d[key]), f'Dubbla id i {key}.')
        require(isinstance(d['templates'], list) and len(d['templates']) <= 12, 'Ogiltig storlek: templates.')
        if mode != 'generateFromNeeds':
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
            if 'jour' in e:
                require(type(e['jour']) is bool, 'Ogiltig jourbehörighet.')
            require(e['status'] in ['active','vacant','inactive'], 'Ogiltig personalstatus.')
            if e.get('resourceType') is not None:
                require(e['resourceType'] in ('employee', 'temp_pool', 'temporary'), 'Ogiltig resurstyp.')
            prof = e.get('profiles') or []
            require(isinstance(prof, list), 'Ogiltiga passprofiler.')
            if mode == 'generateFromNeeds':
                require(set(prof) <= profiles, 'Ogiltiga passprofiler.')
            else:
                require(prof and set(prof) <= profiles, 'Ogiltiga passprofiler.')
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
            require(numeric(d['rules']['minRestDaysInFourWeeks'], 1, 28, True), 'Ogiltig regel: minRestDaysInFourWeeks. F-01 är hård och kan inte stängas av med 0.')
        for key in ('boundaryKnownFrom', 'boundaryKnownTo'):
            if d.get(key):
                date.fromisoformat(d[key])
        if 'hardMaxConsecutiveDays' in d['rules']:
            require(numeric(d['rules']['hardMaxConsecutiveDays'], 1, 14, True), 'Ogiltig regel: hardMaxConsecutiveDays.')
        if 'withinPassMinutesPerShift' in d['rules']:
            require(numeric(d['rules']['withinPassMinutesPerShift'], 0, 180, True), 'Ogiltig regel: withinPassMinutesPerShift.')
        if 'minGeneratedShiftMinutes' in d['rules']:
            require(numeric(d['rules']['minGeneratedShiftMinutes'], 0, 12 * 60, True), 'Ogiltig regel: minGeneratedShiftMinutes.')
        if 'preferredMinShiftMinutes' in d['rules']:
            require(numeric(d['rules']['preferredMinShiftMinutes'], 0, 12 * 60, True), 'Ogiltig regel: preferredMinShiftMinutes.')
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
                if 'dates' in hard:
                    require(isinstance(hard['dates'], list), 'Ogiltiga tillgänglighetsdatum.')
                    for day in hard['dates']:
                        require(isinstance(day, str) and day, 'Ogiltigt tillgänglighetsdatum.')
                        date.fromisoformat(day)
                if 'maxPaidMinutes' in hard:
                    require(numeric(hard['maxPaidMinutes'], 0, 200000, True), 'Ogiltigt maxtak för arbetstid.')
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
                    'consecutive6Sek', 'consecutive7Sek', 'missingRestDaySek', 'missingPairOffSek', 'missingMinOffSek',
                    'nightSeries3Sek', 'nightSeries4Sek'):
            if key in ow:
                require(numeric(ow[key], 0, 10000), f'Ogiltig målvikt: {key}.')
        if 'compensatoryRest' in d and d['compensatoryRest'] is not None:
            require(isinstance(d['compensatoryRest'], list) and len(d['compensatoryRest']) <= 2000, 'Ogiltig kompensationsvila.')
            for row in d['compensatoryRest']:
                require(isinstance(row, dict), 'Ogiltig kompensationsvila.')
                require(row.get('employeeId') in employees, 'Kompensationsvila saknar medarbetare.')
                require(numeric(row.get('minutesOwed'), 0, 48 * 60, True), 'Ogiltiga minuter kompensationsvila.')
                if row.get('status') is not None:
                    require(row['status'] in ('owed', 'consumed', 'waived'), 'Ogiltig status för kompensationsvila.')
        if 'shiftProfiles' in d['rules'] and d['rules']['shiftProfiles'] is not None:
            require(isinstance(d['rules']['shiftProfiles'], dict), 'Ogiltiga passprofiler.')
        require(type(d['boundaryAcknowledged']) is bool,'Periodgränser måste bekräftas explicit.')
        for s in d['boundaryShifts']:
            require(s['employeeId'] in employees, 'Gränspass saknar medarbetare.')
            paid(s)
        vacant = d.get('vacantShifts')
        if vacant is None:
            vacant = d.get('openShifts')
        if vacant is not None:
            require(isinstance(vacant, list) and len(vacant) <= 8000, 'Ogiltiga öppna pass.')
            ids = set()
            for s in vacant:
                require(isinstance(s, dict), 'Ogiltigt öppet pass.')
                sid = s.get('id')
                require(isinstance(sid, str) and sid, 'Öppet pass saknar id.')
                require(sid not in ids, 'Dubbla id i öppna pass.')
                ids.add(sid)
                date.fromisoformat(s['date'])
                require(isinstance(s.get('start'), str) and isinstance(s.get('end'), str), 'Öppet pass saknar tid.')
                require(s.get('source') in (None, 'medvind', 'fore'), 'Ogiltig källa för öppet pass.')
        for t in d['templates']:
            require(t['type'] in ['day','evening','night','jour'], 'Ogiltig passtyp.')
            require(isinstance(t['skills'],list), 'Passkompetens saknas.')
            for day in days(wp['start'],wp['end']):
                paid({**t,'date':day})
        if d.get('limits') is not None:
            validate_limits_block(d.get('limits'))
        occ_cap = effective_max_occurrences(d)
        require(len(occurrences(d)) <= occ_cap, f'Högst {occ_cap} insatstillfällen per beräkning. Förkorta perioden.')
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('Grunduppgifter saknas eller har fel format.') from exc
    return d
