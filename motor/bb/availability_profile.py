"""Build a private reviewed development profile; never install, deploy, or search.

Usage: python -m bb.availability_profile --help
The input is the app's normalized transfer contract, not a workbook or result.
"""
import argparse
from copy import deepcopy
from datetime import date
import json
import os
from pathlib import Path

from .availability_import import STRATEGY, prepare_case, source_identity
from .profile_encoding import encode_profile


def build_profile(raw, case, *, business_id, profile_id, review_source, reviewed_at, decision_ledger=None):
    if not all(isinstance(v, str) and v.strip() for v in (business_id, profile_id, review_source, reviewed_at)):
        raise ValueError('Verksamhet, profil-ID, granskad källa och granskningsdatum krävs.')
    date.fromisoformat(reviewed_at)
    if raw.get('source_archive') is not None:
        raise ValueError('Använd appens överföringsunderlag utan originalarkiv.')
    case = deepcopy(case)
    # Source prose and complete cells stay in the input/archive. Preserve all
    # operative decisions and references; avoid duplicating the workbook here.
    for need in case.get('needs', []):
        for key in ('original_fields', 'effective_fields', 'description', 'description_html'):
            need.pop(key, None)
    for segment in case.get('source_schedule_segments', []):
        segment.pop('source_fields', None)
    profile = dict(schema_version='bb-analysis-input-profile/1.0', profile_id=profile_id,
        business_id=business_id, data_use='development', engine_strategy=STRATEGY,
        source_identity=source_identity(raw), reviewed_case=case,
        review_provenance=dict(source=review_source, reviewed_at=reviewed_at),
        partial_input_policy='KEEP_ALL_NEEDS_BLOCK_UNVERIFIED_ASSIGNMENTS',
        decision_ledger=decision_ledger or [])
    prepare_case(raw, profile, {'absence_mode': 'preserve'})
    return profile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('input','case','output','business-id','profile-id','review-source','reviewed-at'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--decision-ledger')
    parser.add_argument('--compressed',action='store_true',help='Create a bounded gzip+base64 JSON envelope for a private server file.')
    args=parser.parse_args()
    path=Path(args.output).resolve()
    checkout=Path(__file__).resolve().parents[2]
    if not Path(args.output).is_absolute() or path.is_relative_to(checkout):
        parser.error('Utfilen måste ligga på en absolut privat sökväg utanför kodarkivet.')
    def read(value):
        source=Path(value)
        if source.stat().st_size>64*1024*1024:
            raise ValueError('Granskningsfilen överskrider verktygets storleksgräns.')
        return json.loads(source.read_text())
    profile=build_profile(read(args.input),read(args.case),business_id=args.business_id,
        profile_id=args.profile_id,review_source=args.review_source,reviewed_at=args.reviewed_at,
        decision_ledger=read(args.decision_ledger) if args.decision_ledger else None)
    # Refuse to overwrite any retained profile; permissions never default public.
    with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as stream:
        stream.write(json.dumps(encode_profile(profile) if args.compressed else profile,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(profile_id=profile['profile_id'],source_identity=profile['source_identity'],
                          status='PREPARED_NOT_REGISTERED',optimizer_started=False)))


if __name__=='__main__':main()
