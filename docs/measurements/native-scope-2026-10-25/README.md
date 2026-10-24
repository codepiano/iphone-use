# Physical native request admission

Two new router regressions failed on the prior candidate: session initialization
continued into Home after scope loss, and fresh launch continued into launch
after a termination acknowledgement. The third check already passed: a single
in-flight native acknowledgement retained success. Synthetic failure output is
preserved in `reproduction-before.txt`.

## Contract

Scoped non-text native actions now admit each signed runner request immediately
before execute, after signing. Owner/private revocation rejects later requests,
including read-only retries and follow-up native mutations. Read-only setup may
be cancelled; an approved mutation retains its transport so its acknowledgement
can arrive. Successful completed actions keep their original success.

A ledger records mutation-capable request approvals, valid native reply envelopes
and explicit definite-unsent rejections. It stores counts, not UI, arguments or
credentials. Session/settings/element lookups are metadata, not user mutations.
These acknowledgement counts are not app postconditions or proof a UI goal was
achieved. A request with no usable acknowledgement remains uncertain.

If the logical action stops after acknowledged sub-operations and has no uncertain
mutation, the receipt is action_interrupted/partial, retry_safe:false with
native_mutations_confirmed and native_mutations_uncertain. A request stopped
before any native mutation remains not_sent; mixed uncertainty remains unknown.
Permission revocation does not label the device broken. The batch preserves its
whole-step counts separately from the interrupted native prefix.

MCP's failed-batch text includes native acknowledgement counts even when no
whole step completed and structured output is off. No whole-action replay is
authorized. Non-agent/human control keeps its existing behavior; a task-local
scope is installed only for the scoped action and its native focus preparation.

## Evidence

`software-checks.json` retains log hashes and exact summaries: 892 server unit
tests (one ignored), 217 HTTP cases, 233 MCP unit tests (one ignored), 26 stdio
cases, and workspace Clippy with the CI toolchain 1.96.0 and `-D warnings`.
A separate rerun confirms all three native-scope tests, including single/batch
and owner/private variants. Candidate daemon/MCP debug builds pass.

The preceding PR CI at `17fd39a` exposed an alert-wait regression: active-private
reads returned 409 instead of the established 423. This candidate restores 423
for observing batches and passes all 16 wait-for-evidence checks; blind input
scope refusals retain 409. The failed CI log hash is retained, not counted as a
passing checkpoint.

`simulator-results.json` records 31 passing actual XCTest runner/daemon/stdio
cases on an isolated iPhone 17 / iOS 27 Simulator. The new fresh-launch case
observes the termination acknowledgement, changes privacy on/off, and verifies
one confirmed native sub-operation, zero uncertain and zero later launch
requests. All 30 previous input/continuation/cancellation/recovery/host-protocol
cases also pass. The exact source and daemon/MCP hashes were independently
rechecked. The Simulator is absent from simctl inventory; private runtime/state
folders were deleted and cleanup reports no errors. Runner build interruption
at teardown is the deliberate termination of its long-running test server.

All fixtures and Simulator resources are disposable, not personal phone data.

## Limits

The admission guard covers the timed signed runner path in this request scope.
Spawned/background work needs its own explicit scope; system/vault/intent/device
service paths, whole flow/suite authority across HTTP requests, log retention,
physical modes, actual hosts and release/paired task acceptance remain separate
work. Current native operations may finish; no per-event immediate-stop or
rollback guarantee is made. The broader competitive objective is incomplete.
