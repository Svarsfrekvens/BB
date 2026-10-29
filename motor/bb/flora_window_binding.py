"""Server-only transfer of a reviewed window decision to an exact source snapshot.

The checked-in evidence contains reference coordinates and row hashes, not private
need payloads. No source window or personnel count is rewritten. The mounted
profile is immutable; only its returned, hashed worker snapshot is narrowed.
"""
from copy import deepcopy
import json
from pathlib import Path

from .flora_jobs import digest

PROFILE_ID = 'flora-original-upload-morning-plan-historical-pass-20261021'
EVIDENCE_HASH = '3ae2937e057d7385e6cc692754290841c02a3c5e45317558502056799c3dd184'


def _load_evidence():
    return json.loads(Path(__file__).with_name('flora_window_binding.json').read_text())


def _checked(evidence):
    if (not isinstance(evidence, dict) or digest(evidence) != EVIDENCE_HASH
            or evidence.get('version') != 'flora-original-window-binding/1.0'
            or evidence.get('window_semantics') != 'EXECUTION_WINDOW'):
        raise ValueError('Fönsterbevisets version eller hash stämmer inte.')
    return evidence


def bind_profile(profile, dataset_id):
    """Called after the existing exact source binding and server profile selection."""
    if profile.get('profile_id') != PROFILE_ID:
        return profile
    from .business_profiles import BusinessProfileError
    try:
        evidence = _checked(_load_evidence())
        if any(profile.get(k) != evidence[k] for k in ('profile_id', 'business_id', 'data_use', 'source_identity', 'source_file_sha256')):
            raise ValueError('Fönsterbeviset gäller en annan profil eller källa.')
        if digest(profile) != evidence['base_profile_hash']:
            raise ValueError('Profilen har ändrats efter fönstergranskningen.')
        if dataset_id != evidence['dataset_id']:
            raise ValueError('Fönsterbeviset gäller ett annat dataset.')
        decisions = profile['need_decisions']
        ids = [n['need_id'] for n in evidence['needs']]
        if len(set(ids)) != len(ids) or set(ids) != set(decisions):
            raise ValueError('Fönsterbeviset omfattar inte exakt profilens behov.')
        flex_ids = {k for k, d in decisions.items() if d['flex']}
        if flex_ids != set(evidence['inactive_flex_need_ids']):
            raise ValueError('Profilens analysutvidgningar har ändrats.')
        out = deepcopy(profile)
        for d in out['need_decisions'].values():
            if d.get('window_semantics') is not None:
                raise ValueError('En annan fönsterbindning finns redan.')
            d.update(window_semantics='EXECUTION_WINDOW', flex=False)
        out['window_binding'] = evidence
        from .flora_timing_decisions import bind
        return bind(out)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise BusinessProfileError('WINDOW_BINDING_MISMATCH',
            'Serverns fönsterbevis matchar inte den granskade profilen.', 503) from exc


def verify_input(raw, profile):
    """Repeat the whole binding in preflight and worker, before case construction.

    The inverse projection checks that no other original profile decision changed.
    A client-provided metadata field never creates or selects this binding.
    """
    if 'window_binding' not in profile:
        return
    evidence = _checked(profile['window_binding'])
    from .flora_timing_decisions import strip_verified
    original = strip_verified(profile)
    original.pop('window_binding')
    flex_ids = set(evidence['inactive_flex_need_ids'])
    for nid, d in original['need_decisions'].items():
        if d.get('window_semantics') != 'EXECUTION_WINDOW' or d.get('flex') is not False:
            raise ValueError('Fönsterbindningen har ändrats eller analysutvidgningar aktiverats.')
        del d['window_semantics']
        d['flex'] = nid in flex_ids
    if digest(original) != evidence['base_profile_hash']:
        raise ValueError('Profilbesluten matchar inte fönsterbeviset.')
    from .availability_import import source_identity
    md = raw['metadata']
    if (source_identity(raw) != evidence['source_identity']
            or any(md.get(k) != evidence[k] for k in ('source_file_sha256','business_id','dataset_id','data_use'))):
        raise ValueError('Källuppgifterna matchar inte fönsterbeviset.')
    period = evidence['period']
    if (md.get('planning_period_id') != period['id'] or md.get('timezone') != period['timezone']
            or [p for p in md['periods'] if p['id'] == period['id']]
            != [{k:period[k] for k in ('id','start','end')}]):
        raise ValueError('Perioden matchar inte fönsterbeviset.')
    rows = [n for n in raw['customer_needs'] if period['start'] <= n['date'][:10] <= period['end']]
    indexed = {n['need_id']:n for n in rows}
    expected = {n['need_id']:n for n in evidence['needs']}
    if len(indexed) != len(rows) or set(indexed) != set(expected):
        raise ValueError('Fönsterbeviset saknar entydig täckning av periodens behov.')
    for nid, n in indexed.items():
        proof = expected[nid]
        source = proof['original_source_reference']
        if (digest(n) != proof['input_row_sha256']
                or n.get('source_ref') != proof['app_reference_literal']
                or any(n.get('source_fields', {}).get(k) != source[v]
                       for k,v in [('source_id','source_id'),('source_sheet','sheet'),('source_row','row')])):
            raise ValueError('Ett källbehov eller dess radreferens matchar inte fönsterbeviset.')
