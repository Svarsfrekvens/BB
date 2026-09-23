"""Independent validator. It never imports solver.py or trusts solver status."""
from .domain import (check_input, occurrences, span, paid, overlap, intersect, instant,
                     add_days, days, parts, night_intervals, jour_intervals, monday,
                     period_paid_cap_minutes, skills_on_day, hard_constraints, weekend_allowed,
                     clock_minutes, longest_rest_minutes, duty_week_windows, soft_constraints,
                     calendar_work_days, consecutive_six_seven_counts, longest_work_run,
                     has_consecutive_off, rest_days_target, f01_known_span, f01_window_known,
                     duty_occasions, occasion_span, occasion_profile_id, shift_profiles,
                     occasion_exceeds_max_span, max_jour_in_night_windows,
                     jour_eligible, night_eligible, pass_requires_night_eligibility,
                     consecutive_pass_run, required_rest_after_minutes)
from .generate import planning_day_bounds


def _all_boundary(group, boundaries):
    ids = [s.get('id') for s in group if s.get('id')]
    return bool(ids) and all(i in boundaries for i in ids)


def _history(warnings, source, message, **more):
    warnings.append(dict(rule='BOUNDARY_HISTORY', sourceRule=source, message=message, **more))


def validate(data, schedule):
    errors, warnings = [], []

    def issue(rule, message, **more):
        errors.append(dict(rule=rule, message=message, **more))

    def warn(rule, message, **more):
        warnings.append(dict(rule=rule, message=message, **more))

    try:
        check_input(data)
        occ = occurrences(data)
    except (ValueError, KeyError, TypeError) as exc:
        return dict(valid=False, errors=[dict(rule='INPUT',message=str(exc))], warnings=[])
    employees = {e['id']:e for e in data['employees']}
    wp, r = data['workplace'], data['rules']
    lo, hi = instant(wp['start'],'00:00'), instant(add_days(wp['end'],1),'00:00')
    boundaries = {s['id'] for s in data['boundaryShifts']}
    processed = []
    try:
        ids = [s['id'] for s in schedule['shifts']] + list(boundaries)
        if len(ids) != len(set(ids)):
            issue('DUPLICATE_SHIFT','Ett pass-id förekommer flera gånger.')
        for s in schedule['shifts'] + data['boundaryShifts']:
            try:
                a,b = span(s)
                work = paid(s)
                processed.append(dict(**s,a=a,b=b,work=work))
                e = employees.get(s['employeeId'])
                if not e:
                    issue('EMPLOYEE','Medarbetare saknas.',shiftId=s['id']); continue
                meta = dict(employeeId=e['id'],shiftId=s['id'])
                if s['id'] not in boundaries and e['status'] != 'active':
                    issue('STATUS',f"{e['code']}: inte aktiv.",**meta)
                if pass_requires_night_eligibility(s) and not night_eligible(e):
                    msg = f"{e['code']}: saknar nattbehörighet."
                    if s['id'] in boundaries:
                        _history(warnings, 'NIGHT', msg, **meta)
                    else:
                        issue('NIGHT', msg, **meta)
                if s.get('type') == 'jour' and not jour_eligible(e):
                    issue('JOUR',f"{e['code']}: saknar jourbehörighet.",**meta)
                hard = hard_constraints(e)
                types = hard.get('allowedTypes')
                if types and s.get('type') not in types and s['id'] not in boundaries:
                    issue('PROFILE',f"{e['code']}: passtypen {s.get('type')} är inte tillåten.",**meta)
                if s['id'] not in boundaries and not weekend_allowed(e, s['date']):
                    issue('WEEKEND',f"{e['code']}: helgmönstret tillåter inte arbete {s['date']}.",**meta)
                weekdays = hard.get('weekdays')
                if weekdays and s['id'] not in boundaries:
                    from datetime import date as _date
                    if _date.fromisoformat(s['date']).isoweekday() not in weekdays:
                        issue('WEEKDAY',f"{e['code']}: veckodagen är inte tillåten.",**meta)
                if hard.get('earliestStart') and s['id'] not in boundaries:
                    if clock_minutes(s['start']) < clock_minutes(hard['earliestStart']):
                        issue('WINDOW_EMP',f"{e['code']}: passet startar före tidigaste start.",**meta)
                if hard.get('latestEnd') and s['id'] not in boundaries:
                    start_m = clock_minutes(s['start']); end_m = clock_minutes(s['end']); lim = clock_minutes(hard['latestEnd'])
                    if end_m > start_m and end_m > lim:
                        issue('WINDOW_EMP',f"{e['code']}: passet slutar efter senaste sluttid.",**meta)
                    if end_m <= start_m and lim < 24 * 60 and end_m > lim:
                        issue('WINDOW_EMP',f"{e['code']}: passet slutar efter senaste sluttid.",**meta)
                max_h = hard.get('maxShiftHours')
                min_h = hard.get('minShiftHours')
                hours = (b-a)/60
                if max_h is not None and hours > float(max_h)+1e-9 and s['id'] not in boundaries:
                    issue('SHIFT_LENGTH',f"{e['code']}: längre än individens maxpass.",**meta)
                if min_h is not None and s.get('type')!='jour' and hours+1e-9 < float(min_h) and s['id'] not in boundaries:
                    issue('SHIFT_LENGTH',f"{e['code']}: kortare än individens minpass.",**meta)
                if not set(s['skills']) <= skills_on_day(e, s['date']):
                    issue('SKILL',f"{e['code']}: saknar passkompetens.",**meta)
                if b-a > r['maxShiftHours']*60:
                    msg=f"{e['code']}: för långt pass."
                    if s['id'] in boundaries:
                        _history(warnings,'SHIFT_LENGTH',msg,**meta)
                    else:
                        issue('SHIFT_LENGTH',msg,**meta)
                if any(v['employeeId']==e['id'] and overlap(a,b,instant(v['start'],'00:00'),instant(add_days(v['end'],1),'00:00')) for v in data['absences']):
                    issue('ABSENCE',f"{e['code']}: pass under frånvaro.",**meta)
            except (ValueError,KeyError,TypeError) as exc:
                issue('TIME',f'Ogiltigt arbetspass: {exc}')
        for e in employees.values():
            shifts = sorted((s for s in processed if s['employeeId']==e['id']),key=lambda x:x['a'])
            groups = duty_occasions(shifts)
            for i, group in enumerate(groups):
                if i:
                    prev = groups[i - 1]
                    gap = occasion_span(group)[0] - occasion_span(prev)[1]
                    hist = _all_boundary(prev, boundaries) and _all_boundary(group, boundaries)
                    if gap < 0:
                        msg = f"{e['code']}: {gap/60:g} timmars vila före {group[0]['date']} {group[0]['start']}."
                        if hist:
                            _history(warnings, 'SHIFT_OVERLAP', msg, employeeId=e['id'], shiftId=group[0].get('id'))
                        else:
                            issue('SHIFT_OVERLAP', msg, employeeId=e['id'], shiftId=group[0].get('id'))
                    elif gap < r['minRestHours'] * 60:
                        msg = f"{e['code']}: {gap/60:g} timmars vila före {group[0]['date']} {group[0]['start']}."
                        if hist:
                            _history(warnings, 'REST', msg, employeeId=e['id'], shiftId=group[0].get('id'))
                        else:
                            issue('REST', msg, employeeId=e['id'], shiftId=group[0].get('id'))
                pid = occasion_profile_id(group, r)
                spec = shift_profiles(r).get(pid) or {}
                span_a, span_b = occasion_span(group)
                if occasion_exceeds_max_span(group, r):
                    msg = f"{e['code']}: sammanvägt tjänstgöringstillfälle längre än profilen {pid} tillåter."
                    if _all_boundary(group, boundaries):
                        _history(warnings, 'COMPOSITE_LENGTH', msg, employeeId=e['id'])
                    else:
                        issue('COMPOSITE_LENGTH', msg, employeeId=e['id'])
                need_jour = spec.get('minJourMinutesInNightWindow')
                if need_jour:
                    got = max_jour_in_night_windows(group, r, spec)
                    if got + 1e-9 < int(need_jour):
                        msg = f"{e['code']}: sammanvägt pass saknar minst {int(need_jour)/60:g} timmar sammanhängande jour i nattfönstret."
                        if _all_boundary(group, boundaries):
                            _history(warnings, 'COMPOSITE_JOUR_WINDOW', msg, employeeId=e['id'])
                        else:
                            issue('COMPOSITE_JOUR_WINDOW', msg, employeeId=e['id'])
                owed = required_rest_after_minutes(group, r)
                if owed and i + 1 < len(groups):
                    nxt = groups[i + 1]
                    wait = occasion_span(nxt)[0] - span_b
                    if wait + 1e-9 < owed:
                        msg = f"{e['code']}: {owed/60:g} timmars efterföljande vila krävs efter sammanvägt pass."
                        if _all_boundary(group, boundaries) and _all_boundary(nxt, boundaries):
                            _history(warnings, 'COMP_REST', msg, employeeId=e['id'])
                        else:
                            issue('COMP_REST', msg, employeeId=e['id'])
            bound_shifts = [s for s in shifts if s.get('id') in boundaries]
            used = sum(intersect(a,b,lo,hi) for s in shifts for a,b in s['work'])
            used_b = sum(intersect(a,b,lo,hi) for s in bound_shifts for a,b in s['work'])
            cap = period_paid_cap_minutes(e, list(days(wp['start'], wp['end'])), r, wp)
            if cap is not None and used > cap+0.01:
                if e.get('resourceType') == 'temporary':
                    msg=f"{e['code']}: fler timmar än registrerat maxtak ({cap/60:g} h)."
                else:
                    msg=f"{e['code']}: fler timmar än periodkapaciteten enligt SSG."
                if used_b > cap+0.01:
                    _history(warnings,'CONTRACT',msg,employeeId=e['id'])
                    if used > used_b+0.01:
                        issue('CONTRACT',msg,employeeId=e['id'])
                else:
                    issue('CONTRACT',msg,employeeId=e['id'])
            for week in {monday(day) for day in days(wp['start'],wp['end'])}:
                wa,wb = instant(week,'00:00'),instant(add_days(week,7),'00:00')
                wh=sum(intersect(a,b,wa,wb) for s in shifts for a,b in s['work'])
                wh_b=sum(intersect(a,b,wa,wb) for s in bound_shifts for a,b in s['work'])
                if wh > r['maxWeeklyHours']*60:
                    msg=f"{e['code']}: för många timmar kalenderveckan {week}."
                    if wh_b > r['maxWeeklyHours']*60:
                        _history(warnings,'WEEK_HOURS',msg,employeeId=e['id'])
                        if wh > wh_b+0.01:
                            issue('WEEK_HOURS',msg,employeeId=e['id'])
                    else:
                        issue('WEEK_HOURS',msg,employeeId=e['id'])
            worked = calendar_work_days(shifts, wp['start'], wp['end'])
            worked_b = calendar_work_days(bound_shifts, wp['start'], wp['end'])
            run = longest_work_run(worked)
            run_b = longest_work_run(worked_b)
            legal = r.get('hardMaxConsecutiveDays')
            if legal and run > int(legal):
                msg=f"{e['code']}: fler än {int(legal)} arbetsdagar i följd (hårt tak)."
                if run_b > int(legal):
                    _history(warnings,'CONSECUTIVE',msg,employeeId=e['id'])
                    if run > run_b:
                        issue('CONSECUTIVE', msg, employeeId=e['id'])
                else:
                    issue('CONSECUTIVE', msg, employeeId=e['id'])
            person_cap = hard_constraints(e).get('maxConsecutiveDays')
            if person_cap and run > int(person_cap):
                msg=f"{e['code']}: fler arbetsdagar i följd än individens hårda tak."
                if run_b > int(person_cap):
                    _history(warnings,'CONSECUTIVE',msg,employeeId=e['id'])
                    if run > run_b:
                        issue('CONSECUTIVE', msg, employeeId=e['id'])
                else:
                    issue('CONSECUTIVE', msg, employeeId=e['id'])
            n6, n7 = consecutive_six_seven_counts(worked)
            if n7:
                warn('CONSECUTIVE_SOFT', f"{e['code']}: {run} arbetsdagar i följd (A-03, mål 5).", employeeId=e['id'])
            elif n6:
                warn('CONSECUTIVE_SOFT', f"{e['code']}: 6 arbetsdagar i följd (A-02, mål 5).", employeeId=e['id'])
            rest_target = rest_days_target(r)
            span_from, span_to = add_days(wp['start'], -27), add_days(wp['end'], 27)
            known_from, known_to = f01_known_span(data)
            worked_ext = calendar_work_days(shifts, span_from, span_to)
            worked_b_ext = calendar_work_days(bound_shifts, span_from, span_to)
            days_ext = list(days(span_from, span_to))
            incomplete = False
            for i, start_w in enumerate(days_ext):
                if i + 28 > len(worked_ext):
                    break
                end_w = days_ext[i + 27]
                if end_w < wp['start'] or start_w > wp['end']:
                    continue
                if not f01_window_known(start_w, end_w, known_from, known_to):
                    incomplete = True
                    continue
                rest = sum(1 for w in worked_ext[i:i + 28] if not w)
                rest_b = sum(1 for w in worked_b_ext[i:i + 28] if not w)
                if rest < rest_target:
                    msg = f"{e['code']}: färre än {rest_target} fridagar i 28-dagarsperioden från {start_w} (F-01)."
                    if rest_b < rest_target:
                        _history(warnings, 'REST_DAYS', msg, employeeId=e['id'])
                        if rest < rest_b:
                            issue('REST_DAYS', msg, employeeId=e['id'])
                            incomplete = False
                            break
                    else:
                        issue('REST_DAYS', msg, employeeId=e['id'])
                        incomplete = False
                        break
            if incomplete:
                issue('BOUNDARY_INCOMPLETE', f"{e['code']}: F-01 kan inte godkännas, 28-dagarsfönster saknar bekräftad boundary-data.", employeeId=e['id'])
            if len(worked) >= 2 and not has_consecutive_off(worked, 2):
                warn('PAIR_OFF_SOFT', f"{e['code']}: saknar två sammanhängande fridagar (F-02).", employeeId=e['id'])
            min_off = hard_constraints(e).get('minConsecutiveOffDays')
            if min_off:
                need = int(min_off)
                if any(worked) and not has_consecutive_off(worked, need):
                    msg = f"{e['code']}: saknar {need} sammanhängande lediga dagar."
                    if any(worked_b) and not has_consecutive_off(worked_b, need):
                        _history(warnings, 'MIN_OFF', msg, employeeId=e['id'])
                    else:
                        issue('MIN_OFF', msg, employeeId=e['id'])
            soft_off = soft_constraints(e).get('minConsecutiveOffDays')
            if soft_off:
                need = int(soft_off)
                if any(worked) and not has_consecutive_off(worked, need):
                    warn('MIN_OFF_SOFT', f"{e['code']}: saknar önskade {need} sammanhängande lediga dagar.", employeeId=e['id'])
            weekly = float(r.get('minWeeklyRestHours') or 36)
            if weekly > 0:
                duties = [(s['a'], s['b']) for s in shifts]
                bound_duties = [(s['a'], s['b']) for s in bound_shifts]
                for day, wa, wb in duty_week_windows(wp['start'], wp['end'], duties):
                    if longest_rest_minutes(duties, wa, wb) + 1e-9 < weekly * 60:
                        msg = f"{e['code']}: mindre än {weekly:g} timmars sammanhängande veckovila i sju dagarsperioden från {day}."
                        if bound_duties and longest_rest_minutes(bound_duties, wa, wb) + 1e-9 < weekly * 60:
                            _history(warnings, 'WEEK_REST', msg, employeeId=e['id'])
                        else:
                            issue('WEEK_REST', msg, employeeId=e['id'])
            night_run_lim = hard_constraints(e).get('maxNightConsecutive')
            jour_run_lim = hard_constraints(e).get('maxJourConsecutive')
            nrun = consecutive_pass_run(shifts, 'night')
            jrun = consecutive_pass_run(shifts, 'jour')
            nrun_b = consecutive_pass_run(bound_shifts, 'night')
            jrun_b = consecutive_pass_run(bound_shifts, 'jour')
            if night_run_lim and nrun > int(night_run_lim):
                msg = f"{e['code']}: för många nattpass i följd."
                if nrun_b > int(night_run_lim):
                    _history(warnings, 'NIGHT_SERIES', msg, employeeId=e['id'])
                    if nrun > nrun_b:
                        issue('NIGHT_SERIES', msg, employeeId=e['id'])
                else:
                    issue('NIGHT_SERIES', msg, employeeId=e['id'])
            if jour_run_lim and jrun > int(jour_run_lim):
                msg = f"{e['code']}: för många jourpass i följd."
                if jrun_b > int(jour_run_lim):
                    _history(warnings, 'JOUR_SERIES', msg, employeeId=e['id'])
                    if jrun > jrun_b:
                        issue('JOUR_SERIES', msg, employeeId=e['id'])
                else:
                    issue('JOUR_SERIES', msg, employeeId=e['id'])
            if nrun >= 4:
                warn('NIGHT_SERIES_STRONG', f"{e['code']}: {nrun} nattpass i följd (röd kvalitetsavvikelse, mål 2).", employeeId=e['id'])
            elif nrun >= 3:
                warn('NIGHT_SERIES_SOFT', f"{e['code']}: 3 nattpass i följd (gul kvalitetsavvikelse, mål 2).", employeeId=e['id'])
            jour = [s for s in shifts if s.get('type') == 'jour']
            sorterade = sorted(jour, key=lambda s: s['date'])
            bound_jour = [s for s in sorterade if s.get('id') in boundaries]
            for i, start in enumerate(sorterade):
                gransen = add_days(start['date'], 27)
                total = sum(s['b'] - s['a'] for s in sorterade[i:] if s['date'] <= gransen)
                total_b = sum(s['b'] - s['a'] for s in bound_jour if start['date'] <= s['date'] <= gransen)
                if total > 48 * 60 + 0.01:
                    msg = f"{e['code']}: mer än 48 timmar jourtid under fyra veckor från {start['date']}."
                    if total_b > 48 * 60 + 0.01:
                        _history(warnings, 'JOUR_4W', msg, employeeId=e['id'])
                        if total > total_b + 0.01:
                            issue('JOUR_4W', msg, employeeId=e['id'])
                            break
                    else:
                        issue('JOUR_4W', msg, employeeId=e['id'])
                        break
            per_manad = {}
            per_manad_b = {}
            for s in sorterade:
                k = s['date'][:7]
                per_manad[k] = per_manad.get(k, 0) + (s['b'] - s['a'])
                if s.get('id') in boundaries:
                    per_manad_b[k] = per_manad_b.get(k, 0) + (s['b'] - s['a'])
            for manad, total in per_manad.items():
                if total > 50 * 60 + 0.01:
                    msg = f"{e['code']}: mer än 50 timmar jourtid i {manad}."
                    tb = per_manad_b.get(manad, 0)
                    if tb > 50 * 60 + 0.01:
                        _history(warnings, 'JOUR_MONTH', msg, employeeId=e['id'])
                        if total > tb + 0.01:
                            issue('JOUR_MONTH', msg, employeeId=e['id'])
                    else:
                        issue('JOUR_MONTH', msg, employeeId=e['id'])
        assignments=schedule['assignments']
        known={o['id'] for o in occ}
        # Ett förslag får redovisa obemannat behov, men bara om det är öppet
        # deklarerat. Odeklarerad brist är fortfarande ett fel.
        declared={}
        for u in schedule.get('uncovered') or []:
            try:
                declared[u['occurrenceId']]=int(u['count'])
            except (KeyError,TypeError,ValueError):
                issue('UNCOVERED','Obemannat behov är felaktigt redovisat.')
        for a in assignments:
            if a['occurrenceId'] not in known:
                issue('UNKNOWN_TASK','Okänd insats i tilldelningen.',occurrenceId=a['occurrenceId'])
        for o in occ:
            rows=[a for a in assignments if a['occurrenceId']==o['id']]
            meta=dict(occurrenceId=o['id'])
            distinct=len({a['employeeId'] for a in rows})
            gap=declared.get(o['id'],0)
            if len(rows)!=distinct:
                issue('COVERAGE',f"{o['task']['name']} {o['date']}: samma medarbetare räknas flera gånger.",**meta)
            elif distinct+gap!=o['count']:
                issue('COVERAGE',f"{o['task']['name']} {o['date']}: kräver {o['count']} olika medarbetare.",**meta)
            elif gap:
                warnings.append(dict(rule='UNCOVERED',message=f"{o['task']['name']} {o['date']}: {gap} av {o['count']} insatstillfällen är obemannade i förslaget.",occurrenceId=o['id']))
            if len({a['start'] for a in rows})>1:
                issue('SIMULTANEOUS','Dubbelbemanningen startar inte samtidigt.',**meta)
            for a in rows:
                if type(a['start']) is not int or type(a['end']) is not int or not o['earliest']<=a['start']<=o['latest'] or a['end']!=a['start']+o['task']['minutes']:
                    issue('WINDOW','Insatsen har fel tid eller längd.',**meta)
                e=employees.get(a['employeeId'])
                if not e or e['status']!='active' or not set(o['task']['skills'])<=skills_on_day(e, o['date']):
                    issue('TASK_SKILL','Insatsen saknar behörig medarbetare.',**meta)
                krav=o['task'].get('requiredEmployeeId')
                if krav and a['employeeId']!=krav:
                    issue('TASK_SKILL','Insatsen måste ligga på utsedd medarbetare.',**meta)
                forbid=set(hard_constraints(e).get('forbiddenCustomerIds') or [])
                if o['task']['customerId'] in forbid:
                    issue('CUSTOMER',f"{e['code']}: får inte arbeta med kunden.",**meta)
                if not any(s['employeeId']==a['employeeId'] and any(x<=a['start'] and y>=a['end'] for x,y in s['work']) for s in processed):
                    issue('ON_DUTY','Medarbetaren är inte i tjänst hela insatsen.',**meta)
        reserve=int(r.get('withinPassMinutesPerShift') or 0)
        if reserve:
            for s in processed:
                if s['id'] in boundaries or s.get('type')=='jour':
                    continue
                paid_m=sum(b-a for a,b in s['work'])
                used=sum(a['end']-a['start'] for a in assignments if a['employeeId']==s['employeeId'] and s['a']<=a['start'] and a['end']<=s['b'])
                if used+reserve>paid_m+0.01:
                    issue('WITHIN_PASS',f"Pass {s.get('date')} {s.get('start')} rymmer inte planeringsaktiviteter inom arbetstiden.",shiftId=s.get('id'),employeeId=s.get('employeeId'))
        for e in employees.values():
            rows=sorted((a for a in assignments if a['employeeId']==e['id']),key=lambda x:x['start'])
            for i,a in enumerate(rows):
                for b in rows[i+1:]:
                    if b['start']>=a['end']: break
                    issue('TASK_OVERLAP',f"{e['code']}: dubbelbokad på {a['occurrenceId']} och {b['occurrenceId']}.",employeeId=e['id'])
        floor_lo, floor_hi = lo, hi
        if data.get('_rhClipFloors'):
            ps, pe = planning_day_bounds(data)
            floor_lo, floor_hi = instant(ps, '00:00'), instant(add_days(pe, 1), '00:00')
        for a,b in night_intervals(wp['start'],wp['end']):
            a,b=max(a,floor_lo),min(b,floor_hi)
            if a>=b: continue
            work=[(x,y,s['employeeId']) for s in processed if employees.get(s['employeeId'],{}).get('night') and employees[s['employeeId']]['status']=='active' for x,y in s['work']]
            points=sorted({a,b}|{t for x,y,_ in work for t in (x,y) if a<t<b})
            for t in points[:-1]:
                if len({e for x,y,e in work if x<=t<y})<r['nightFloor']:
                    issue('NIGHT_FLOOR',f"Vaken natt saknar täckning {' '.join(parts(t))}."); break
        jour_floor = int(r.get('jourFloor') or 0)
        if jour_floor:
            for a,b in jour_intervals(wp['start'],wp['end'],r):
                a,b=max(a,floor_lo),min(b,floor_hi)
                if a>=b: continue
                covering=[(s['a'],s['b'],s['employeeId']) for s in processed if s.get('type')=='jour' and jour_eligible(employees.get(s['employeeId'],{})) and employees.get(s['employeeId'],{}).get('status')=='active']
                points=sorted({a,b}|{t for x,y,_ in covering for t in (x,y) if a<t<b})
                for t in points[:-1]:
                    if len({e for x,y,e in covering if x<=t<y})<jour_floor:
                        issue('JOUR_FLOOR',f"Sovande jour saknar täckning {' '.join(parts(t))}."); break
    except (KeyError,TypeError,ValueError) as exc:
        issue('STRUCTURE',f'Schemat kunde inte läsas: {exc}')
    if not data['boundaryAcknowledged']:
        warnings.append(dict(rule='BOUNDARIES',message='Passen före och efter perioden har inte bekräftats.'))
    warnings.append(dict(rule='SCOPE',message='Kontrollen omfattar implementerade regler, inte hela kollektivavtalet.'))
    return dict(valid=not errors,errors=errors,warnings=warnings)
