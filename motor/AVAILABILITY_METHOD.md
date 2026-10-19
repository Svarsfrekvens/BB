# Reviewed availability strategy

`engine_strategy: reviewed-availability/1.0` adds per-person availability and
per-need eligibility to the existing authenticated `/api/engine/jobs` flow.
The previous Flora strategy remains available with its existing profiles.
The server registry chooses the business, purpose, dataset variant and method.
A request cannot choose another business's profile or a file path.

This version is a **development method for an exact reviewed input version**.
It does not claim that a business is ready for arbitrary future periods.
Changed staff, windows, source rows, periods or workspace decisions require
explicit profile review. They fail before queueing instead of using stale facts.

## Input and profile

The browser reads a workbook into `bb-input/1.0`. Its byte-identical source
archive stays in workspace storage. Transfer metadata carries the file's SHA256;
the profile also binds all normalized source facts by a canonical identity.
The shared route and app gateway both accept at most 8 MiB; the legacy Flora
route retains its 6 MiB limit. Every source occurrence remains represented.

A private `bb-analysis-input-profile/1.0` contains the reviewed input domains,
permission sets, dated availability, historical duties and sourced decisions.
It cannot contain selected duties, assignments, saved results or search hints.
Source rows are read from the submitted input for each run. Original source,
confirmed corrections and scenario changes remain distinct.

The profile builder performs pure validation without an optimizer:

```sh
python -m bb.availability_profile \
  --input /private/normalized-input.json \
  --case /private/reviewed-case.json \
  --output /private/new-version-profile.json \
  --business-id VERIFIED_WORKSPACE_BUSINESS_ID \
  --profile-id REVIEWED_VERSION_ID \
  --review-source 'Explicit reviewed decisions and source references' \
  --reviewed-at YYYY-MM-DD
```

Add `--compressed` to package a deterministic, size-bounded gzip/base64 JSON
envelope for a private server file. Checksums and decoded sizes are verified;
encoding does not change the canonical profile identity and is not encryption.
Repeated source prose stays in the original input/archive rather than the case.

Files stay outside the repository with mode 0600. Creation does not register a
workspace, modify Render, deploy, submit a job or approve a schedule. Installation
uses the existing private server registry and requires the actual verified
workspace identity. A missing business never falls back to Flora.

## Search and accounting

- All needs have a coverage decision, including needs with no verified performer.
  Unknown permission means no assignment, while the need stays in the denominator.
- Confirmed availability is required. Historical presence is not availability;
  a vacancy is staffing demand, never an employee or an implicit temporary booking.
- Co-planning is opt-in through a source-bound, per-need reviewed policy.
  Compatible workflows may share an eligible person; exclusive and unclassified
  activities retain that person's full capacity. Missing policy keeps legacy
  no-overlap behavior. See [CONCURRENCY.md](CONCURRENCY.md) for decision binding,
  independent checks, unique personal minutes and practical unknowns.
- Ordinary source Ar is preserved exactly per person. The whole mutable duty
  minimum includes retained original duties. Whole typed Jo and its source demand
  are handled separately from active work.
- Frozen history, individual conditions, fixed daily/weekly phases and rolling
  limits remain explicit. Numerical exception/rest profiles do not verify their
  local operational applicability.
- Coverage is optimized first. The time objective runs only after maximum whole
  coverage is proved and while the total search deadline permits it. FEASIBLE
  and a time limit never imply an optimal result or real-world impossibility.
- The authenticated capability request uses the uploaded dataset as a routing
  hint within that workspace's registered variants. This strategy recommends a
  300-second search budget; the app opts in, displays it and preserves the request
  identity across reloads. The legacy strategy keeps its existing app budget.
- This version supports the explicitly reviewed no-break scenario. Ar is reported
  as gross active time; paid net, costs and customer-time percentage stay unknown.
  It does not convert omitted breaks into zero unpaid break time.

## Result and verification

The worker emits `bb-engine-run/1.0`, with job/input/profile/method identities,
original-source evidence, actual selected rows, assigned/unassigned needs and
per-need omission reasons. The independent validator recalculates eligibility,
capacity, whole duties, source Jo, person hours, rest and inherited breaches.
New violations, historical deviations and unresolved controls stay separate.
Every result remains review-required and business approval remains false.

```sh
cd motor
python -m unittest discover -s tests -v
```

Tests use invented businesses and source rows. Actual uploads and private
profiles must never be added to fixtures or Git. API/worker tests exercise
three isolated profiles and reject cross-business access and changed input.
