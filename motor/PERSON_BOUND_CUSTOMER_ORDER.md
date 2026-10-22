# Person-bound customer order in the reviewed scheduling experiment

The opt-in private profile setting `config.sequential_individual_customers=true`
requires an explicit `config.non_individual_customer_ids` list. It is supported
only with `break_policy=EXPLICIT_NO_BREAK_SCENARIO`. Without the setting, saved
jobs and existing profile behavior are unchanged.

For each selected need, the solver now selects the required number of named
workers and proves that each worker has a containing active `Ar` interval.
That interval may be fixed, reassigned as one reviewed unit, a selected shift,
or the active part of a selected whole-duty candidate. A worker's individual
needs for different customers cannot overlap. Two needs for the same customer
retain their previous co-planning permission; a need marked `exclusive` remains
exclusive against every other need. Listed non-individual customer groups keep
their reviewed sharing behavior unless the need is explicitly exclusive.

The independent minute validator consumes the solver's named assignments. It
rejects absent, duplicate, unknown or off-duty executors and reports any
cross-customer person-minute overlap. The result has a separate
`sequential_individual_customers` rule state. Other practical issues such as
attention within one customer, location and travel remain open observations.

This model must not be activated by a client-supplied flag. The protected
profile owns the decision and its organization/source binding. A changed
profile produces a new job identity; previous runs and approval state remain
unchanged. The model does not widen any source need window or create staff
availability. A source-window exception requires its own documented decision
and separate input/profile version.
