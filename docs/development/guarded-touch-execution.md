# Guarded touch execution

This fork adds an **opt-in** source-level controller. Existing release tools do
not silently change their taps or cadence. Installing/deploying the fork is a
separate step; this change does not resume any collection task.

The controller imports the independently maintained `pointer-trajectory`
Python package, contract `>=0.4,<0.5`. No planner implementation is vendored or
downloaded at runtime. Install the authorized package from its own checkout into
a dedicated Python environment, rather than changing a running service's Python
environment. Public CI runs the policy tests without that optional dependency;
the four real-planner tests require it and report skips when absent.

## Planning and dispatch

`scripts/guarded_phone.py` consumes fresh logical screen geometry. A tap locates
one exact label/identifier, then calls `generate_tap` / `validate_tap`. Default
landing is center-biased within an inset of 15%, contact lasts 60–140 ms, and
drift is bounded to 1 logical point. Each action gets a new system-entropy seed,
recorded privately for diagnosis. No approach path from the last button is made.
`drag`, `scroll` and `flick` use `generate_gesture` / `validate_gesture`.
These are engineering presets, not a measured human model or a guarantee against
application restrictions. Pressure/contact-area synthesis is not implemented.

The daemon's new action is:

```json
{
  "type": "touch_path",
  "snapshot": "fresh-full-screen-token",
  "element": 1,
  "path": {
    "viewport": {"width": 430, "height": 932},
    "samples": [
      {"x": 140, "y": 220, "t_ms": 0},
      {"x": 140, "y": 220, "t_ms": 17},
      {"x": 141, "y": 220, "t_ms": 100}
    ],
    "hold_before_ms": 0,
    "hold_after_ms": 0
  }
}
```

Send to `POST /agent/input?return=delta`, or use the same fields with
`kind:touch_path` in MCP `phone_run_steps`. Coordinates are **logical points**,
not normalized fractions or screenshot pixels. A fresh snapshot is mandatory;
`element` additionally binds a tap to one current target. For movement, omit
`element` but keep the snapshot. The daemon re-reads the tree before dispatch.

The guarded controller additionally sends an opt-in `context` on the single
HTTP action (raw MCP `touch_path` keeps its existing strict full-tree contract):

```json
{"context":{"application":"大众点评","present":["美食排行","美食餐厅"],"absent":["吃喝玩乐指南"]}}
```

Before reading, it reserves the existing owner lease with
`POST /agent/owner {"claim":true}`. This does not start Runner, read the screen,
change a privacy hold or take over another owner. The context's snapshot must
match the daemon's own last read, younger than five seconds, still in the same
owner/privacy epoch, with no intervening Runner POST. Unknown/expired baselines
stop without an automatic refresh/retry. Single HTTP actions are the supported
entry point; an intervening batch scope reset intentionally invalidates a cached
baseline.

The daemon independently reads again and checks the exact application root,
positive/negative page anchors and their frames/states, the original unique
semantic target and its complete row, and all visible rows intersecting the
contact corridor (segment bounds plus two logical points). The original target
can move to a different row index when unrelated rows appear, but cannot be
replaced, moved, duplicated, hidden or disabled. New warnings, alerts and
recognized verification/rate-limit/empty-result text anywhere stop the contact.
Other controls are still checked for occlusion immediately before dispatch.
Unrelated countdown text outside these areas may change; arbitrary stale
snapshots are not accepted. Paths without `context` retain the original exact
full-snapshot check. Neither mode retries unknown or refused deliveries.

The whole path has 2–512 samples, strictly increasing integer times starting at
zero, 10–16000 ms total, at most 10000 ms movement and at most 3000 ms per hold.
The live viewport must match exactly; paths are not stretched on rotation.
Snapshot-bound samples must remain inside their target, avoid other touch
controls, and target a visible, enabled element. Occlusion tests are deliberately
conservative; they can refuse uncertain layouts. There is no occlusion override
or automatic re-targeting/reveal in this path.

The existing Runner's `ipu:timedDragPath` capability is required. The daemon
converts relative sample intervals into a **single** W3C touch source: position,
down, timed movement/pauses, up. It never compresses to the old 16 equal-duration
drag stops. Ordinary agent leases, privacy generations, blocked-app policy,
action limits and alert checks still apply. The browser `/control` endpoint
rejects these paths because its short acknowledgement budget is inappropriate.
Delivery failure is not replayed through another implementation.

## Checkpointed controller

Use the Python class from an authorized task, or its one-step CLI. The CLI
requires `IPHONE_USE_URL`, `IPHONE_USE_AGENT_TOKEN`, `IPHONE_USE_OWNER`, an explicit
private state directory, an exact accessibility application label and stable
item identity. Tokens stay in memory, not arguments/checkpoints. Plain HTTP is
restricted to loopback; remote origins require HTTPS. Redirects are refused.

Example **input document** for a navigation step in a disposable fixture:

```json
{
  "step_id": "open-details",
  "request": {"kind": "tap", "locator": {"label": "Next", "kind": "Button"}},
  "before": {"present": ["Next"]},
  "after": {"present": ["Details"], "absent": ["Loading"]}
}
```

With the dependency and updated daemon installed, run
`python scripts/guarded_phone.py step --state <private-task-dir> --app <exact-app-label> --item <stable-id>`
and supply that document on stdin. This is an actual action, not a dry run.
`finish` takes `{"verified":{"present":["independent business-result anchor"]}}`
on stdin and independently reads the item's final result. Use a specific
collection/result anchor: an unchanged title or the transport receipt alone does
not prove that a business write succeeded. The helper does not infer collection
membership. There is deliberately no unattended list runner.

The local plugin also ships `scripts/run-guarded.sh --owner <stable-task-owner>`.
Its remaining arguments are the same `step` / `finish` CLI arguments above.
This launcher uses a dedicated planner environment at
`~/.local/share/iphone-use-guarded/venv` (or `IPHONE_USE_GUARDED_PYTHON`) and
reads the selected native daemon's LaunchAgent configuration in memory. A
credential is borrowed only for that same local origin/port; a different origin
requires its own explicit credential. Nothing is printed or put in arguments.
The launcher neither starts services nor resumes a checkpoint. The underlying
raw MCP tap tools retain their original semantics; installing this fork alone
does not make an unguarded tap use trajectory planning. Repetitive third-party
work must use the guarded entry point as the bundled skill specifies.

The same task's processes must share the state directory. A nonblocking file
lock rejects competing calls, while daemon owner leases govern other tasks.
The task checkpoint binds the application, daemon origin and owner. It stores
hashed item/step identities, counts, seed and reason codes, never screen contents,
entered text or credentials. Its write is fsynced **before** sending input.

For every action the controller:

1. Waits for its persisted cadence deadline and confirms drivable status.
2. Requires two fresh observations with matching explicit page anchors and
   unchanged anchor geometry/state, viewport and intended tap target or text
   focus. Unrelated countdowns/carousels can change. The latest full snapshot
   still binds dispatch; stale snapshots and occlusion remain hard refusals.
   Empty/partial screens, changed app and system alerts stop it.
3. Sends one action, then requires two matching observations of its explicit
   postcondition. An unsettled response alone never causes the action to repeat.
4. Requires an independent business postcondition at `finish_item` before a new
   item can begin. Completed item identities cannot be dispatched again. Stable
   step IDs also prevent repeating a verified action after a caller crash before
   it recorded the return. Keep these IDs stable across process restarts; do not
   generate new IDs or seeds to force a retry.

Defaults, configurable through the Python `Pacing` class:

| Limit | Default |
| --- | --- |
| After a verified action | 2–3.5 seconds before the next action |
| Between completed items | at least 10 seconds |
| Round | 3 independently verified items, then 30 extra seconds (40 total) |
| Action budget per item | 12 |
| Observation polling / deadline | 1 second / 20 seconds |

Observation and execution time add to these intervals. These defaults are
conservative task settings, not known safe limits for any third-party app.
Short text insertion is supported into one observed focused nonsecure field;
it does not clear/replace, split a paste into typing, or submit automatically.
Focus can still change during an in-flight native text segment; this controller
does not claim per-character isolation. See the upstream review before adopting
the pending target-bound text work.

Visible verification/rate-limit markers or recognized empty-result messages,
an HTTP error, transport loss, timeout, missing/ambiguous target, an exhausted
budget, or interruption latch the checkpoint **paused**. Recognition is heuristic
and text-based; it cannot identify every challenge or distinguish every benign
message. No automatic verification solving, unlock, reconnect, retry, unpause,
or fallback to a faster raw tool is provided. A restarted process also refuses a
dispatching/verifying/paused checkpoint. After a pause, inspect the actual app
state and reconcile the outcome before any explicit new task; preserve the old
checkpoint and completed identities. Changing a seed does not authorize replay.

## Validation boundary

All builds/tests run in a disposable repository copy, with independent Cargo
artifacts/caches and a copy of the planner. No live daemon was replaced and no
phone action or real collection mutation is required by these tests.

- Core tests cover timestamp preservation, one down/up pair, viewport binding
  and invalid paths.
- HTTP router tests cover actual Runner payloads, zero dispatch on stale tokens,
  changed viewport, occlusion and unsafe geometry, plus one-send unknown delivery.
- MCP tests cover schema conversion/validation.
- Controller tests cover pacing, postconditions, persisted crash/interruption
  stops, task locking, item boundaries, deduplication and the real optional planner.
- Existing settle/outcome regression tests retain their separate delivery and
  observation contracts.

This does not establish physical tap recognition, actual OS sampling fidelity,
long-run app compatibility or avoidance of risk controls. Those require a later,
explicitly scoped fixture/device acceptance before operational rollout.

Local device-free results (2026-10-30): 37 core tests, 64 HTTP router/regression
tests, the MCP conversion test, the capability catalogue and timed-contact budget
tests passed. The controller passed 23 tests with external planner 0.4.0; without
the planner, 20 passed and the three planner integration tests explicitly skipped.
The Runner's 274 existing device-independent Swift checks passed, including its
W3C timing parser, with compiler module caches isolated from running services.
Neither the private library's implementation nor its repository is modified here.

## First physical acceptance (2026-10-30)

On macOS/iOS 27.2 with Xcode 27.1, a separately signed native Runner and
locally built fork daemon ran on independent loopback ports/state/build/cache
directories. The installed PUA service stayed stopped and its configuration was
not replaced during acceptance. After the person unlocked the phone, fresh
drivable status and a 430 x 932 logical viewport were observed in Dianping.

The pilot preserved two paused checkpoints rather than bypassing them. One
input was refused with HTTP 409; the Runner audit for that request contained
queries only and no touch dispatch. Its error body was not retained, so the
exact refusal cause is not claimed. A reviewed fresh attempt then applied a
123-ms planned contact to a home-page venue card. That card opened a ranking
page, while the pilot had expected a detail page, so postcondition verification
correctly timed out and paused. The actual page was inspected before planning
another step; the applied contact was not repeated.

From that observed ranking page, a new navigation unit successfully opened the
venue detail and returned to the ranking page. Both steps passed independent
two-snapshot page checks, and the unit's final result was independently checked
and checkpointed complete. Its planned contacts were 61 and 94 ms with five and
seven timed samples, respectively, each with a single down/up pair. The detail
screen was visually inspected and its favorite remained unselected. No favorite,
purchase, message, recorded replay or batch-collection action was sent.

This accepts fresh target selection, dispatch through the timed-contact route,
page verification, conservative stops and a bounded real-app navigation unit.
It does not measure the OS's physical touch-sampling fidelity, prove a personal
behavioural match, validate long batches or establish avoidance of platform
restrictions. Wireless operation was not repeated after the system update.
Raw screenshots, tokens, device identifiers, timing audits and checkpoints stay
in private local storage outside this repository. The person authorized formal
integration replacement only after this pilot succeeded; installation and host
tool loading still require their own delivery verification.

## Live-page waiting correction (2026-10-30)

Formal installation of the verified native build exposed two acceptance issues.
A planned bottom-tab contact was rejected as `element_occluded`; daemon task
metrics and the pre-dispatch guard identify a refusal, with zero unknown
outcomes. That checkpoint remains paused. A separate food-category navigation
then applied, but its guessed `筛选` postcondition was not exposed under that
label: the accessibility tree reported `FilterButtonTitle`. The page was
inspected, and the applied contact was not repeated.

Two read-only observations also showed the same category anchors while a coupon
countdown changed once per second, changing the full snapshot every time.
Requiring whole-screen equality would indefinitely reject this otherwise stable
page even with correct anchors. Plugin `0.27.7-guarded.2` instead compares the
explicit anchors' geometry/state, viewport and the pre-action target/focus across
two fresh reads. It still inspects every read for blockers and retains full
snapshot/target binding at dispatch. It does not add a retry, unpause or occlusion
override. Six device-free regressions cover changing countdowns, moving targets
and anchors, viewport changes, disappearing anchors, later challenges and absent
conditions. Previously paused records remain paused; this correction does not
retroactively verify their results.

The subsequent `0.27.7-guarded.3` correction also carries this context across
the single-action dispatch check, using the binding described above. Isolated
validation passed 10 touch-route tests (multiple changing-tree cases per test),
21 action-outcome, 34 settle, 15 privacy-capture and two coordinate regressions,
plus 30 controller and five launcher tests with the external planner. Previously
captured category frames independently show that the intended ranking/edge-back
contact regions remained equal while the full snapshots changed. Physical
acceptance and deployment have separate private receipts; paused historical
checkpoints are never retroactively resumed by this correction.
