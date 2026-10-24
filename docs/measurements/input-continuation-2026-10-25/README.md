# Input continuation: candidate validation

This follow-up adds cross-call continuation and strengthens native input on top
of the [first binding candidate](../input-target-2026-10-24/README.md). It is not
physical-device, release-package or comparative performance acceptance.

## Verified behavior

The final recorded daemon and actual XCTest runner pass 13 cases on a disposable
iPhone 17 simulator, iOS 27.0, Xcode 27.0 (27A266a). The exact source, daemon and
runner executable hashes are in `simulator-attempt-5.json`.

- A bound input is read back, cleared and appended in its original field.
- Switching to a second field with the same label or switching apps refuses
  the old target. Session replacement and another native command invalidate it.
- A 500-character draft completes across 200 + 200 + 100 character portions,
  without reselection; the final field equals the full synthetic draft.
- Clicking into the middle of that long field and clearing it empties the whole
  field. The old Backspace loop left text after the caret. Native clear now
  selects all in the original app, rechecks the bound field, deletes once and
  checks the result; it never taps to regain focus or retries uncertain input.
- Ownership release and native focus/session changes refuse continuation.
- The fixture changes focus during a 200-character chunk: field A receives 20
  characters and B receives 180. The daemon reports 0 confirmed / 200 uncertain,
  issues no continuation, and sends no second chunk.
- Another owner takes control during a live native chunk. The old request stops
  after its acknowledged 200 characters. Completion does not reuse its original
  takeover header to steal the lease back, and no continuation is issued.

The 13-case run cleaned up its daemon, disposable credentials and simulator.
No personal daemon, phone, launch agent or Simulator keyboard setting was changed.

## Software entry checks

`validation-summary.json` records the parsed results and log hashes:

- server library: 883 passed, 1 ignored, both with local test concurrency 2 and
  in a final default-thread run after the compilation/simulator jobs ended;
- related HTTP binaries: 34 passed (20 batch outcomes, 4 input-schema tests,
  1 guarded-input entry test, 9 continuation tests with additional subcases);
- MCP library: 232 passed, 1 ignored; actual stdio: 15 passed;
- Swift: 278 checks; Home contract: 7 passed;
- iOS Simulator and unsigned device-target compilation pass.

HTTP cases cover safe token rotation, read-only inspection, wrong owners,
release/reacquisition, takeover, expiry, session replacement, other mutations,
focus loss, transport uncertainty and cancellation. A request that loses its
owner while waiting for the real runner mutex is refused for both short and
long text, without a target lookup, unlock, focus change or text dispatch.
The renewal cases also exercise an in-flight request outlasting its lease:
renewal keeps the same ownership incarnation if no handoff occurred.

Real stdio checks read `tools/list`, verify token-only input is discoverable,
and call `phone_type` in full/slim output modes. They check the forwarded owner,
exact continuation body and preserved token/partial verdict. Mixing a token
with new text is refused before contacting the daemon.

Two earlier default-thread library runs failed existing coordination/readiness
checks; their counts and log hashes are retained in the summary. The unchanged
coordination case passed 10 isolated rechecks. The final default-thread run also passes. No existing assertion was relaxed
or test skipped to obtain these results.

## Reproduce

Build the candidate daemon with `heavy-cargo`, then:

```bash
IPU_RUNNER_DERIVED_DATA=/tmp/ipu-continuation/DerivedData bash runner/build.sh --simulator
python3 scripts/test-input-target-simulator.py \
  --xctestrun /tmp/ipu-continuation/DerivedData/Build/Products/<printed-name>.xctestrun \
  --daemon target/debug/iphone-use \
  --out /tmp/ipu-continuation-acceptance-new
```

The harness creates a fresh simulator and a separately named daemon instance,
state directory, runtime directory and loopback listener. It uses synthetic
text, signed runner requests and disposable agent credentials. It never replays
an unknown action. Tokens are redacted from logs and disposable credential files
are removed during cleanup. `--daemon` is optional for the native-only checks.

## Earlier simulator attempts

All attempts are retained:

1. Six native cases passed; the daemon's default instance name collided with an
   existing daemon's PID guard. Startup was refused. The harness now uses an
   isolated instance and runtime directory; the existing daemon was not stopped.
2. Native input and 500-character continuation passed. The next preparation
   exposed the real mid-caret clear defect and stopped on `guarded clear incomplete`.
3. The select-all correction and mid-chunk postflight check passed 12 cases.
4. The reviewed ownership gate and synthesis-fallback policy passed 12 cases.
5. The final lease-renewal correction and live-owner-takeover case passed all 13.

## Limits

Counts on continuation responses describe the current call, not cumulative
model rounds or an entire task. The guarded native postflight detects an observed
focus/app change; this is not proof of per-character isolation or of detecting a
rapid away-and-back focus change. Physical phones, old iOS versions, domestic
host applications and full agent task comparisons still require acceptance.
Cancellation coverage drops a router request future after token consumption;
it does not establish device stop latency after a TCP disconnect or host-side
cancellation. Those end-to-end stop checks remain open. Runtime continuation
tokens never become replayable flow steps; a draft records a review todo for
the entire original input and its clear behavior.
