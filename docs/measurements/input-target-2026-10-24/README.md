# Target-bound input: candidate validation

The first candidate (`33afac7`) binds long-text chunks to a live AX field on supporting native
runners. It has not been installed on a physical phone, released, or compared
for task speed against another product.

Device-free checks on this candidate:

- `heavy-cargo test -p server --lib`: 880 passed, 1 ignored.
- `heavy-cargo test -p server --test guarded_text --test agent_actions_outcome --test agent_input_schema`:
  25 passed. The guarded-text entry test covers single/batch requests with
  either a definite rejection or an uncertain transport loss at chunk three.
  It verifies confirmed/uncertain counts, the missing remainder, the original
  runner reason, no target reselection, no replay and no later batch action.
- `bash runner/unit-check.sh`: 269 checks passed.
- `python3 scripts/test-runner-home-check.py`: 7 passed.
- `runner/build.sh --unsigned` and `runner/build.sh --simulator`: compiled
  with the selected Xcode and iOS 27.0 SDK, without device signing.

## Actual XCTest runner on an isolated simulator

`simulator-attempt-4.json` records five passed cases on iOS Simulator 27.0:

1. Target-bound input followed by a separate field-value readback.
2. Clearing the bound field and appending through the same binding.
3. Switching to a second field with the same label rejects the old binding;
   both field values are checked for unintended input.
4. Switching to Home rejects the bound input; the original field is checked
   after returning to the fixture.
5. Creating a new runner session invalidates the old binding.

The JSON records exact native sources, harness and runner executable hashes.
The executable ran inside a disposable simulator, with a fresh per-run signed
channel and no personal daemon or device. Cleanup completed without errors.
These tests exercise native guarded requests; daemon chunk sequencing and
single/batch error shapes are covered separately by the HTTP tests above.
The direct native input strings are short, so this is not a long-document
throughput or timing result.

Reproduce (pass the exact `.xctestrun` printed by the build):

```bash
IPU_RUNNER_DERIVED_DATA=/tmp/ipu-input-build bash runner/build.sh --simulator
python3 scripts/test-input-target-simulator.py \
  --xctestrun /tmp/ipu-input-build/Build/Products/<printed-name>.xctestrun \
  --out /tmp/ipu-input-acceptance-new
```

The script creates and deletes its own simulator. It does not change global
Simulator keyboard settings or operate an already-booted simulator. It saves
synthetic field data and redacts the ephemeral runner token from its log.

## Earlier attempts

Failures are retained alongside the successful run:

- Attempt 1 exhausted a 20-second request budget during the test fixture's
  cold XCTest activation, before input checks. Fixture setup now launches once
  through simctl, and runner requests allow a longer bounded timeout.
- Attempt 2 reached the fixture but could not read its tree. The fixture's
  crash report showed `UIApplicationEvaluateRuntimeIssueForNoSceneLifecycleAdoption`.
  The fixture now uses a Scene delegate. This was a test app defect.
- Attempt 3 passed the first four guard checks, then failed to focus a field
  after resuming the app while using pre-transition element handles. Attempt
  4 re-resolves fields from the fresh hierarchy before choosing the next
  focus target. This does not establish that old handles remain usable across
  an app transition, and no runner click behavior was changed to force focus.

Each attempt cleaned up its disposable simulator. None of these runs proves
physical-device behavior or superiority across full agent tasks. Remaining
work is tracked in [the acceptance matrix](../../development/competitive-acceptance.md).

Later continuation work and its separate evidence are in
[the follow-up report](../input-continuation-2026-10-25/README.md).
