# Reviewed per-need co-planning

The availability strategy supports an explicit `bb-concurrency-policy/1.0`
scenario in a private reviewed profile. Existing profiles without this policy
retain their original no-overlap assignment constraints. No activity title,
customer label or source completion status enables co-planning automatically.

A policy must state its schema, mode (`EXPLICIT_PER_NEED_COMPATIBILITY`),
status (`SCENARIO` or `CONFIRMED_BY_USER`), decision ID, source, business ID,
canonical source identity and exact period endpoints. Every need must have a
`concurrency` decision with `mode`, matching `decision_id`, `source_ref`,
`source_row_sha256` and `reason`. Unknown policy/decision fields are rejected.
The row checksum is SHA-256 of the complete normalized source need serialized
as UTF-8 JSON with sorted keys, compact separators, no NaN, and Unicode retained.

- `SHARED`: this person may perform overlapping shared activity workflows.
- `EXCLUSIVE`: this person is unavailable for any other activity during it.
- `UNCLASSIFIED`: remains exclusive; its unresolved classification is reported.

Each need still has its own complete interval, required distinct performers,
profession/skills, eligibility and input blockers. Different people's permissions
are never pooled. Shared workflow minutes are not additive personal work time.
The model's cumulative encoding uses the number of potential shared needs as
an auxiliary capacity; it does not create an operational concurrency limit.
All shift, absence, rest, jour and exact personal Ar constraints are unchanged.

The adapter verifies the policy's owner, period and source identity, plus each
classification's source-row checksum. Changed descriptions require new review,
even if someone updates the overall source identity. The policy is profile data,
not a request option. A client cannot inject it through workspace decisions.
Policy and implementation identities participate in job cache identity; changing
a reviewed policy creates a new job and preserves the previous stored result.

The independent validator imports no solver, model or policy adapter. It verifies
policy provenance itself, then recalculates simultaneous assignments, exclusive
collisions, distinct staffing, actual active presence and other rules. Exports
include peak simultaneous workflows by person, overlap examples, the sum of
source need durations, and personal assignment minutes counted once by interval
union. These are separate measures. They do not verify a customer-time percentage
or paid net hours. Practical attention, location and travel remain UNKNOWN.

A scenario policy never approves a business schedule. All output remains
review-required. Old profiles and other businesses receive no inherited policy.
Private profiles, source descriptions and actual assignments must stay outside
Git. Activation requires deploying matching code and binding the reviewed private
profile to the intended dataset variant; code deployment alone enables no sharing.

Private profile packaging supports both the existing `gzip+base64` encoding and
an optional `xz+base64` encoding in `bb-compressed-profile/1.0`. Packaging does not
alter the decoded profile or its canonical identity. XZ decoding limits both
output size and dictionary memory and rejects incomplete or additional streams.
Older files can be repackaged without changing their bindings, profile contents
or stored job results. Keep exact original file backups for deployment rollback.
