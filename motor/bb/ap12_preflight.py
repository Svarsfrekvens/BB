"""Read-only AP12 evidence summary for a saved request and the current profile.

This reports potential source-row identities. It never predicts which rows a
future optimization will choose or approves a transfer.
"""

from datetime import datetime

from .engine_methods import prepare


def pass_mapping_preflight(request: dict, profile: dict, *, saved_profile_hash: str,
                           current_profile_hash: str, input_hash: str) -> dict:
    case = prepare(profile, request)  # Import and profile checks only; no solve.
    if profile.get('engine_strategy') == 'reviewed-availability/1.0':
        return dict(schema_version='bb-engine-pass-preflight/1.0',
                    strategy='reviewed-availability/1.0', input_hash=input_hash,
                    current_profile_hash=current_profile_hash,
                    current_profile_matches_saved_job=current_profile_hash == saved_profile_hash,
                    source_rows_in_period=None, source_rows_excluded=None,
                    possible_pass_evidence=None, applicability='FLORA_ONLY',
                    future_result_guaranteed=False, transfer_approved=False)

    origin = datetime.fromisoformat(case['origin'])
    horizon = case['horizon']
    unit_by_row = {sid: unit['id'] for unit in case['reassignable_temporary_units']
                   for sid in unit['segment_ids']}
    candidate_ids = {candidate['id'] for candidate in case['candidates']}
    decisions = profile['segment_decisions']
    rows = request['input']['schedule_segments']
    counts = {'profile_whole_duty_id': 0, 'reviewed_reassignment_unit': 0,
              'model_candidate_shift': 0, 'unverified': 0}
    excluded = 0
    period_rows = 0
    for row in rows:
        start = (datetime.fromisoformat(row['start']) - origin).total_seconds() / 60
        end = (datetime.fromisoformat(row['end']) - origin).total_seconds() / 60
        if start >= horizon or end <= 0:
            continue
        period_rows += 1
        sid = row['segment_id']
        decision = decisions[sid]
        if decision['mode'] == 'excluded':
            excluded += 1
        elif decision.get('whole_duty_id'):
            counts['profile_whole_duty_id'] += 1
        elif sid in unit_by_row:
            counts['reviewed_reassignment_unit'] += 1
        elif sid in candidate_ids:
            counts['model_candidate_shift'] += 1
        else:
            counts['unverified'] += 1
    return dict(schema_version='bb-engine-pass-preflight/1.0',
                strategy='flora-reassignment/1.0', input_hash=input_hash,
                current_profile_hash=current_profile_hash,
                current_profile_matches_saved_job=current_profile_hash == saved_profile_hash,
                source_rows_in_period=period_rows, source_rows_excluded=excluded,
                possible_pass_evidence=counts,
                reviewed_reassignment_units=len(case['reassignable_temporary_units']),
                candidate_shifts=len(case['candidates']),
                original_breaks=len(case['references']['import']['breaks']),
                future_result_guaranteed=False, transfer_approved=False)
