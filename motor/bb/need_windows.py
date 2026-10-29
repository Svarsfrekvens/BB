"""Typed input windows; legacy absence remains absence, never inferred evidence."""
TYPES = ('EXECUTION_WINDOW', 'START_WINDOW')


def resolve(source, reviewed):
    for value in (source, reviewed):
        if value is not None and value not in TYPES:
            raise ValueError('Okänd tidsfönstertyp; underlaget behöver granskas.')
    if source is not None and reviewed is not None and source != reviewed:
        raise ValueError('Tidsfönstrets betydelse motsäger den granskade profilen.')
    return source if source is not None else reviewed


def complete(needs, *, required=False):
    """Frontend v1 requires all period needs when a contract is present."""
    values = [resolve(n.get('window_semantics'), None) for n in needs]
    if any(v is not None for v in values) and any(v is None for v in values):
        raise ValueError('Blandade typade och okända behovsfönster saknar ett komplett tidsfönsterkontrakt.')
    if required and any(v is None for v in values):
        raise ValueError('NEED_WINDOW_CONTRACT_REQUIRED: uttrycklig fönstertyp saknas i källan och den granskade profilen.')
    return bool(values) and all(v is not None for v in values)


def bounds(semantics, left, right, duration, period_start, period_end):
    """Inclusive start bounds, half-open execution/period. No source rewriting."""
    resolve(semantics, None)
    if (any(type(x) is not int for x in (left, right, duration, period_start, period_end))
            or duration <= 0 or right <= left):
        raise ValueError('Tidsfönster och duration måste ha giltiga hela minuter.')
    last = right if semantics == 'START_WINDOW' else right - duration
    first, last = max(left, period_start), min(last, period_end - duration)
    if first > last:
        raise ValueError('Behovet ryms inte i sitt tidsfönster och sin period.')
    return first, last


def row(need, identity, stamp):
    return dict(need_id=identity, window_semantics=need['window_semantics'],
                source_window_start=stamp(need['source_window_start']),
                source_window_end=stamp(need['source_window_end']),
                duration_minutes=need['duration'], personnel_count=need['count'])


def export(needs, identity, stamp, *, required=False):
    if not complete(needs, required=required) and not required:
        return {}
    ids = [identity(n) for n in needs]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('NEED_WINDOW_CONTRACT_INVALID: saknade eller dubbla behovs-ID.')
    return {'need_window_contract': {'version': 'bb-need-window/1.0',
            'needs': [row(n, i, stamp) for n, i in zip(needs, ids)]}}


def check_joint(case, raw=None):
    """Fail before queueing and again at export; never type legacy evidence by guess.

    The importer already checks source/profile coverage. Repeat against its frozen
    input here so a truncated or changed internal case cannot certify a subset.
    """
    source, modeled = case['source_needs'], case['needs']
    complete(source, required=True)
    def indexed(rows):
        ids = [n['id'] for n in rows]
        if any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('NEED_WINDOW_CONTRACT_INVALID: saknade eller dubbla behovs-ID.')
        return dict(zip(ids, rows))
    sources, models = indexed(source), indexed(modeled)
    if sources.keys() != models.keys():
        raise ValueError('NEED_WINDOW_CONTRACT_INVALID: modellerade behov skiljer sig från källbehoven.')
    meta = case.get('integration', {})
    mapping = meta.get('need_id_map', {})
    exported_ids = [mapping.get(i, i) for i in sources]
    upload = case.get('import_provenance', {}).get('upload')
    if upload is not None:
        expected = [n['need_id'] for n in upload['customer_needs']
                    if case['origin'][:10] <= n['date'][:10] < case['end'][:10]]
        if len(set(expected)) != len(expected) or len(exported_ids) != len(expected) or set(exported_ids) != set(expected):
            raise ValueError('NEED_WINDOW_CONTRACT_INVALID: kontraktet täcker inte exakt planeringsperiodens behov.')
    if len(set(exported_ids)) != len(exported_ids):
        raise ValueError('NEED_WINDOW_CONTRACT_INVALID: dubblerad källkoppling.')
    fields = ('window_semantics', 'source_window_start', 'source_window_end', 'duration', 'count', 'domains')
    unresolved_locks = []
    for i, n in sources.items():
        if any(n.get(k) != models[i].get(k) for k in fields):
            raise ValueError('NEED_WINDOW_CONTRACT_INVALID: kontraktet motsäger det modellerade behovet.')
        if type(n.get('count')) is not int or n['count'] < 1:
            raise ValueError('NEED_WINDOW_CONTRACT_INVALID: ogiltigt personalantal.')
        first, last = bounds(n['window_semantics'], n.get('source_window_start'), n.get('source_window_end'), n['duration'], 0, case['horizon'])
        if meta.get('original_window_binding', {}).get('locked_by_default') and first != last:
            # Neither an analysis classification nor interval boundaries prove
            # an approved start or permission to move within that interval.
            unresolved_locks.append(i)
        if not n.get('domains') or any(a < first or b > last or a > b for a, b in n['domains']):
            raise ValueError('Startdomänen motsäger det typade källfönstret: '+i)
    if unresolved_locks:
        raise ValueError('NEED_TIMING_DECISION_REQUIRED: '
                         +str(len(unresolved_locks))
                         +' behov saknar verifierad låst starttid eller uttryckligt flyttbeslut. Intervall är inte flytträtt.')
    if raw is not None:
        placed = indexed(raw.get('placements', []))
        for i, p in placed.items():
            n = sources.get(i)
            if n is None or type(p.get('start')) is not int or not any(a <= p['start'] <= b for a, b in n['domains']):
                raise ValueError('NEED_WINDOW_CONTRACT_INVALID: placering utanför verifierat startintervall.')


def check_exported_placements(contract, placements):
    """Check the actual JSON-facing evidence, including independently assigned rows."""
    from datetime import datetime
    windows = {n['need_id']: n for n in contract['needs']}
    for p in placements:
        n = windows.get(p['need_id'])
        if n is None or any(p.get(k) != v for k, v in n.items()):
            raise ValueError('NEED_WINDOW_CONTRACT_INVALID: exporterad placering motsäger kontraktet.')
        a, b = datetime.fromisoformat(p['start']), datetime.fromisoformat(p['end'])
        left, right = datetime.fromisoformat(n['source_window_start']), datetime.fromisoformat(n['source_window_end'])
        if b <= a or a < left or (a > right if n['window_semantics'] == 'START_WINDOW' else b > right):
            raise ValueError('NEED_WINDOW_CONTRACT_INVALID: exporterad placering ligger utanför källfönstret.')


def placement(need, stamp):
    if need.get('window_semantics') is None:
        return {}
    return {k: v for k, v in row(need, '', stamp).items() if k != 'need_id'}
