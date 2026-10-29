"""Exact-source application of Patricia's common timing decision.

No title matching at runtime, no inferred fixed start, no historical exceptions.
The original windows and source certificate remain unchanged.
"""
from copy import deepcopy
import json
from pathlib import Path
from .flora_jobs import digest

PROFILE_ID = 'flora-original-upload-morning-plan-historical-pass-20261021'
DECISION_HASH = 'a93c200b1a1270fa9455ab4d30fc07cc671391886072adb77c6dc04f60e2e582'
POLICIES = {'MOVABLE_WITHIN_SOURCE_WINDOW', 'UNIQUE_SOURCE_START', 'REVIEW_REQUIRED'}


def _load():
    return json.loads(Path(__file__).with_name('flora_timing_decisions.json').read_text())


def _checked(value):
    if (not isinstance(value, dict) or digest(value) != DECISION_HASH
            or value.get('version') != 'flora-timing-decision/1.0'):
        raise ValueError('TIMING_DECISION_BINDING_MISMATCH: serverbeslutets hash eller version stämmer inte.')
    return value


def _rules(evidence):
    out = {}
    for group in evidence['groups']:
        if group['policy'] not in POLICIES:
            raise ValueError('TIMING_DECISION_BINDING_MISMATCH: okänd tidsregel.')
        for nid in group['need_ids']:
            if nid in out:
                raise ValueError('TIMING_DECISION_BINDING_MISMATCH: dubblerad medlemskoppling.')
            out[nid] = {k:group[k] for k in ('policy','category','reason','group_id')}
            out[nid]['decision_id'] = evidence['decision_id']
            if group.get('event_condition_resolution'):
                out[nid]['event_condition_resolution'] = group['event_condition_resolution']
            if group.get('unresolved_dependency'):
                out[nid]['unresolved_dependency'] = group['unresolved_dependency']
    return out


def _matches_window(evidence, window):
    if (evidence['window_evidence_hash'] != digest(window)
            or evidence['window_binding_id'] != window['binding_id']
            or any(evidence[k] != window[k] for k in
                   ('source_identity','source_file_sha256','profile_id','dataset_id','period'))):
        raise ValueError('TIMING_DECISION_BINDING_MISMATCH: beslutet gäller ett annat käll-/fönsterbevis.')
    rules = _rules(evidence)
    if set(rules) != {n['need_id'] for n in window['needs']}:
        raise ValueError('TIMING_DECISION_BINDING_MISMATCH: behov saknas eller har tillkommit.')
    return rules


def bind(profile):
    if profile.get('profile_id') != PROFILE_ID:
        return profile
    evidence = _checked(_load())
    rules = _matches_window(evidence, profile['window_binding'])
    if set(rules) != set(profile['need_decisions']):
        raise ValueError('TIMING_DECISION_BINDING_MISMATCH: profilens medlemskoppling har ändrats.')
    out = deepcopy(profile)
    out['timing_binding'] = evidence
    for nid, d in out['need_decisions'].items():
        if 'timing_authorization' in d:
            raise ValueError('TIMING_DECISION_BINDING_MISMATCH: en annan tidsbindning finns redan.')
        d['timing_authorization'] = rules[nid]
    return out


def strip_verified(profile):
    """Verify the exact server overlay, then undo only that overlay for base hash."""
    out = deepcopy(profile)
    if 'timing_binding' not in out:
        if out.get('profile_id') == PROFILE_ID:
            raise ValueError('TIMING_DECISION_BINDING_MISMATCH: obligatoriskt serverbeslut saknas.')
        return out
    evidence = _checked(out.pop('timing_binding'))
    rules = _matches_window(evidence, out['window_binding'])
    if set(rules) != set(out['need_decisions']):
        raise ValueError('TIMING_DECISION_BINDING_MISMATCH: fel behovsmängd.')
    for nid, d in out['need_decisions'].items():
        if d.pop('timing_authorization', None) != rules[nid]:
            raise ValueError('TIMING_DECISION_BINDING_MISMATCH: tidsbehörigheten har ändrats.')
    return out


def case_rules(case):
    """Check modeled permissions against pinned evidence again before export."""
    meta = case.get('integration', {})
    marker = meta.get('timing_binding')
    if marker is None:
        return {}
    evidence = _checked(_load())
    if marker != {'decision_id':evidence['decision_id'], 'decision_hash':DECISION_HASH}:
        raise ValueError('TIMING_DECISION_BINDING_MISMATCH: modellens beslutsbevis har ändrats.')
    window = meta.get('original_window_binding', {})
    if window != {'binding_id':evidence['window_binding_id'], 'locked_by_default':True}:
        raise ValueError('TIMING_DECISION_BINDING_MISMATCH: modellens fönsterbindning har ändrats.')
    return _rules(evidence)
