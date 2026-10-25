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
| Hosts | Codex, Claude, Cursor/Desktop and domestic hosts work through their actual tool and panel paths | WorkBuddy/Doubao candidate adapters now have protocol and installer checks; live host trust, rendering, reuse and task acceptance remain open |
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
- Ordinary short text on `ipu:atomicText` binds, optionally clears, types and
  postflights in one native request. Newlines require a TextView and secure
  fields refuse input. Older compatible text routes stop on failed clearing,
  but do not acquire this atomic field contract.
- Typing binds the focused field at dispatch. An earlier caller snapshot/locator
  is not an explicit target argument to `phone_type`. The candidate now adds
  snapshot-bound `set_value` prefix/chunks on `ipu:elementReplace`; see
  [replacement evidence](../measurements/element-replace-2026-10-25/README.md).
  Separate editing-key paths, occluded/AX-poor fields and physical replacements
  still require acceptance.
- Foreground MCP cancellation now observes its request token and drops the HTTP
  call. Actual stdio + daemon + runner checks observe one current chunk finishing,
  without later chunks or replay; raw TCP observations are also recorded. This
  is not a per-character immediate-stop guarantee. Physical transports, real
  host cancellation and default long-input pacing still need acceptance.
- No physical-device acceptance or comparative speed result is available yet.

## Failure recovery, in development

Selected UI failures from `/agent/input` and `/agent/actions` now request a fresh,
bounded image and give recovery advice while retaining the original delivery and
batch verdict. The capture is a later observation with explicit timing/source,
not the failure instant. Owner and privacy generations fence capture across
handoff and private-hold transitions. Unavailable, timed-out and oversized
captures leave the original failure intact. MCP returns one image block without
base64 duplication in text or structured output.

[Recovery evidence](../measurements/recovery-image-2026-10-25/README.md) records
software checks and the actual candidate integration results. [List recovery](../measurements/list-recovery-2026-10-25/README.md) adds
`scroll_find`/`collect` diagnostics and entry/read/send/publication scope guards.
Physical popups, real scrolling apps, custom-drawn screens, server-side cancellation after disconnect and image
rendering in real hosts remain open.

## Candidate host adapters

[Host adapter evidence](../measurements/host-adapters-2026-10-25/README.md)
records WorkBuddy resource-frame transport, a Doubao single-panel mode,
isolated config installation, GUI proxy reproduction/fix and 24 combined
Simulator cases. Only protocol/panel-script emulation and backend integration
are accepted here; WorkBuddy/Doubao applications are not installed on this host.
Actual trust, skill import, image rendering, panel reuse and complete tasks
remain open. A subsequent native-video candidate adds bounded H.264 batches over MCP and
WebCodecs canvas decoding, with the existing 2 fps PNG fallback. Actual host
rendering and reference streaming comparisons remain open. See
[native panel video](../measurements/panel-video-2026-10-25/README.md).

Ordinary screenshot/overlay, element/OCR reads, cached images, MJPEG/H.264
publication and late encoder callbacks now have privacy-generation fences;
[privacy evidence](../measurements/privacy-transitions-2026-10-25/README.md)
records the reproduced failures and regressions. Backend concurrency checks do
not establish physical/host acceptance or erase data already delivered. [Text privacy evidence](../measurements/input-privacy-2026-10-25/README.md)
adds queued/session/binding/clear/chunk fences and private-bound continuation. It also
freezes the authenticated owner incarnation before queue waits, rejects owner
A-to-B-to-A queued text and avoids renewing the new incarnation from old work.
The combined Simulator input-privacy checkpoint passes 28 cases, including a hold triggered
after the fixture observes its first input character and fresh continuation
after timed expiry plus an ordinary hold. [Action observation evidence](../measurements/observation-scope-2026-10-25/README.md)
adds per-request final/wait/publication filtering while keeping mutation receipts.
[Native request admission](../measurements/native-scope-2026-10-25/README.md)
adds send-time guards and native-prefix receipts. Untimed/spawned/service paths,
cross-request flows/suites, vault/intent/metadata and
log retention, installed packages and physical modes still require audit.

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

The [paired benchmark driver](../../scripts/agent-bench/README.md#paired-products)
now accepts a single explicit reference stdio configuration and records its
namespace, task hashes, CLI model identity and operator trial conditions.
Re-audit restores original trace-bound timing/status before independent receipt
attachment. The comparison helper keeps failures and orphan attempts, refuses
mixed conditions and leaves missing evidence unready. Its hermetic tests use
synthetic traces and a stub executable; **no actual paired product trial has
been performed**. CLI reported turns remain distinct from independently counted
model network requests, and readiness of supplied records is not superiority.

## Current candidate evidence

[First binding validation](../measurements/input-target-2026-10-24/README.md),
[continuation validation](../measurements/input-continuation-2026-10-25/README.md),
[atomic short input/cancellation validation](../measurements/short-input-2026-10-25/README.md),
[failure recovery](../measurements/recovery-image-2026-10-25/README.md),
[host adapters](../measurements/host-adapters-2026-10-25/README.md),
[read/stream privacy](../measurements/privacy-transitions-2026-10-25/README.md)
[input privacy](../measurements/input-privacy-2026-10-25/README.md)
[action observations](../measurements/observation-scope-2026-10-25/README.md)
[native admission](../measurements/native-scope-2026-10-25/README.md),
[selected value reads](../measurements/value-read-2026-10-25/README.md)
and [selected replacement](../measurements/element-replace-2026-10-25/README.md)
retain exact staged source/binary hashes and earlier failures.
The latest combined Simulator run passes 39 cases through the actual daemon,
runner and stdio MCP. It includes private input interruption and valid fresh
work after expiry, alongside the prior target/cancellation/recovery/host checks.
The native admission case additionally preserves one termination acknowledgement
while refusing a later relaunch after privacy changes.
Native H.264 packets also pass through runner/daemon/stdio resources and decode
independently; private on/off forces a fresh video subscription. [Continuous viewing evidence](../measurements/video-endurance-2026-10-25/README.md)
adds a 20-second native run across HTTP expiry and two independent MCP viewers,
plus idle-competition and decoder-stall fixes. [Actual Chrome replay](../measurements/browser-video-2026-10-25/README.md)
now verifies native AU decoding, real canvas pixels, decoder reuse, privacy
clear/resume and PNG fallback in both synthetic host modes. The full native-to-
MCP-to-browser live pipeline, installed-host presentation, physical rotation
and long soak remain unverified.
List diagnostics additionally preserve coverage and produce one fresh image over
stdio; private on/off after a swipe ACK preserves one confirmed gesture and
sends no later source request. The first counter-instrumentation failure and the
corrected 38-case run are retained separately.
[List deadline evidence](../measurements/list-deadline-2026-10-25/README.md)
adds an entry-wide 80-second budget, historical partial-row checkpoints and
budget-limited recovery. The real queue probe returns after 80.005 seconds with
zero dispatch and remains inactive after the independent occupying input ends;
no owner/privacy transition masks termination. The fixture verifies 6,015
characters by its own count/hash while AX returns only 512. The subsequent [selected-value reader](../measurements/value-read-2026-10-25/README.md)
reads the full 6,015-character AX attribute through Runner, daemon and stdio MCP,
matching the App-owned hash. Bulk previews keep their 512-character size and
carry a provider truncation marker. Intentional limits report completeness and
UTF-16 counts; secure fields refuse. This proves the owned Simulator fixture,
not provider completeness on every app or physical-device support.
Physical acceptance, other action/key and observation/vault paths,
remaining opaque-action/flow/vault/log, recovery/host/video work, distribution and comparative task trials
remain open. The broader goal is not complete.
