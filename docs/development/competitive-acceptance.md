# iPhone automation acceptance

Goal: outperform zhongerxin/iPhone-use across task completion, latency, safety,
installation, supported clients and remote viewing. An implementation or passing
mock test does not establish that goal. Keep physical-device results separate
from source, simulator, CI, release and installed-package evidence.

Baseline inspected on 2026-10-24:

- Ours: `ab32b3fe516974cc96d009ad1714b2ffb05a141b` (v0.23.0).
- Reference: `zhongerxin/iPhone-use` at
  `3ce9c080534e89fab91a237bf1c53a4a7e9d80a7` (MIT).
- Reference implementation paths: `server/wda_controller.py`,
  `tests/test_latency.py`, `workbuddy/`, `doubao/`,
  `skills/iphone-use/references/app-snapshots.md`.
- This is a source comparison. Neither product has been run in a controlled
  head-to-head trial in this work. The reference's published timings are not
  independent measurements.

| Area | Required outcome | Evidence still required |
| --- | --- | --- |
| Input target | Long input and continuation retain the original field, app and session; loss of focus stops without refocusing or replay | Protocol tests, simulator and physical app/field-switch cases; continuation across calls |
| Partial delivery | Confirmed, uncertain and unsent portions remain distinct, including clear, timeout, cancellation and batches | HTTP and MCP entry tests with injected failures, then device readback |
| Recovery | Occlusion, no progress, missing targets and failed postconditions provide a fresh bounded screenshot and useful recovery; original errors survive capture failure | Entry tests, on-device popups and custom drawn UI |
| Reading | Native and WebView content stays usable, with bounded output and explicit truncation/coverage | Same-page samples, Chinese lists, AX-poor screens, hidden and covered rows |
| Task latency | Higher or equal verified completion rate; better completion latency and model round trips on representative tasks | Paired same-device runs, same model, initial state and independent postconditions |
| Replay | Repeated tasks complete with deterministic flows and useful failure evidence | Installed-package flow runs on representative apps |
| Setup/recovery | Fresh setup, upgrade, existing setup reuse, signing errors and reconnect have actionable outcomes | Disposable install tests and free/paid signing with devices |
| Hosts | Codex, Claude, Cursor/Desktop and domestic hosts work through their actual tool and panel paths | WorkBuddy and Doubao adaptation and live host acceptance |
| Viewing/control | Live view, human takeover, capture-hidden UI, gestures and pause/resume work reliably | Browser, MCP panel and iOS controller acceptance; measured bandwidth/latency |
| Deployment modes | USB, Wi-Fi, multiple phones, old supported iOS and simulator keep documented behavior | Separate acceptance per mode/version; do not generalize one phone's results |
| Privacy/access | No unexpected collection; authentication, owner isolation and limits remain enforced | Read-only/security regressions, wrong-owner and concurrent-control tests |
| Distribution | Actual downloaded release installs, discovers tools and operates the phone | Artifact hashes, signing/notarization, entry tests and physical acceptance |

## Runner input binding, in development

A supporting runner advertises `ipu:guardedInput` in session capabilities.
`GET /session/:sid/wda/input-target` binds a live, enabled, focused nonsecure
editable AX element. Long text uses that binding for every chunk and for an
optional clear. Guarded requests never tap to regain focus. Each successful
chunk renews the binding's 60-second idle expiry; session setup/deletion and
registry eviction invalidate it. Failed binding does not clear or type.

The phone re-reads the same AX element and checks its process against the
foreground immediately before dispatch. A rejected chunk is unsent; previously
acknowledged chunks remain confirmed. A transport/synthesis failure can be
partially delivered and is never retried through XCUIApplication.typeText.
Targeted synthesis must support the original process ID or refuse.

Limits to close before claiming input superiority:

- The current candidate adds owner-bound, single-use continuation across API
  calls and native invalidation for intervening commands. Its current native
  capability is `ipu:inputContinuation`; older `guardedInput`-only runners do
  not provide the continuation contract. Actual daemon/runner continuation
  acceptance is recorded below; physical-device testing remains open.
- Native postflight detects an observed focus/app change during a chunk and
  reports that chunk as unknown. The simulator covers this with a 20/180 split
  between two fields. This does not prove per-character isolation, rapid
  away-and-back focus detection or physical-device behavior.
- Old runners without the capability keep their existing input behavior;
  they must not be described as protected.
- Short text rechecks ownership after queueing and ambiguous synthesis never
  falls back to another typing implementation. Short literal input does not yet
  carry the same explicit field binding as long/continued input. Separate key
  paths and daemon-level best-effort legacy clear behavior still need review.
- Router-future cancellation proves the token is consumed without replay; actual
  TCP-disconnect/host-cancellation stop latency and default long-input pacing
  still need end-to-end acceptance.
- No physical-device acceptance or comparative speed result is available yet.

## Trial protocol

Use the same phone, iOS, app versions, account/data shape, transport and model.
Run each product in isolation with its own setup, never two controllers at once.
Record exact source/build versions, runner version, cold/warm state and initial
page. Alternate product order. Keep all failed and unknown runs.

Start with reversible tasks: Settings navigation and reading, long Notes draft,
searching a loaded list, collecting a bounded list, dismissing a popup and
continuing, lock/unlock recovery, and switching focus during input. Do not send
messages, buy, delete user content or change account/security settings as a
benchmark. Use synthetic draft text and redact personal UI from saved evidence.

An independent fresh read or device assertion must check the task's requested
answer and final state. Report completion rate, full task time (median and
spread), real model round trips, text/image output volume and unknown outcomes.
A screenshot, HTTP acknowledgement or model's final answer alone is insufficient.
Use `scripts/agent-bench` for our traces and independent verification receipts;
keep equivalent raw trace and postcondition evidence for the reference.

## Current candidate evidence

[First binding validation](../measurements/input-target-2026-10-24/README.md)
records the initial candidate. [Continuation validation](../measurements/input-continuation-2026-10-25/README.md)
records 13 actual daemon/runner simulator cases, HTTP/MCP entry checks, exact
source and binary hashes, and earlier failed attempts. Physical acceptance,
complete short-input/legacy-clear protection, the remaining recovery/host work
and comparative task trials remain open. The broader goal is not complete.
