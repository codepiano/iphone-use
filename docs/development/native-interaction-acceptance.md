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
- Short locked-field typing and text-before-launch batches need explicit
  compatibility coverage before the aggregate is mergeable.
- Resource-based video must carry the selected instance; it must never read
  the startup daemon as a fallback for another selected phone.

The current integration branch compiles and passes 912 server library tests
and 255 MCP library tests (one ignored in each); this does not replace the
remaining integration, host, physical and default-path acceptance lanes.
