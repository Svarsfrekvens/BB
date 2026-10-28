"""Typed input windows; legacy absence remains absence, never inferred evidence."""
TYPES = ('EXECUTION_WINDOW', 'START_WINDOW')


def resolve(source, reviewed):
    for value in (source, reviewed):
        if value is not None and value not in TYPES:
            raise ValueError('Okänd tidsfönstertyp; underlaget behöver granskas.')
    if source is not None and reviewed is not None and source != reviewed:
        raise ValueError('Tidsfönstrets betydelse motsäger den granskade profilen.')
    return source if source is not None else reviewed


def complete(needs):
    """Frontend v1 requires all period needs when a contract is present."""
    values = [resolve(n.get('window_semantics'), None) for n in needs]
    if any(v is not None for v in values) and any(v is None for v in values):
        raise ValueError('Blandade typade och okända behovsfönster saknar ett komplett tidsfönsterkontrakt.')
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


def export(needs, identity, stamp):
    if not complete(needs):
        return {}
    return {'need_window_contract': {'version': 'bb-need-window/1.0',
            'needs': [row(n, identity(n), stamp) for n in needs]}}


def placement(need, stamp):
    if need.get('window_semantics') is None:
        return {}
    return {k: v for k, v in row(need, '', stamp).items() if k != 'need_id'}
