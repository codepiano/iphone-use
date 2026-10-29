# Guarded touch execution

This fork adds an **opt-in** source-level controller. Existing release tools do
not silently change their taps or cadence. Installing/deploying the fork is a
separate step; this change does not resume any collection task.

The controller imports the independently maintained `pointer-trajectory`
Python package, contract `>=0.4,<0.5`. No planner implementation is vendored or
downloaded at runtime. Install the authorized package from its own checkout into
a dedicated Python environment, rather than changing a running service's Python
environment. Public CI runs the policy tests without that optional dependency;
the three real-planner tests require it and report skips when absent.

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

The same task's processes must share the state directory. A nonblocking file
lock rejects competing calls, while daemon owner leases govern other tasks.
The task checkpoint binds the application, daemon origin and owner. It stores
hashed item/step identities, counts, seed and reason codes, never screen contents,
entered text or credentials. Its write is fsynced **before** sending input.

For every action the controller:

1. Waits for its persisted cadence deadline and confirms drivable status.
2. Requires two fresh, unchanged screen observations matching explicit
   preconditions. Empty/partial screens, changed app and system alerts stop it.
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
