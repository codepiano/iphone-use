# Gesture delivery at actual HTTP/MCP entries, 2026-10-26

The actual `iphone-use serve` binary and an actual stdio `iphone-use-mcp` peer
run against a loopback-only scripted Runner. Its independent request/effect
ledger simulates an effect before returning a W3C error (HTTP 500 or 200) or
closing the connection. A separate refusal control returns HTTP 400/invalid
argument ending in “nothing was sent” without simulating an effect. The Runner
has no device connection. These are protocol integration checks, not UIKit,
XCTest or physical acknowledgement-loss injection.

Both [default MCP output](default-result.json.gz) and
[full MCP output](full-result.json.gz) pass the same 42 scenarios (84 executions):
HTTP tap/swipe/longpress/multi_longpress, actual MCP tap and gesture batches,
success/refusal controls and partially completed batches. Each uncertain action
is posted once; its outcome stays unknown and retry_safe is false. When the
first batch step succeeded and the second is uncertain, applied_actions and
completed retain one, failed_step is one, batch_outcome stays unknown and the
Return suffix is never posted. A refusal at the second step likewise keeps the
whole batch non-retryable while identifying that step as not_sent.

The script additionally checks the native ledger before starting each distinct
trial and after stopping the children, so late native input cannot vanish when
counters are reset. Cleanup confirms both children stopped, the native acceptor
thread/socket closed and temporary credential/runtime directories removed.
Only result/diagnostic logs are eligible for CI artifacts; private state is not.
No reconnect, model or signing command is used.

[Summary](summary.json) records source/script identity and scope. The local run
uses existing validation binaries with their actual hashes. Rust daemon/MCP
source has no changes from their a7981aa source to 05a26fb; their older embedded
Runner is not executed. The CI gate builds both binaries from its current PR
head, then runs `scripts/test-gesture-delivery-entry.py` in both output modes.
Real phone transports, real host behavior, structured=off and comparative tasks
still need separate evidence.

Two preliminary harness failures are retained: [incorrect lock JSON in the
scripted Runner](initial-readiness.json.gz) prevented readiness before input;
[an incorrect batch enum assertion](initial-batch-contract.json.gz) stopped after
34 completed scenarios. The authoritative batch contract requires unknown when
the failed step is uncertain, even with a confirmed prefix. These are harness
corrections, not reported product regressions; earlier harness source versions
were not retained as reproducible test releases.
