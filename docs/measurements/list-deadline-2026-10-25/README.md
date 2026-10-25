# Handler-wide list execution deadline

Four virtual-time router scenarios failed on the previous candidate: queue wait,
in-flight mutation, a later read after an acknowledged swipe, and optional
recovery capture. `before-deadline.txt` retains the failures. These tests advance
the actual 80-second timer without waiting that long or touching a real phone.

One handler-entry deadline now covers queue, preparation, traversal and optional
recovery. It is passed into the existing traversal reserve rules, native signed
admission and the outer work timeout. A ready underlying error cannot bypass the
expired deadline. Expiry returns list_deadline/HTTP 504 with not_sent for zero
sent mutations, partial for confirmed prefixes and unknown for unacknowledged
sends. Current phone work may still finish; no action is automatically replayed.

The collection engine checkpoints completed-page rows and page counts without
reimplementing row filtering/deduplication. A hard timeout retains those as
historical partial observations, complete:false and no actionable snapshot.
Owner/privacy changes still strip that checkpoint at response publication.
MCP's error compaction preserves partial rows in text even with structured
output disabled. Missing data is not interpreted as a complete or empty list.

Optional recovery cannot extend the same deadline. It uses the minimum of its
normal two-second budget and time remaining, shares native scope admission,
and reports image_omitted:request_deadline while preserving an earlier completed
lookup result. A local scope/deadline refusal is not broken capture hardware.
Two intermediate failed checks are retained: ready IO failure could win over
an elapsed timer; capture could mark the device unhealthy at that boundary.
The final post-IO scope/clock checks cover both.

`software-checks.json` retains exact summaries/log hashes: 892 server unit tests
(one ignored), 241 related HTTP tests including six deadline cases, 246 MCP unit
tests (one ignored), 28 stdio cases, pinned 1.96.0 workspace Clippy and final
candidate daemon/MCP builds. Timer, preparation, in-flight uncertainty, confirmed
checkpoint, recovery-health and late-publication cases all pass.

`simulator-results.json` records 39 passing combined checks through the actual
XCTest runner, daemon and stdio MCP on an isolated iPhone 17 / iOS 27 Simulator.
The queue probe uses native typing in an owned fixture to hold the runner lock.
The waiting list returns 504/list_deadline in 80,005 ms, not_sent/retry_safe:true,
zero native dispatches and zero swipes. The original input then finishes
naturally, with **no private hold or owner transition** used to stop anything;
no delayed traversal source request or swipe follows lock release.

The workload's full 6,015-character value is verified by an App-owned character
count and CryptoKit SHA-256 receipt, independently of controller acknowledgements
and AX. `fixture-verification.json` retains fixture source/binary/receipt hashes.
The oracle is debounced and enabled only for the dedicated queue workload prefix.
This is not a model-throughput benchmark or comparative performance result.

All four earlier Simulator attempts remain in simulator-attempt-1..4.json:
a boolean variable shadowed the lookup helper before setup; guarded clear could
not establish the fresh field precondition after an interrupted gesture; AX
attribute readback returned 512 characters rather than a full-value oracle;
an instrumented short-budget run produced an uncertain chunk. That last timing
cause was not conclusively isolated; prefix-only observation avoids adding
oracle work to the baseline cases. No input timeout or safety assertion was
loosened. Setup now restarts its owned fixture without replaying the uncertain
clear, and full-value verification comes from the App-owned receipt.

The final run also observes the AX response length of 512 alongside the verified
6,015-character field. The full-value/truncation reading issue is **unresolved**;
the result must not be represented as complete AX reading or input loss.

All listed source/daemon/MCP hashes and the fixture receipt were independently
checked. The Simulator is absent from simctl inventory; ephemeral state/runtime
folders were removed, and cleanup reports no errors.
The preceding e06679a candidate passed PR checks 40148746956, security
40148746864 and Simulator smoke 40148746873; those checks apply only to that SHA.

## Limits

This is the cooperative handler execution budget, not a hard real-time network
response SLA. Existing native operations can finish after the controller drops
its transport. Client transport disconnect/server-side cancellation, other
opaque actions/flow/suite budgets, physical devices and installed hosts still
need separate acceptance. Timer tests use Tokio test-util as a dev-only feature;
no test clock API is added to production HTTP. Full competitive superiority is
not established by these checks.
