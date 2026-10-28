"""Evidence for duty grouping. Source-cell collections never prove whole duties."""
from collections import defaultdict

WORK_CODES = {'Ar', 'Jo', 'Kl', 'Öv'}
VERIFIED = 'VERIFIED_WHOLE_DUTY'
UNVERIFIED = 'UNVERIFIED_GROUPING'


def occasions(case, raw):
    source = {r['id']: r for r in case['references']['import']['segments']}
    expected = defaultdict(list)
    for row in source.values():
        if row.get('whole_duty_id') and row['code'] in WORK_CODES:
            expected[row['whole_duty_id']].append(row)
    overlays = {p['id']: p['source_segment_id'].rsplit('-', 1)[0]
                for kind in ('planned_oncall_replacements', 'planned_active_replacements')
                for p in case.get('integration', {}).get(kind, [])}
    groups = defaultdict(list)
    for row in raw.get('segments', []):
        if row['code'] not in WORK_CODES:
            continue
        original = source.get(row['id'], {})
        explicit = original.get('whole_duty_id')
        # Separate namespaces prevent a generated ID from impersonating an explicit group.
        kind = 'explicit' if explicit else 'collection'
        key = explicit or overlays.get(row['id']) or (row['id'].rsplit('-', 1)[0] if original else row['id'])
        groups[(row['person'], kind, key)].append(row)
    out = []
    for (person, kind, key), rows in sorted(groups.items()):
        originals = expected.get(key, []) if kind == 'explicit' else []
        signature = lambda r: (r['id'], r['person'], r['code'], r['start'], r['end'])
        verified = bool(originals) and sorted(map(signature, rows)) == sorted(map(signature, originals))
        out.append(dict(person=person, id=key, grouping_kind=kind, start=min(r['start'] for r in rows),
                        end=max(r['end'] for r in rows), rows=rows,
                        grouping_status=VERIFIED if verified else UNVERIFIED,
                        unknown_whole_duty_rules=[] if verified else ['whole_duty_minimum','whole_duty_maximum','inter_duty_rest','active_only_duty_over13h','night_jour','jour_compensation'],
                        grouping_basis='EXPLICIT_SOURCE_MEMBERSHIP' if verified else 'TECHNICAL_COLLECTION_ONLY',
                        combined_jour={'Ar','Jo'} <= {r['code'] for r in rows}))
    return out


def global_limit(case):
    """An unselected or unversioned decision must never become PASS."""
    from ..rule_policy import VERSION, _decision
    envelope = case.get('rule_policy', {})
    policy = envelope.get('planning_limits', {})
    maximum = case['config'].get('max_whole_duty_minutes')
    if policy.get('status') != 'SELECTED' or envelope.get('version') != VERSION:
        return None
    try:
        decision = _decision(policy.get('decision'))
    except ValueError:
        return None
    return maximum if type(maximum) is int and maximum == decision['max_whole_duty_minutes'] else None
