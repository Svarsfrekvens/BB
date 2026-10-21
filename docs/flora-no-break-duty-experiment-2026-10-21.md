# Flora: local duty-domain experiment, 2026-10-21

This branch adds an opt-in **experimental** `EXPLICIT_NO_BREAK_SCENARIO` mode to the Flora method. The existing solver-placed-break mode remains the default and its saved results are untouched. The experiment models active-only candidate duties from 4 through 13 hours, including 6, 7, and 8 hours. A combined work/on-call/work duty is a separate whole duty: its overall span is not cut to the active-only 13-hour limit.

In the new mode, source breaks must be absent, the solver generates no breaks, ordinary targets must be supplied in the same no-break minute accounting, and any new active-only candidate longer than 13 hours is rejected. The independent validator rejects inserted breaks and active-only duties above 13 hours. The run is identified as `joint-shifts-no-break-experiment/v0`; no-break applicability is reported as unknown for contractual/legal review, not silently approved.

Local synthetic tests cover 4, 6, 7, 8, and 13-hour active-only duties without breaks; 3 and 14 hours are rejected. A fixed 24-hour work/on-call/work duty remains intact and without a generated break. This does **not yet** add a new optional 24-hour work/on-call/work candidate to the optimizer. Historical approved pass identities are source evidence only, and sick-time rows never become work or on-call.

Two local probes used the same saved Flora request and the reviewed historical-pass profile, copied into memory. Both removed the profile's mathematical reference breaks and recomputed ordinary targets from source `Ar` gross minutes; neither changed the installed profile or sent a job to the remote engine. The first kept the existing 55 candidate windows; the second widened 54 windows from a 10.5-hour maximum to 13 hours within their existing clock windows. The one more restricted window was retained.

| Probe | Covered source needs | Ordinary active minutes | Temporary active minutes | Break minutes | Independent checked status |
|---|---:|---:|---:|---:|---|
| No-break; original candidate windows | 1,451 / 1,451 | 30,930 | 8,275 | 0 | PASS |
| No-break; 54 widened windows | 1,451 / 1,451 | 30,930 | 8,450 | 0 | PASS |

Both searches returned `FEASIBLE` within a 12-second budget per objective stage, **not** an optimum for temporary time. The temporary-minute totals must not be interpreted as a proven benefit or loss from widening windows. They are also not directly comparable with the old break-deducting result. A future optional whole-duty candidate needs joint `Ar`/`Jo` segments, person eligibility, on-call cap, rest, free-day, capacity, break policy, output identity, and independent validation before it can be compared fairly.

Verification: 506 existing motor tests passed (6 skipped), followed by 5 focused no-break tests after the final synthetic jour case was added. No live profile, saved motor result, business workspace, or published app was modified.
