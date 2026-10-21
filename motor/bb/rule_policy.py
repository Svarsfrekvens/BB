"""Versioned shared principles, resolved against one business's reviewed inputs.

No employee, date, daybreak or local agreement is inherited from another unit.
The manifest describes method behavior; it is not an approval certificate.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json

VERSION = 'bb-shared-principles/1.0'
PRINCIPLES = (
    ('source_preservation', 'Original, planeringsscenario och historiska utfall hålls åtskilda.'),
    ('whole_duties', 'Passgränser bedöms på hela arbetstillfällen, inte varje arbets- eller jourdel.'),
    ('separate_time_types', 'Aktivt arbete, jour, rast, frånvaro och övertid redovisas separat.'),
    ('known_history', 'Känd historik används över periodgränsen; okänd framtid blir inte ledighet.'),
    ('fixed_daily_rest', 'Sammanhängande dygnsvila kontrolleras mot personens fasta dygnsbryt; jour är inte vila och undantag kräver verksamhetens underlag.'),
    ('explicit_permissions', 'Behörighet och tillgänglighet får inte härledas ur namn eller exempeldata.'),
    ('business_isolation', 'Personkopplingar, lokala tider och beslut väljs från rätt verksamhetsprofil.'),
    ('independent_validation', 'Beräknat förslag kontrolleras separat; okänt är inte godkänt.'),
    ('traceable_method', 'Varje körning redovisar metodversion, profil och effektiva inställningar.'),
)


def shared_principles():
    return dict(version=VERSION, automatic_learning=False,
                principles=[dict(id=k, scope='SHARED_METHOD', description=v) for k,v in PRINCIPLES],
                business_specific=['staff_permissions', 'availability', 'need_windows', 'day_boundaries',
                                   'night_jour_window', 'contract_applicability', 'cost_rates'],
                planning_limits_supported=[1200,1440],
                planning_limits_path='scenario.workspace.unit_rules.planning_limits',
                legal_approval=False)


def _decision(value):
    if not isinstance(value,dict) or set(value)!={'max_whole_duty_minutes','source','confirmed_at'}:
        raise ValueError('Planeringsgränsen kräver max_whole_duty_minutes, source och confirmed_at.')
    limit=value['max_whole_duty_minutes']
    if type(limit) is not int or limit not in (1200,1440):
        raise ValueError('Välj uttryckligen 1200 eller 1440 minuter för högsta hela passlängd.')
    if not isinstance(value['source'],str) or not value['source'].strip():
        raise ValueError('Planeringsgränsen saknar källa.')
    when=value['confirmed_at']
    if not isinstance(when,str) or len(when)!=10:
        raise ValueError('Planeringsgränsen saknar giltigt beslutsdatum.')
    try:date.fromisoformat(when)
    except ValueError:raise ValueError('Planeringsgränsen saknar giltigt beslutsdatum.') from None
    return deepcopy(value)


def resolve_policy(profile,scenario,config,daily_rest_parameters):
    """config is the importer's private copy, never a persisted profile."""
    unit_rules=(scenario.get('workspace') or {}).get('unit_rules') or {}
    selected=None;origin=None
    if 'planning_limits' in profile:
        selected=_decision(profile['planning_limits']);origin='REVIEWED_BUSINESS_PROFILE'
    if 'planning_limits' in unit_rules:
        # A run-level plan may tighten the reviewed maximum, never loosen it.
        requested=_decision(unit_rules['planning_limits'])
        if selected and requested['max_whole_duty_minutes']>selected['max_whole_duty_minutes']:
            raise ValueError('Scenariot får inte höja verksamhetsprofilens beslutade maxpass.')
        selected=requested;origin='EXPLICIT_PLANNING_SCENARIO'
    if 'max_whole_duty_minutes' in config:
        if not selected or config['max_whole_duty_minutes']!=selected['max_whole_duty_minutes']:
            raise ValueError('Maxpass i konfigurationen saknar överensstämmande dokumenterat beslut.')
    if selected:config['max_whole_duty_minutes']=selected['max_whole_duty_minutes']
    values={k:deepcopy(config.get(k)) for k in ('min_shift','min_free_days','calendar_mode','week_break',
        'min_daily_rest','min_weekly_rest','oncall_cap_28d','break_length','break_threshold',
        'max_continuous_active','max_staff_on_duty','duty_profile','break_policy')}
    result=dict(version=VERSION,profile_id=profile['profile_id'],
                business_id=profile.get('business_id'),data_use=profile.get('data_use'),
                profile_source=deepcopy(profile.get('review_provenance',profile.get('source'))),
                shared_principle_ids=[k for k,_ in PRINCIPLES],
                effective_profile_values=values,
                day_boundaries=deepcopy(daily_rest_parameters),
                planning_limits=dict(status='SELECTED' if selected else 'NOT_SELECTED',
                                     decision=selected,origin=origin,
                                     applies_to='DUTIES_STARTING_IN_PLANNING_PERIOD',
                                     automatic_split=False,legal_approval=False),
                automatic_learning=False,other_business_decisions_inherited=False)
    result['fingerprint']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False,
        separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return result
