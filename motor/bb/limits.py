"""Konfigurerbara storlekstak. Inte verksamhetsregler.

Default behåller dagens beteende. Explicit payload eller miljövariabel
kan höja taket för en kontrollerad körning. Ogiltiga värden avvisas.
Motorn är auktoritativ; klienten varnar mot samma default.
"""
from __future__ import annotations

import os

DEFAULT_MAX_OCCURRENCES = 1600
DEFAULT_MAX_CANDIDATE_SHIFTS = 10000
DEFAULT_MAX_SUPPORT_COMBINATIONS = 120000

# Högsta tillåtna konfiguration. Ovanför detta fail-closed även vid explicit värde.
CEILING_MAX_OCCURRENCES = 4000
CEILING_MAX_CANDIDATE_SHIFTS = 20000
CEILING_MAX_SUPPORT_COMBINATIONS = 250000

SYNC_MAX_SOLVE_SECONDS = 300
ASYNC_MAX_SOLVE_SECONDS = 900
SOLVE_MAX_SECONDS = 900

_ENV_OCC = 'BB_MAX_OCCURRENCES'
_ENV_CAND = 'BB_MAX_CANDIDATE_SHIFTS'
_ENV_SUP = 'BB_MAX_SUPPORT_COMBINATIONS'


def _parse_int(raw, name):
    if raw is None or raw == '':
        return None
    if type(raw) is bool:
        raise ValueError(f'Ogiltig storleksgräns: {name}.')
    if type(raw) is float:
        if raw != int(raw):
            raise ValueError(f'Ogiltig storleksgräns: {name}.')
        raw = int(raw)
    if type(raw) is int:
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s or not s.lstrip('-').isdigit():
            raise ValueError(f'Ogiltig storleksgräns: {name}.')
        return int(s)
    raise ValueError(f'Ogiltig storleksgräns: {name}.')


def _bounded(value, default, ceiling, name):
    if value is None:
        return default
    if type(value) is not int or value < 1 or value > ceiling:
        raise ValueError(f'Ogiltig storleksgräns: {name}.')
    return value


def validate_limits_block(limits):
    if limits is None:
        return
    if not isinstance(limits, dict):
        raise ValueError('Ogiltiga storleksgränser.')
    ceilings = {
        'maxOccurrences': CEILING_MAX_OCCURRENCES,
        'maxCandidateShifts': CEILING_MAX_CANDIDATE_SHIFTS,
        'maxSupportCombinations': CEILING_MAX_SUPPORT_COMBINATIONS,
    }
    for key, ceiling in ceilings.items():
        if key in limits and limits[key] is not None:
            _bounded(_parse_int(limits[key], key), None, ceiling, key)


def _from_env(env_name, default, ceiling, name):
    raw = os.environ.get(env_name)
    if raw is None or raw == '':
        return default
    return _bounded(_parse_int(raw, name), default, ceiling, name)


def _from_payload(data, key, default, ceiling, name, env_name):
    block = (data or {}).get('limits') if isinstance(data, dict) else None
    if isinstance(block, dict) and key in block and block[key] is not None:
        return _bounded(_parse_int(block[key], name), default, ceiling, name)
    return _from_env(env_name, default, ceiling, name)


def clamp_solve_seconds(raw, ceiling):
    try:
        value = float(30 if raw is None else raw)
    except (TypeError, ValueError, OverflowError):
        value = 30.0
    return min(float(ceiling), max(1.0, value))


def effective_max_occurrences(data=None):
    return _from_payload(data, 'maxOccurrences', DEFAULT_MAX_OCCURRENCES, CEILING_MAX_OCCURRENCES, 'maxOccurrences', _ENV_OCC)


def effective_max_candidate_shifts(data=None):
    return _from_payload(data, 'maxCandidateShifts', DEFAULT_MAX_CANDIDATE_SHIFTS, CEILING_MAX_CANDIDATE_SHIFTS, 'maxCandidateShifts', _ENV_CAND)


def effective_max_support_combinations(data=None):
    return _from_payload(data, 'maxSupportCombinations', DEFAULT_MAX_SUPPORT_COMBINATIONS, CEILING_MAX_SUPPORT_COMBINATIONS, 'maxSupportCombinations', _ENV_SUP)


def reported_limits(data=None):
    """Server-auktoritativa tak. Default/env om data saknas; annars request-overrides."""
    return dict(
        maxOccurrences=effective_max_occurrences(data),
        maxCandidateShifts=effective_max_candidate_shifts(data),
        maxSupportCombinations=effective_max_support_combinations(data),
        defaultMaxOccurrences=DEFAULT_MAX_OCCURRENCES,
        defaultMaxCandidateShifts=DEFAULT_MAX_CANDIDATE_SHIFTS,
        defaultMaxSupportCombinations=DEFAULT_MAX_SUPPORT_COMBINATIONS,
        source='motor',
        kind='INPUT_OR_SOLVER_SAFETY_LIMIT',
        asyncJobs=os.environ.get('BB_ASYNC_JOBS', '').strip().lower() in ('1', 'true', 'yes', 'on'),
    )
