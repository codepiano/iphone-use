# Scoped list traversal and visual recovery

Four new router regressions failed on the prior candidate: a private list could
start native work; source data read across owner/private changes survived and
could lead into a swipe; an acknowledged swipe was not represented as an
interrupted native prefix; and a queued body retained old list UI. The synthetic
failures are preserved in `before-list-scope.txt`.

## Contract

List calls freeze the owner/privacy incarnation before queue waits and reuse
the native signed-send admission guard. Read-only setup/page reads/retries can
be cancelled on revocation; a current native mutation retains its transport
for an acknowledgement. No later swipe or source read is admitted. A queued
owner A-to-B-to-A name cannot reacquire permission. Revocation does not mark a
healthy device broken. Scope loss removes rows, targets, candidates, snapshots
and diagnostic pixels, with a final response-body publication fence.

The separate `swipes` counter records acknowledged whole gestures even when a
later settle/read is revoked. Native confirmed/uncertain counts also include
preparatory controls. An interrupted confirmed prefix is partial/retry_safe:false;
uncertainty stays unknown, and zero dispatched mutations remain not_sent. A
successful later read does not retroactively prove a failed gesture's delivery.

Selected missing/ambiguous/blocked lookups and no-row/no-progress/duplicate-page
or failed traversals reuse the existing two-second, bounded fresh-image helper.
Partial rows, coverage, original errors and delivery counts remain intact.
A found target, end marker or intentional page-budget stop does not capture.
The original owner/privacy scope governs capture; the standard opt-out still
works. MCP delivers exactly one image block, with no base64 duplication, and
keeps acknowledged/uncertain delivery text in full/slim/off output modes.

## Evidence

`software-checks.json` retains exact log hashes/summaries: 892 server unit tests
(one ignored), 234 HTTP checks in the combined run, and updated list recovery
checks increasing the distinct covered HTTP total to 235. Final list scope and
recovery files pass five and four tests. MCP passes 246 unit tests (one ignored)
and 27 stdio tests; an additional rerun of the updated stdio case exercises both
list tools, all three output modes and confirmed/uncertain delivery. Pinned
1.96.0 workspace Clippy and candidate daemon/MCP builds pass.

The first Simulator attempt passed 37 cases but failed its last unannotated
assertion. Its result is retained in `simulator-attempt-1.json`. The counter
recognized only session-prefixed source paths while production used `/source`;
`attempt-1-analysis.json` retains the supporting events and labels the diagnosis
as inference. The corrected harness counts both paths, records the receipt and
includes assertion context/tracebacks. No product assertion was relaxed.

The final `simulator-results.json` records 38 passing cases through the actual
XCTest runner, daemon and stdio MCP on an isolated iPhone 17 / iOS 27 Simulator.
Both list diagnostics return one PNG with zero swipes and preserve not-found or
incomplete coverage. After a real native swipe ACK, private on/off returns a
partial receipt with one confirmed swipe, zero uncertain and no later source
read; the receipt is retained separately. The preceding 35 binding, privacy,
recovery, host-protocol and native-video cases also pass.

Every listed source and daemon/MCP binary hash was independently rechecked.
The Simulator is absent from simctl inventory and ephemeral runtime/state
folders were deleted; cleanup reports no errors. These are not physical-device
or installed-host rendering results. The preceding 8988f16 candidate passed
PR checks 40146001113, security 40146001063 and Simulator smoke 40146001053.

## Remaining work

Real scrolling apps, native/WebView mixed lists, physical USB/Wi-Fi and old iOS,
installed hosts/packages, long sessions and paired task trials still require
acceptance. Overall queued traversal deadlines and server-side termination after
transport disconnect need separate audit; dropping a client request is not proof
the server stopped. Current native operations may finish, and no rollback or
per-event immediate-stop guarantee is made. The broader goal remains incomplete.
