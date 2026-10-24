"""Versioned review-required joint scheduling method.

The implementation is extracted from a reviewed experiment, not a declaration
that an input or a produced roster is approved for operational use.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from math import isfinite
from zoneinfo import ZoneInfo

from .arithmetic import check_arithmetic
from .daily_rest import assess as assess_daily_rest
from .optimizer import solve as _solve

METHOD = 'joint-shifts-breaks-needs/v1'
OBJECTIVE_MODES = {'coverage_then_temporary', 'coverage_then_workload_then_temporary'}


def check_case(case):
    """Reject unsupported profiles instead of silently pooling unknown capacity."""
    cfg = case['config']
    required = ['shift_step','break_length','break_threshold','min_work_before_break',
                'min_work_after_break','max_continuous_active','min_daily_rest',
                'min_weekly_rest','min_free_days','oncall_cap_28d','max_staff_on_duty',
                'min_shift','calendar_mode','week_break']
    if any(k not in cfg for k in required):
        raise ValueError('Regelprofilen saknar uttryckliga inställningar.')
    if case['horizon'] != 28*1440 or cfg['calendar_mode'] != 'rolling' or cfg['week_break'] != 'MONDAY 00:00':
        raise ValueError('Denna metod stöder ett måndagsankrat 28-dagarsscenario med rullande fridagar och fast måndagsvecka.')
    profile = cfg.get('duty_profile',{})
    profile_keys = ['max_reassigned_minutes','long_jour_min_minutes','night_jour_min_minutes','night_start_minute','night_end_minute','compensation_trigger_minutes','compensation_mode']
    if any(k not in profile for k in profile_keys) or profile.get('compensation_mode') != 'REFERENCE_UNCONFIRMED_REST_AT_LEAST_DUTY_SPAN':
        raise ValueError('Uttrycklig arbetstillfälles- och kompensationsprofil saknas eller stöds inte.')
    origin = datetime.fromisoformat(case['origin'])
    end = datetime.fromisoformat(case['end'])
    if origin.weekday() != 0 or origin.time() != datetime.min.time() or end-origin != timedelta(minutes=case['horizon']):
        raise ValueError('Perioddatum och horisont stämmer inte med metodens kalenderprofil.')
    tz = ZoneInfo(case.get('integration',{}).get('period',{}).get('timezone','Europe/Stockholm'))
    # The reviewed method uses local wall minutes. A DST-crossing case must use
    # the UTC-based general engine rather than quietly losing/gaining an hour.
    offsets = {(origin+timedelta(days=d)).replace(tzinfo=tz).utcoffset() for d in range(-28,30)}
    if len(offsets) != 1:
        raise ValueError('Referensmetodens väggtidsmodell stöder inte en sommartidsomställning i denna horisont.')
    if cfg['min_free_days'] < 9 or cfg['min_shift'] < 240:
        raise ValueError('Beslutade minimikrav på fridagar eller helt arbetspass får inte försvagas.')
    break_policy=cfg.get('break_policy','SOLVER_PLACED')
    if break_policy not in ('SOLVER_PLACED','EXPLICIT_NO_BREAK_SCENARIO'):
        raise ValueError('Okänd rastprofil.')
    if break_policy=='EXPLICIT_NO_BREAK_SCENARIO' and case['references']['import'].get('breaks'):
        raise ValueError('Scenario utan rast får inte innehålla registrerade referensraster.')
    if 'max_whole_duty_minutes' in cfg and (type(cfg['max_whole_duty_minutes']) is not int or cfg['max_whole_duty_minutes'] not in (1200,1440)):
        raise ValueError('Högsta hela passlängd måste vara 1200 eller 1440 minuter.')
    if not case['staff'] or len(case['staff']) > 80 or len(case['needs']) > 4000:
        raise ValueError('Underlagets storlek stöds inte av denna testmetod.')
    for key in ['staff','needs','candidates','fixed_segments','reassignable_temporary_units']:
        rows = case[key]
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Dubbla ID i '+key+'.')
    whole=case.get('whole_duty_candidates',[])
    if not isinstance(whole,list) or any(not isinstance(r,dict) for r in whole):
        raise ValueError('Hela passkandidater måste vara en lista med giltiga poster.')
    if len({r.get('id') for r in whole}) != len(whole):
        raise ValueError('Dubbla ID i hela passkandidater.')
    staff = {p['id']:p for p in case['staff']}
    for p in staff.values():
        if p.get('all_task_skills') is not True or p.get('day') != 'JA' or p.get('evening') != 'JA':
            raise ValueError('Verifierad gemensam insatsbehörighet och dag/kvällsbehörighet krävs; okänt får inte bli JA.')
        if type(p.get('ordinary')) is not bool or (p['ordinary'] and (type(p.get('target_net')) is not int or p['target_net'] < 0)):
            raise ValueError('Verifierad personaltyp och individuellt ordinarie nettomål krävs.')
    for n in case['needs']:
        if type(n.get('exclusive')) is not bool or not n.get('parallel_permission'):
            raise ValueError('Behovets samplaneringsbeslut och exklusivitet måste vara uttryckliga.')
        if type(n.get('duration')) is not int or n['duration'] <= 0 or type(n.get('count')) is not int or n['count'] < 1:
            raise ValueError('Behovets varaktighet eller antal personer är okänt/ogiltigt.')
        if not n.get('domains') or any(a > b or a < 0 or b+n['duration'] > case['horizon'] for a,b in n['domains']):
            raise ValueError('Behovet ryms inte i ett tillåtet fönster: '+n['id'])
        semantics=n.get('window_semantics')
        if semantics is not None and semantics not in ('EXECUTION_WINDOW','START_WINDOW'):
            raise ValueError('Okänd tidsfönsterbetydelse: '+n['id'])
        if semantics is not None and (type(n.get('source_window_start')) is not int or type(n.get('source_window_end')) is not int or n['source_window_end']<=n['source_window_start']):
            raise ValueError('Källfönstrets tider saknas: '+n['id'])
    sequential=cfg.get('sequential_individual_customers',False)
    if type(sequential) is not bool:
        raise ValueError('Personbunden kundordning måste vara ett uttryckligt booleskt profilbeslut.')
    if sequential:
        groups=cfg.get('non_individual_customer_ids')
        known={n['customer'] for n in case['needs']}
        if (break_policy!='EXPLICIT_NO_BREAK_SCENARIO' or not isinstance(groups,list) or
            any(not isinstance(value,str) or not value for value in groups) or
            len(groups)!=len(set(groups)) or not set(groups)<=known):
            raise ValueError('Personbunden kundordning kräver giltiga, uttryckligt undantagna grupp-ID och no-break-scenario.')
    for r in case['fixed_segments']:
        if r['person'] not in staff or type(r['start']) is not int or type(r['end']) is not int or r['start'] >= r['end']:
            raise ValueError('Ogiltigt känt schemasegment.')
        if r['code']=='Jo' and r['end']>0 and staff[r['person']].get('sleeping_oncall')!='JA':
            raise ValueError('Jour saknar verifierad behörig mottagare.')
    for c in case['candidates']:
        if c['person'] not in staff or c['min_length'] < cfg['min_shift'] or not(0 <= c['day'] < 28) or c['lo'] >= c['hi']:
            raise ValueError('Ogiltig kandidat eller personkoppling.')
        if break_policy=='EXPLICIT_NO_BREAK_SCENARIO' and any(
            r['person']==c['person'] and r['code'] in ('Ar','Jo','Kl','Öv') and
            max(r['start'],c['lo'])<min(r['end'],c['hi'])
            for r in case['fixed_segments']):
            raise ValueError('Arbetspasskandidat överlappar samma persons låsta arbete eller jour.')
        if break_policy=='EXPLICIT_NO_BREAK_SCENARIO' and (
            c['max_length'] > 780 or c['min_length'] > c['max_length'] or
            c['lo'] < c['day']*1440 or c['hi'] > (c['day']+1)*1440 or
            c['hi']-c['lo'] < c['min_length']):
            raise ValueError('Arbetspass utan jour måste rymmas inom 4–13 timmar på en dag.')
    generated=({r['id'] for r in case['fixed_segments']}|{c['id'] for c in case['candidates']}|
               {r['id'] for r in case['references']['import']['segments']})
    possible_by_person={p:[] for p in staff}
    for c in case['candidates']:
        possible_by_person[c['person']].append((c['lo'],c['hi']))
    for c in whole:
        parts=c.get('parts',[])
        if (break_policy!='EXPLICIT_NO_BREAK_SCENARIO' or not isinstance(c.get('id'),str) or
            not c['id'] or c.get('person') not in staff):
            raise ValueError('Helt jourpass kräver egen giltig kandidat och explicit scenario utan rast.')
        if (type(c.get('start')) is not int or type(c.get('end')) is not int or
            not isinstance(parts,list) or any(not isinstance(r,dict) for r in parts) or
            c['end']-c['start']!=1440 or not 0<=c['start']<c['end']<=case['horizon'] or
            [r.get('code') for r in parts]!=['Ar','Jo','Ar']):
            raise ValueError('Jourkandidat måste vara ett helt 24-timmarspass Ar–Jo–Ar.')
        if not staff[c['person']].get('sleeping_oncall')=='JA' or any(
            type(r.get('start')) is not int or type(r.get('end')) is not int or r['start']>=r['end'] for r in parts):
            raise ValueError('Jourkandidat saknar behörig person eller giltiga tider.')
        if parts[0]['start']!=c['start'] or parts[-1]['end']!=c['end'] or any(
            a['end']!=b['start'] for a,b in zip(parts,parts[1:])):
            raise ValueError('Jourkandidat har lucka, överlapp eller ofullständiga passgränser.')
        duty_profile=cfg['duty_profile'];jo=parts[1]
        longest_night=max((max(0,min(jo['end'],(day+1)*1440+duty_profile['night_end_minute'])-
                           max(jo['start'],day*1440+duty_profile['night_start_minute']))
                           for day in range(c['start']//1440-1,c['end']//1440+1)),default=0)
        if longest_night<duty_profile['night_jour_min_minutes']:
            raise ValueError('Jourkandidat saknar minst fem timmar sammanhängande nattjour.')
        if c['id'] in generated or any(f"{c['id']}:{i}" in generated for i in range(1,4)):
            raise ValueError('Jourkandidat krockar med befintligt schemarad-ID.')
        if any(r['person']==c['person'] and r['code'] in ('Ar','Jo','Kl','Öv') and
               max(r['start'],c['start'])<min(r['end'],c['end']) for r in case['fixed_segments']):
            raise ValueError('Jourkandidat överlappar samma persons låsta arbete eller jour.')
        generated.update(f"{c['id']}:{i}" for i in range(1,4))
        possible_by_person[c['person']].extend((r['start'],r['end']) for r in parts if r['code']=='Ar')
    for person,spans in possible_by_person.items():
        for i,(a,b) in enumerate(spans):
            if any(max(a,x)<min(b,y) for x,y in spans[i+1:]):
                raise ValueError('Överlappande möjliga arbetstider för samma person stöds inte i experimentet.')


def validate_case(case, result):
    """Independent validation with explicit PASS/FAIL/UNKNOWN rule states."""
    raw = result.get('raw_solution',result)
    if 'segments' not in raw:
        return {'overall':'UNKNOWN','validator':'independent-minute-certificate/v1','rules':[],
                'violations':[],'historical':[], 'unknowns':[{'rule_id':'no_candidate','message':'Inget schema finns att validera.'}]}
    checked = check_arithmetic(case,raw)
    summary = checked['summary']
    violations = summary['scope_errors']
    rest = assess_daily_rest(case, raw)
    violations.extend(rest['violations'])
    summary['scope_check_pass'] = not violations
    summary['daily_rest_24h'] = {k:rest[k] for k in ('version','status','required_minutes','missing_person_ids')}
    checked['exports']['daily_rest_24h.json'] = rest
    by_rule = {v['rule'] for v in violations}
    checks = {
        'source_integrity': ('Kända källbehov, P1, fasta segment och personkopplingar är bevarade.', {'original_need_records_changed','known_actual_P1_work_missing','fixed_segment_modified_or_missing','duplicate_segment_id','unknown_or_invalid_candidate','unit_integrity','duplicate_mapped_segment','missing_or_extra_unit_recipient','work_during_confirmed_absence','incomplete_whole_duty_candidate','invalid_whole_duty_candidate'}),
        'ordinary_net': ('Ordinarie Ar-netto kontrollerat separat per person.', {'retained_original_worked_net','target_not_matched_to_original_known_Ar'}),
        'whole_duty_minimum': ('Minimilängd för hela källpassgrupper och nya/kortade pass kontrollerad.', {'whole_occasion_under4h','candidate_bounds_or_length','active_only_duty_over13h'}),
        'rolling_free_days': ('Lediga kalenderdagar kontrollerade i varje rullande 28-dagarsfönster med känd P1.', {'free_calendar_days9'}),
        'breaks': ('Föreslagna raster och aktiv tid utan rast kontrollerade separat.', {'active_continuous_over5h','break_length','break_outside_contiguous_Ar','overlapping_breaks','fixed_break_chain_membership','unexpected_break_in_authorized_without_breaks_test'}),
        'inter_duty_rest': ('Kända vilogap mellan arbetstillfällen kontrollerade; ersätter inte full 24-timmarskontroll.', {'daily_rest11h','same_person_overlapping_Ar_Jo_segments'}),
        'weekly_rest': ('Sammanhängande vila i profilens fasta veckor kontrollerad.', {'fixed_Monday_weekly_rest36h'}),
        'rolling_jour_cap': ('Jourtak kontrollerat i rullande 28-dagarsfönster med känd historik.', {'rolling28day_Jo48h'}),
        'mathematical_assignments': ('Minutvis utförartäckning och handlingens exklusivitet kontrollerade.', {'executor_coverage','shopping_overlap','need_window','need_outside_period','duplicate_need_id','unknown_placed_need','invalid_person_assignment','same_person_different_customers'}),
        'capacity_limit': ('Profilens samtidiga personalnärvaro kontrollerad.', {'max2_active_staff'}),
    }
    rules = [{'rule_id':k,'status':'FAIL' if by_rule & names else 'PASS','message':message} for k,(message,names) in checks.items()]
    if case['config'].get('sequential_individual_customers'):
        names={'invalid_person_assignment','same_person_different_customers','executor_coverage','shopping_overlap'}
        rules.append(dict(rule_id='sequential_individual_customers',status='FAIL' if by_rule & names else 'PASS',
                          message='Personbundna individuella insatser för olika kunder sker efter varandra.'))
    counts = {status:sum(row['status']==status for row in rest['windows']) for status in ('PASS','FAIL','UNKNOWN')}
    rest_message = (f"Fast dygnsvilokontroll: {counts['PASS']} dygn uppfyllda, {counts['FAIL']} avvikelser, "
                    f"{counts['UNKNOWN']} dygn kräver periodunderlag eller undantagsprövning. "
                    f"Dygnsbryt saknas för {len(rest['missing_person_ids'])} medarbetare. "
                    "Jour räknas inte som vila. Villkor för långa jourpass redovisas separat i kontrollintyget.")
    rules.append(dict(rule_id='daily_rest_24h',status=rest['status'],message=rest_message))
    if case['config'].get('max_whole_duty_minutes') is not None:
        rules.append(dict(rule_id='whole_duty_maximum',status='FAIL' if 'whole_duty_over_selected_limit' in by_rule else 'PASS',
                          message='Hela planerade arbetstillfällen kontrollerade mot vald maxlängd.',
                          limit_minutes=case['config']['max_whole_duty_minutes']))
    unknowns = [
        {'rule_id':'jour_compensation_applicability','message':'Referensprofilens kompensationsantagande och individuella undantag är inte verifierade verksamhetsbeslut.'},
        {'rule_id':'practical_concurrency','message':'Tillåten samplanering verifierar inte praktisk aktiv medverkan, plats eller förflyttning.'},
        {'rule_id':'contract_accounting','message':'Bevarat Ar-netto är inte verifierad full SSG eller frånvaroavräkning.'},
        {'rule_id':'untimed_support','message':'Otidsatt journal-, kontaktpersons-, samordnar-, APT- och överlämningstid kan inte antas vara noll.'},
        {'rule_id':'complete_period_edges','message':'Efterföljande okänd historik och passhöljen kan inte godkännas som hela verifierade arbetstillfällen.'},
    ]
    if rest['status']=='UNKNOWN':
        unknowns.append(dict(rule_id='daily_rest_24h',message=rest_message))
    if case['config'].get('break_policy')=='EXPLICIT_NO_BREAK_SCENARIO':
        unknowns.append(dict(rule_id='no_break_applicability',message='Scenario utan rast är ett uttryckligt modellantagande; avtals- och laglig tillämplighet är inte verifierad.'))
    extended=[n for n in case.get('source_needs',[]) if 'approved_window_extension' in n]
    if extended:
        unknowns.append(dict(rule_id='approved_test_window_extension',
                             message=f'{len(extended)} källfönster har beslutade testundantag; originaltiderna är bevarade och skarp tillämpning kräver separat granskning.',
                             need_ids=[n['source_row'] for n in extended]))
    for item in case.get('integration',{}).get('unknowns',[]):
        unknowns.append(item if isinstance(item,dict) else {'rule_id':'input_limitation','message':str(item)})
    for row in summary['inherited_conditional_Jo_issues']:
        unknowns.append({'rule_id':'inherited_jour_window','message':'Ärvd jourkedja saknar verifierad planprofil.', 'detail':row})
    rules.extend({'rule_id':u['rule_id'],'status':'UNKNOWN','message':u['message']} for u in unknowns if u['rule_id']!='daily_rest_24h')
    return {'overall':'FAIL' if violations else 'UNKNOWN','validator':'independent-minute-certificate/v1',
            'rules':rules,'violations':violations,'unknowns':unknowns,
            'historical':[],
            'inherited_scenario_issues':summary['inherited_conditional_Jo_issues'],
            'checked_status':'PASS' if summary['scope_check_pass'] else 'FAIL',
            'details':summary,'certificates':checked['exports']}


def _normalize(case, raw, validation):
    meta=case.get('integration',{}); people={p['id']:p for p in case['staff']}; needs={n['id']:n for n in case['needs']}
    def mapped(kind,value):return meta.get(kind+'_id_map',{}).get(value,value)
    def stamp(t):
        dt=datetime.fromisoformat(case['origin'])+timedelta(minutes=t)
        tz=ZoneInfo(meta.get('period',{}).get('timezone','Europe/Stockholm'))
        return dt.replace(tzinfo=tz).isoformat(timespec='minutes')
    def clip(a,b):return max(0,min(case['horizon'],b)-max(0,a))
    def union(rows):
        out=[]
        for a,b in sorted(rows):
            if b<=a:continue
            if out and a<=out[-1][1]:out[-1][1]=max(b,out[-1][1])
            else:out.append([a,b])
        return out
    def source_people():
        out={}; imported=case['references']['import']['segments']; cfg=case['config']
        no_breaks=cfg.get('break_policy')=='EXPLICIT_NO_BREAK_SCENARIO'
        for pid,p in people.items():
            rows=[r for r in imported if r['person']==pid]
            spans=union([(max(0,r['start']),min(case['horizon'],r['end'])) for r in rows if r['code']=='Ar' and clip(r['start'],r['end'])])
            gross=sum(b-a for a,b in spans)
            # Explicitly the reviewed mathematical break reference, not a claim
            # that exported source cells already had these unpaid breaks.
            br=0 if no_breaks else cfg['break_length']*sum(max(0,(b-a-cfg['max_continuous_active']+cfg['max_continuous_active']+cfg['break_length']-1)//(cfg['max_continuous_active']+cfg['break_length'])) for a,b in spans)
            occupied={d for d in range(28) if any(r['start']<(d+1)*1440 and r['end']>d*1440 for r in rows)}
            out[pid]={'net_minutes':gross-br,'gross_minutes':gross,'jour_minutes':sum(clip(a,b) for a,b in union([(r['start'],r['end']) for r in rows if r['code']=='Jo'])), 'break_minutes':br,'free_days':28-len(occupied)}
        return out
    before_people=source_people()
    stats=validation.get('details',{}); after_people=stats.get('people',{})
    placed={p['id'] for p in raw.get('placements',[])}; all_need_minutes=sum(n['duration']*n['count'] for n in needs.values())
    covered_minutes=sum(needs[i]['duration']*needs[i]['count'] for i in placed if i in needs)
    def totals(pp,after):
        net_key='worked_net_minutes' if after else 'net_minutes'; gross_key='gross_Ar_minutes' if after else 'gross_minutes'; jour_key='jour_P2_minutes' if after else 'jour_minutes'
        def total(key,ordinary=None):return sum(v[key] for pid,v in pp.items() if ordinary is None or people[pid]['ordinary']==ordinary)
        complete=bool(pp)
        values={'ordinary_net_minutes':total(net_key,True) if complete else None,'temporary_net_minutes':total(net_key,False) if complete else None,
                'ordinary_gross_minutes':total(gross_key,True) if complete else None,'temporary_gross_minutes':total(gross_key,False) if complete else None,
                'jour_minutes':total(jour_key) if complete else None,'break_minutes':total('break_minutes') if complete else None,
                'overtime_minutes':None,'extra_minutes':None,'vacant_minutes':None,
                'fully_covered_needs':stats.get('fully_covered_needs') if after else None,'total_needs':len(needs),
                'covered_need_minutes':covered_minutes if after and complete else None,'uncovered_need_minutes':all_need_minutes-covered_minutes if after and complete else None}
        rows=raw.get('segments',[]) if after else case['references']['import']['segments']
        # Only typed rows are counted. If source contains an untimed row of a
        # category the importer marks the corresponding total unknown.
        code_sets=meta.get('time_type_codes',{})
        unknown_types=set()
        for item in meta.get('unknown_time_types',[]):
            if isinstance(item,str):unknown_types.add(item)
            elif isinstance(item,dict):
                code=item.get('source_code',item.get('code'))
                matched={kind for kind,codes in code_sets.items() if codes is not None and code in codes}
                unknown_types.update(matched or code_sets.keys())
        for category in ['overtime','extra','vacant']:
            codes=code_sets.get(category)
            if complete and codes is not None and category not in unknown_types:
                values[category+'_minutes']=sum(clip(r['start'],r['end']) for r in rows if r.get('code') in codes)
        return values
    persons=[]
    weekly=validation.get('certificates',{}).get('independent_workload.json',{}).get('weekly_active_net_minutes',{})
    for pid,p in people.items():
        a=after_people.get(pid)
        persons.append({'person_id':mapped('person',pid),'alias':meta.get('person_aliases',{}).get(pid,p.get('name',pid)),
                        'before':before_people[pid], 'after':None if a is None else {'net_minutes':a['worked_net_minutes'],'gross_minutes':a['gross_Ar_minutes'],'jour_minutes':a['jour_P2_minutes'],'break_minutes':a['break_minutes'],'free_days':a['free_days']},
                        'weekly_net_minutes':weekly.get(pid),'minimum_rolling_free_days':None if a is None else a['rolling_free_min']})
    # Only profile-confirmed whole duties, reviewed reassignment units, and
    # generated candidate shifts provide a pass identity. Source-row prefixes,
    # touching times and source_ref are never used to invent a whole pass.
    unit_by_row={sid:u['id'] for u in case.get('reassignable_temporary_units',[]) for sid in u['segment_ids']}
    candidate_ids={c['id'] for c in case.get('candidates',[])}
    whole_part_ids={f"{c['id']}:{i}":c['id'] for c in case.get('whole_duty_candidates',[]) for i in range(1,4)}
    def pass_identity(row):
        if row.get('whole_duty_id'):
            basis=('PLANNED_REPLACEMENT_OF_REVIEWED_DUTY'
                   if row.get('locked_reason')=='EXPLICIT_PLANNED_ACTIVITY_SCENARIO'
                   else 'PROFILE_WHOLE_DUTY_ID')
            return 'reviewed:'+row['whole_duty_id'], basis
        if row['id'] in unit_by_row:
            return 'unit:'+unit_by_row[row['id']], 'REVIEWED_REASSIGNABLE_UNIT'
        if row['id'] in candidate_ids:
            return 'generated:'+row['id'], 'MODEL_CANDIDATE_SHIFT'
        if row['id'] in whole_part_ids:
            return 'generated:'+whole_part_ids[row['id']], 'MODEL_WHOLE_DUTY_CANDIDATE'
        return None, 'UNVERIFIED'
    segments=[{'segment_id':r['id'],'person_id':mapped('person',r['person']),'start':stamp(r['start']),'end':stamp(r['end']),'code':r['code'],
               'pass_id':pass_identity(r)[0], 'pass_id_basis':pass_identity(r)[1],
               'staffing_type':'ordinary' if people[r['person']]['ordinary'] else 'temporary','source_ref':meta.get('segment_source_refs',{}).get(r['id']),
               'minutes_in_period':clip(r['start'],r['end'])} for r in raw.get('segments',[])]
    breaks=[]
    for index,r in enumerate(raw.get('breaks',[])):
        anchors=[s for s in raw.get('segments',[]) if s['person']==r['person'] and s['start']<=r['start']<r['end']<=s['end']]
        anchor=anchors[0] if len(anchors)==1 else None
        breaks.append({'break_id':f'break:{index}', 'person_id':mapped('person',r['person']),
                       'start':stamp(r['start']), 'end':stamp(r['end']),
                       'duty_id':anchor['id'] if anchor else None,
                       'anchor_segment_id':anchor['id'] if anchor else None,
                       'anchor_status':'UNIQUE_CONTAINING_SEGMENT' if anchor else 'UNRESOLVED',
                       'pass_id':pass_identity(anchor)[0] if anchor else None})
    period_duties=[s for s in segments if s['minutes_in_period']>0 and s['code'] in ('Ar','Jo','Kl','Öv')]
    interventions=[{'need_id':mapped('need',r['id']),'person_id':mapped('person',r['person']),'start':stamp(int((datetime.fromisoformat(r['start'])-datetime.fromisoformat(case['origin'])).total_seconds()//60)),
                    'end':stamp(int((datetime.fromisoformat(r['end'])-datetime.fromisoformat(case['origin'])).total_seconds()//60)), 'customer_id':mapped('customer',r['customer']),
                    'window_semantics':needs[r['id']].get('window_semantics'),
                    'source_window_start':stamp(needs[r['id']]['source_window_start']) if 'source_window_start' in needs[r['id']] else None,
                    'source_window_end':stamp(needs[r['id']]['source_window_end']) if 'source_window_end' in needs[r['id']] else None,
                    'duration_minutes':needs[r['id']]['duration'],'personnel_count':needs[r['id']]['count'],
                    'source_ref':meta.get('need_source_refs',{}).get(r['id'],needs[r['id']].get('source_row'))} for r in validation.get('certificates',{}).get('executors',[])]
    last_feasible=next((s['status'] for s in reversed(raw.get('stages',[])) if s['status'] in {'FEASIBLE','OPTIMAL'}),None)
    solver_status=last_feasible if 'segments' in raw else (raw.get('stages') or [{}])[-1].get('status','UNKNOWN')
    assumptions=[{'id':k,'message':str(v)} for k,v in case.get('scenario_override',{}).items()]
    no_breaks=case['config'].get('break_policy')=='EXPLICIT_NO_BREAK_SCENARIO'
    if case['config'].get('sequential_individual_customers'):
        assumptions.append({'id':'sequential_individual_customers',
                            'message':'Samma medarbetare tidsplacerar individuella insatser för olika kunder efter varandra; undantagna icke-individuella kund-ID kommer från den skyddade profilen.'})
    window_exceptions=[{'need_id':mapped('need',need['id']),
                        **need['approved_window_extension']}
                       for need in case['source_needs'] if 'approved_window_extension' in need]
    if window_exceptions:
        assumptions.append({'id':'approved_test_window_extensions',
                            'message':'Beslutade tidsfönsterundantag gäller endast detta test. Uppladdade originaltider är oförändrade.',
                            'decisions':window_exceptions})
    assumptions.append({'id':'before_break_reference','message':('Ingen rast dras av i detta separata modellspecifika scenario; originalfilen har inga registrerade rasttider.' if no_breaks else 'Före-netto använder scenariots matematiska minimiantal raster enligt rastprofilen, inte verifierade registrerade betalda timmar.'), 'source':case.get('scenario_override',{}).get('ordinary_reference','Explicit rule profile applied to imported Ar intervals')})
    assumptions.extend({'id':u['rule_id'],'message':u['message']} for u in validation.get('unknowns',[]))
    method=('joint-shifts-person-bound-no-break/v1' if case['config'].get('sequential_individual_customers')
            else 'joint-shifts-no-break-experiment/v0' if no_breaks else METHOD)
    result={'schema_version':'bb-engine-run/1.0','review_required':True,'business_schedule_approved':False,'method':method,'solver_status':solver_status,
            'period':meta.get('period',{'id':'P2','start':case['origin'][:10],'end':(datetime.fromisoformat(case['end'])-timedelta(days=1)).date().isoformat(),'timezone':'Europe/Stockholm'}),
            'before':totals(before_people,False),'after':totals(after_people,True),'persons':persons,
            'schedule':{'segments':segments,'breaks':breaks,'interventions':interventions},'validation':validation,
            'need_window_contract':{'version':'bb-need-window/1.0','needs':[
                {'need_id':mapped('need',n['id']),'window_semantics':n.get('window_semantics'),
                 'source_window_start':stamp(n['source_window_start']) if 'source_window_start' in n else None,
                 'source_window_end':stamp(n['source_window_end']) if 'source_window_end' in n else None,
                 'duration_minutes':n['duration'],'personnel_count':n['count']}
                for n in case['source_needs']]},
            'transfer_contract':{'version':'bb-engine-transfer-anchors/1.0',
                                 'pass_ids_complete':solver_status in {'FEASIBLE','OPTIMAL'} and bool(segments) and all(s['pass_id'] is not None for s in segments),
                                 'period_duty_pass_ids_complete':solver_status in {'FEASIBLE','OPTIMAL'} and bool(period_duties) and all(s['pass_id'] is not None for s in period_duties),
                                 'period_duty_rows_without_pass_id':sum(s['pass_id'] is None for s in period_duties),
                                 'break_anchors_complete':all(b['anchor_segment_id'] is not None and b['pass_id'] is not None for b in breaks),
                                 'approval_inherited':False},
            'solver':{'status':solver_status,'phases':raw.get('stages',[]),'wall_seconds':raw.get('total_seconds'),'build_seconds':raw.get('build_seconds'),'model':raw.get('model'),'parameters':raw.get('parameters')},
            'assumptions':assumptions,'unassigned_need_ids':[mapped('need',i) for i in sorted(set(needs)-placed)],'raw_solution':raw,
            'cost_effect':_cost(case,before_people,after_people),
            'daily_rest_parameters':deepcopy(case.get('daily_rest_parameters')),
            'rule_policy':deepcopy(case.get('rule_policy')),
            'time_accounting':{'before_break_reference':{'kind':'EXPLICIT_NO_BREAK_EXPERIMENT' if no_breaks else 'MATHEMATICAL_MINIMUM_REPEATED_BREAK_REFERENCE','recorded_paid_time':False, 'source':case.get('scenario_override',{}).get('ordinary_reference'),'rule_profile':{k:case['config'][k] for k in ['break_length','break_threshold','max_continuous_active']},'minutes_by_person':{mapped('person',pid):p['break_minutes'] for pid,p in before_people.items()},'exported_original_break_minutes':sum(clip(b['start'],b['end']) for b in case['references']['import'].get('breaks',[]))},'after_breaks':'NONE_IN_EXPLICIT_EXPERIMENT' if no_breaks else 'EXPLICIT_SOLVER_PROPOSED_INTERVALS','ordinary_net':'PRESERVED_SOURCE_REFERENCE_NOT_CONTRACTUAL_SSG'},
            'capacity_effect':{'ordinary_net_change_minutes':None if not after_people else sum(a['worked_net_minutes']-before_people[pid]['net_minutes'] for pid,a in after_people.items() if people[pid]['ordinary']),
                               'released_ordinary_customer_capacity_minutes':None,'explanation':'Bevarad ordinarie tid och betald vikarietid hålls isär; praktisk frigjord kundkapacitet är inte verifierad.'}}
    return result


def _cost(case,before,after):
    params=case.get('economic_parameters',{}).get('hourly_cost_by_person',{})
    deltas={pid:(after[pid]['worked_net_minutes']-before[pid]['net_minutes']) for pid,p in {p['id']:p for p in case['staff']}.items() if not p['ordinary'] and pid in after}
    def sourced(pid):
        p=params.get(pid,{})
        return bool(p.get('source') and p.get('currency') and type(p.get('value')) in (int,float) and isfinite(p['value']) and p['value']>=0)
    missing=[pid for pid,delta in deltas.items() if delta and not sourced(pid)]
    changed=[pid for pid,delta in deltas.items() if delta]
    currencies={params[pid]['currency'] for pid in changed if sourced(pid)}
    known=bool(after) and not missing and len(currencies)<=1
    value=sum(delta/60*params[pid]['value'] for pid,delta in deltas.items() if delta) if known else None
    currency=next(iter(currencies)) if known and currencies else None
    return {'temporary_paid_cost_change':value,'currency':currency,'parameters':params,'missing_person_ids':missing,
            'status':('NO_NET_TIME_CHANGE_COST_CURRENCY_UNKNOWN' if known and not changed else 'CALCULATED_FROM_SOURCED_PARAMETERS') if known else 'UNKNOWN_MISSING_OR_MIXED_COST_PARAMETERS',
            'explanation':'Förändrad vikarienettotid × spårbar personkostnad i en gemensam valuta. Jour och ordinarie frigjord kapacitet ingår inte som besparing.'}


def solve_case(case, *, seconds=75, workers=2, seed=41, objective_mode='coverage_then_temporary', progress=None):
    if objective_mode not in OBJECTIVE_MODES:raise ValueError('Okänd sökprofil.')
    if type(seconds) not in (int,float) or not 1 <= seconds <= 300:raise ValueError('Tidsbudget ska vara 1–300 sekunder per söknivå.')
    if type(workers) is not int or not 1 <= workers <= 4:raise ValueError('Antal solvertrådar ska vara 1–4.')
    case=deepcopy(case); check_case(case)
    raw=_solve(case, seconds=seconds, workers=workers, seed=seed, det=seconds, objective_mode=objective_mode, progress=progress)
    validation=validate_case(case,raw)
    return _normalize(case,raw,validation)
