# Atomic short input and cancellation validation

This candidate adds `ipu:atomicText` for ordinary short `text` actions (up to
200 Unicode scalars, without an explicit typing budget or continuation). One
native request binds the focused nonsecure field, optionally clears it, types
and rechecks the same target. It does not assert that a caller's earlier screen
snapshot is current. Human keyboard routes remain separate.

A current runner rejects single-line newlines before clearing; TextView input
can retain line breaks. Whole long text also requests multiline preflight when
this capability is present. Explicit `phone_type.clear` is forwarded to the same
text action. Continuation tokens cannot be combined with clear or new text.
Older compatible text routes stop on failed clearing rather than appending.

The native clear check no longer mistakes literal text equal to a placeholder
for an empty field. Clearing and subsequent typing remain one compound outcome:
a target change after clearing is unknown, not a safe whole-request replay.

MCP `notifications/cancelled` now drives the request cancellation token. A
foreground operation still waiting on its HTTP response is dropped and reported
as unknown; it is never resent. A result already ready is preserved. Cancellation
before dispatch reports not_sent. Background tasks retain their separate task
cancellation API. A synthesized device chunk already in flight can still finish.

## Software checks

- Server library: 883 passed, 1 ignored, including a final default-thread run.
- Related HTTP entry tests: 38 passed. Four short-input tests include native
  single/batch success, definite refusal, ambiguous failure, lost transport,
  legacy short/long clear failures, multiline preflight before clearing and
  capability renegotiation after session replacement.
- MCP library: 232 passed, 1 ignored; actual stdio: 16 passed. The new cancellation
  case observes a real daemon HTTP request, cancels through JSON-RPC, checks the
  unknown verdict promptly, and observes the connection close while the MCP
  process stays alive. Exactly one HTTP request is recorded.
- Swift: 278 checks passed; iOS Simulator and unsigned device-target compilation
  passed. This is compilation evidence, not physical-device acceptance.

## Earlier combined runs

All simulator results are retained as immutable run records:

- Attempt 1 passed 19 cases, including atomic short clear in one native request,
  text equal to its placeholder, secure-field refusal, single-line newline
  refusal before clear, multiline readback and mid-input focus change. It also
  observed raw TCP disconnection with default and 6000 ms budgets: one native
  chunk completed, no owner-release cleanup was required, and a quiet period
  was observed about 4.1 seconds after disconnection (including 0.75 s of required
  quiet observation). Bounded-input stop causality is not established by that
  observation alone. The MCP notification path was not exercised in that run.
- Attempt 2 passed 18 cases, then a receiver read used a native handle invalidated
  by health recovery's session replacement after unknown input. The harness now
  reads both receiver fields in a single fresh AX snapshot and establishes the
  client session before allocating raw handles for a new setup.
- Attempt 3 passed four native cases but failed to focus a field immediately
  after app resumption. The harness now requires a nonblank stable screen before
  choosing fresh targets after launch/resume. It does not repeat the failed tap.
- Attempt 4 returned a stable but blank frame at fixture readiness, before input.
  The fixture now renders a visible title, and the harness waits for a nonblank
  stable scene within a bounded deadline instead of treating the first blank
  sample as a final readiness verdict.

These runs use disposable simulators, separately named daemon instances and
private runtime/state directories. They contain only synthetic text. Credentials
are redacted and temporary processes, credential files and simulators are removed.
No result here is physical-device or comparative task-performance acceptance.


## Final combined run

`simulator-attempt-5.json` records 20 passed cases through the actual daemon,
XCTest runner and, for cancellation, the actual stdio MCP binary. Its source and
three executable hashes match the recorded candidate. The simulator is iPhone 17,
iOS 27.0 with Xcode 27.0 (27A266a). Cleanup completed without errors.

The run retains all prior target/continuation checks and verifies:

- Ordinary short clear/type uses one `/ipu/text` request, with no separate target
  lookup or raw keyboard fallback. The final field is read back exactly.
- Text identical to the field's placeholder is cleared correctly rather than
  treated as empty and appended to.
- Single-line newlines are refused before clearing; a secure field refuses input;
  a TextView retains `one\ntwo` exactly.
- A short input that changes focus during synthesis reports unknown without
  another request. Receiver fields contain 20 and 37 characters, respectively.
- A foreground MCP `notifications/cancelled` sent during a real native chunk
  returns unknown / retry_safe:false. Exactly that current native chunk finishes;
  no later chunk or retry occurs. Idle is observed 4124 ms after notification,
  including the required 750 ms quiet observation window.

Separate raw TCP observations recorded one completed chunk after disconnection
with both default and 6000 ms budgets, without owner-release cleanup. Their
observed quiet times are 4091 and 4118 ms, including the same quiet window.
Those are observations in this simulator/transport, not universal latency bounds;
for bounded input they do not isolate cancellation from the typing budget.

Reproduce with the exact `.xctestrun` printed by `runner/build.sh --simulator`:

```bash
python3 scripts/test-input-target-simulator.py \
  --xctestrun /path/to/IPhoneUseRunner_iphonesimulator.xctestrun \
  --daemon target/debug/iphone-use --mcp target/debug/iphone-use-mcp \
  --out /tmp/ipu-short-input-acceptance-new
```

Remaining acceptance includes real host apps, USB/Wi-Fi physical phones, old iOS,
per-character/rapid away-and-back focus changes, and stop latency outside this
simulator setup. Background task cancellation remains its own API. Separate
editing-key and `set_value` paths still require review. No full task/model
performance comparison against the reference product has been run.
