# Native interaction acceptance

This Draft separates implementation contracts from raw exploratory receipts.
The original research snapshot is retained outside the shipping diff; existing
Git history is unchanged. Small, bounded fixture records used by verdict tests
live under scripts/fixtures/replacement-recovery.

- The private character prototype has two completed physical appends and four
  reached negative stops: A20/B0, A221/B0, App veto and App focus handoff. These
  are experimental observations, not default-path acceptance.
- The default in-flight text path can still type into a changed focused field.
  No per-character isolation or rollback guarantee is made.
- Full-value reads, selected replacement, continuation, bounded traversal and
  native video must be reviewed and released independently with their tests.
- Text requests preserve the already-focused field: they do not run Focus
  shortcuts or unlock the phone, including short text. A locked-field error
  stops input without unlock or replay. A batch starting with text defers Focus
  for the whole batch, and dispatches a later launch only after text succeeds.
  A mock-runner regression covers both cases through the production dispatch.
- Resource-based video must carry the selected instance; it must never read
  the startup daemon as a fallback for another selected phone.

The current integration branch compiles and passes 912 server library tests
and 255 MCP library tests (one ignored in each); this does not replace the
remaining integration, host, physical and default-path acceptance lanes.
