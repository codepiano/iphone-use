# Action observation scopes

Five HTTP regressions failed before this increment: single/batch final reads
returned UI after private/owner changes; wait_for passed and dispatched later
input; earlier wait observations survived in step results; queued response
bodies exposed UI; and an uncertain native action returned its raw UI diagnostic.
`reproduction-before.txt` retains synthetic failures only.

## API contract

A native action's acknowledgement and its optional observation are independent.
A completed action/batch retains its original success, status and dispatch counts
when its final observation is withheld. No absence or postcondition is inferred
from that omission. A wait_for that did not complete in the original scope stops
later steps, retaining prior applied actions and unsafe whole-batch replay.

Scope checks cover owner incarnation, private generation and active privacy.
Probes, settled reads, alerts and pure waits are cancellable; old requests cannot
start a screenshot prefetch after losing their scope. Non-text actions also
recheck before queued dispatch/unlock. An already dispatched logical action may
finish; this increment does not promise to cancel each physical subrequest inside
an opaque action or to retract data already delivered.

Final UI publication is deferred until after timing/advice serialization. When a
scope is lost, a receipt projection removes tree/delta/snapshot/alert/image,
earlier observations, raw diagnostic messages and flow hints. Status, ok/error,
failed-step/batch outcomes, counts, retry safety and confirmed-clear evidence
remain. Healthy bodies are forwarded unchanged without a second parse/copy;
redaction parses only on scope loss. A body with no usable receipt remains
unknown and unsafe to replay. Recovery omission metadata stays explicit.

MCP includes a scope/observation notice in content before full/slim/off shaping,
including unobserved actions, so a known success is not misread as fresh UI or a
failed mutation. A changed scope requires checking status/current ownership
before new work, not automatic replay.

## Evidence

Server library: 890 passed, 1 ignored. Related HTTP tests: 198 passed
(20 batch outcomes, 34 input settle, 107 auth/HTTP, 17 continuation, 6 observation
scope, 6 capture privacy, 4 recovery, 4 short text). MCP library: 233 passed,
1 ignored; real stdio: 25 passed. Exact CI Clippy 1.96 workspace checks pass.
The first broad run caught an old expectation that a private locator still
performed a lookup and returned 422; private agent input now refuses before
lookup with 409/not_sent. The test now requires that stronger preflight while
capture/handoff errors retain their original statuses. Logs and failed checks
are hashed in `software-checks.json`.
All source tests and fixtures are isolated from personal devices and accounts.

## Actual runner integration

`simulator-attempt-1.json` records 30 passed cases on a disposable iPhone 17 /
iOS 27 Simulator using the candidate daemon, XCTest runner and stdio MCP. The
prior 28 cases remain passing. Single and batch observed input each trigger a
private on/off transition only after the fixture sees real input delivery.
Each result keeps ok:true (and completed/applied_actions:1 for the batch), omits
UI, completes exactly one atomic native text request and independently reads
back the intended text. Listed source and binary hashes match; cleanup and
Simulator deletion were independently verified. This is backend integration,
not physical-device or actual-host acceptance.

## Limits

The new guarantee is per agent input/actions API request. Internal lookup/reveal
transitions within opaque native actions, authority between separate flow/suite
requests, vault/intent/other metadata paths and diagnostic log retention still
need their own audit. Physical devices, actual host UI, downloaded release
artifacts and paired same-device completion/latency trials remain open. The
broader comparative objective is not complete.
