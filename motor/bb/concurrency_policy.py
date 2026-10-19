"""Explicit reviewed concurrency decisions; no activity-name inference or IO."""
from hashlib import sha256
import json

SCHEMA = 'bb-concurrency-policy/1.0'
MODES = {'SHARED', 'EXCLUSIVE', 'UNCLASSIFIED'}
POLICY_KEYS = {'schema_version', 'mode', 'status', 'decision_id', 'source',
               'business_id', 'source_identity', 'period_lo', 'period_hi'}
DECISION_KEYS = {'mode', 'decision_id', 'source_ref', 'source_row_sha256', 'reason'}


def source_row_digest(row):
    return sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def reviewed_modes(case):
    """Legacy cases remain exclusive; a new policy must classify every need."""
    needs = case.get('needs', [])
    if 'concurrency_policy' not in case:
        if any('concurrency' in n for n in needs):
            raise ValueError('Samplaneringsklassning saknar ett uttryckligt beslutsunderlag.')
        return None
    policy = case['concurrency_policy']
    if (not isinstance(policy, dict) or set(policy) != POLICY_KEYS or policy.get('schema_version') != SCHEMA
            or policy.get('mode') != 'EXPLICIT_PER_NEED_COMPATIBILITY'
            or policy.get('status') not in ('SCENARIO', 'CONFIRMED_BY_USER')
            or any(not _text(policy.get(k)) for k in ('decision_id', 'source', 'business_id'))
            or not _hash(policy.get('source_identity'))
            or policy.get('period_lo') != case['period']['lo']
            or policy.get('period_hi') != case['period']['hi']):
        raise ValueError('Samplanering kräver ett källbelagt beslut för rätt period och verksamhet.')
    integration = case.get('integration')
    if integration and (policy['business_id'] != integration.get('business_id')
                        or policy['source_identity'] != integration.get('source_identity')):
        raise ValueError('Samplaneringsbeslutet tillhör ett annat underlag eller en annan verksamhet.')
    result = {}
    for need in needs:
        decision = need.get('concurrency')
        if (not isinstance(decision, dict) or set(decision) != DECISION_KEYS
                or decision.get('mode') not in ('SHARED', 'EXCLUSIVE', 'UNCLASSIFIED')
                or decision.get('decision_id') != policy['decision_id']
                or not _text(decision.get('source_ref')) or not _text(decision.get('reason'))
                or not _hash(decision.get('source_row_sha256'))):
            raise ValueError('Insatsen saknar fullständig samplaneringsklassning: '+need['id'])
        row = need.get('original_submitted_row')
        if row is not None and (row.get('need_id') != need['id']
                                or decision['source_row_sha256'] != source_row_digest(row)):
            raise ValueError('Samplaneringsklassningen stämmer inte med källraden: '+need['id'])
        result[need['id']] = decision['mode']
    return result
