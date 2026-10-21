"""Run a local, hypothetical four-week repeat on a future calendar period.

The copied source roster, needs, and candidate windows are scenario assumptions.
This script does not establish future staff availability or save an engine job.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from bb.flora import check_case, solve_case
from experiments.replay_flora_approved_duties import build_replay_case


def build_rolling_case(submitted, profile, examples, start_date):
    case, held = build_replay_case(submitted, profile, examples)
    old_start = date.fromisoformat(case['origin'][:10])
    start = date.fromisoformat(start_date)
    if start <= old_start or (start - old_start).days % 28:
        raise ValueError('The future scenario must start a positive whole number of four-week cycles later.')
    end = start + timedelta(days=28)
    case['origin'] = datetime.combine(start, datetime.min.time()).isoformat(timespec='minutes')
    case['end'] = datetime.combine(end, datetime.min.time()).isoformat(timespec='minutes')
    period = case['integration']['period']
    period.update(id=f'ROLLING4-HYPOTHESIS-{start}',start=start.isoformat(),
                  end=(end-timedelta(days=1)).isoformat())
    # Never present the original uploaded input digest as the digest of a
    # future input file. This is a deterministic scenario fingerprint only.
    historical_digest = case['integration'].pop('input_sha256')
    case['integration']['historical_source_input_sha256'] = historical_digest
    case['integration']['scenario_fingerprint'] = sha256(
        f'ROLLING4_HYPOTHESIS|{historical_digest}|{start}'.encode()).hexdigest()
    case['scenario_override']['rolling_four_week_hypothesis'] = (
        'Historical Flora needs, locked source rows and candidate clock windows '
        'are repeated for a calendar test; future availability is unverified.')
    # The period's 15-hour clock windows can contain a 13-hour active duty.
    # This widens only the 54 less-restricted candidate maxima; the one
    # seven-hour source restriction and four held-out 11-hour examples stay.
    widened = 0
    for candidate in case['candidates']:
        if not candidate['id'].startswith('REPLAY-') and candidate['max_length'] == 630:
            candidate['max_length'] = 780
            widened += 1
    check_case(case)
    return case, held, widened


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('submitted','profile','examples','summary'):
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--start',required=True,help='Future Monday, e.g. 2026-11-23')
    parser.add_argument('--seconds',type=int,default=20)
    args = parser.parse_args()
    read = lambda path: json.loads(path.read_text(encoding='utf-8'))
    case, held, widened = build_rolling_case(
        read(args.submitted),read(args.profile),read(args.examples),args.start)
    result = solve_case(case,seconds=args.seconds,workers=1)
    whole_ids = {c['id'] for c in case['whole_duty_candidates']}
    generated = [s for s in result['schedule']['segments']
                 if s['pass_id'] and s['pass_id'].startswith('generated:')]
    active_only = [s for s in generated
                   if s['pass_id'].removeprefix('generated:') not in whole_ids]
    durations = Counter(round(
        (datetime.fromisoformat(s['end'])-datetime.fromisoformat(s['start'])).total_seconds()/3600,2)
        for s in active_only)
    selected_whole = {s['pass_id'] for s in generated
                      if s['pass_id'].removeprefix('generated:') in whole_ids}
    summary = dict(scenario='HYPOTHETICAL_ROLLING_FOUR_WEEKS',
        period=case['integration']['period'],historical_source_only=True,
        future_availability_verified=False,actual_future_needs_verified=False,
        business_schedule_approved=False,local_only=True,
        source_or_business_data_changed=False,solver_status=result['solver_status'],
        checked_status=result['validation']['checked_status'],
        covered_needs=result['after']['fully_covered_needs'],
        total_needs=result['after']['total_needs'],
        ordinary_active_minutes=result['after']['ordinary_net_minutes'],
        temporary_active_minutes=result['after']['temporary_net_minutes'],
        oncall_minutes=result['after']['jour_minutes'],
        break_minutes=result['after']['break_minutes'],
        heldout_historical_patterns=len(held),selected_whole_duties=len(selected_whole),
        active_only_generated_durations_hours=dict(sorted(durations.items())),
        widened_candidate_maxima=widened,
        unknown_rule_ids=sorted({u['rule_id'] for u in result['validation']['unknowns']}),
        violation_rule_ids=sorted({v['rule'] for v in result['validation']['violations']}),
        objective_stages=result['solver']['phases'],
        scenario_fingerprint=case['integration']['scenario_fingerprint'])
    args.summary.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{summary['covered_needs']}/{summary['total_needs']} repeated needs, "
          f"{summary['selected_whole_duties']} whole duties; check {summary['checked_status']}; "
          f"{args.summary}")


if __name__=='__main__':
    main()
