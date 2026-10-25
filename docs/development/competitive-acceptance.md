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
- The initial assessment was a source comparison. Subsequent
  [paired operation diagnostics](../measurements/paired-pilot-2026-10-25/README.md)
  run both actual MCP implementations and the reference's pinned WDA on one
  owned Simulator. These model-free functional pilots retain native clearing
  failures and uncontrolled resource conditions. They do not establish a
  task-latency win, real model turns or physical-device superiority. The
  reference's published timings are not independent measurements.

The subsequent [physical iPhone 17 Pro Max/iOS 27.2 lane](../measurements/physical-iphone17-2026-10-25/README.md)
uses the same owned fixture over the local network. Twelve native entry/fault
checks and a separate 16-record ABBA cohort plus two focus-shift probes retain
independent App hashes. Ordinary 500-character replacements are 2/2 for each
participant. Full reading favors the dedicated native operation; the strict native default
stops at clear-time focus handoff while reference completes it. A later explicit
selected-field recovery candidate completes the two recorded native handoffs;
see the later acceptance below. Both still fail the mid-input focus-change task.
This adds one-device functional evidence, without a speed/model/release win or
broader physical-device coverage claim.

| Area | Required outcome | Evidence still required |
| --- | --- | --- |
| Input target | Long input and continuation retain the original field, app and session; loss of focus stops without refocusing or replay | Physical app/session/continuation switches beyond the same-App field fixture; in-flight segment isolation remains open |
| Partial delivery | Confirmed, uncertain and unsent portions remain distinct, including clear, timeout, cancellation and batches | HTTP and MCP entry tests with injected failures, then device readback |
| Recovery | Occlusion, no progress, missing targets and failed postconditions provide a fresh bounded screenshot and useful recovery; original errors survive capture failure | Entry tests, on-device popups and custom drawn UI |
| Reading | Native and WebView content stays usable, with bounded output and explicit truncation/coverage | Same-page samples, Chinese lists, AX-poor screens, hidden and covered rows |
| Task latency | Higher or equal verified completion rate; better completion latency and model round trips on representative tasks | Paired same-device runs, same model, initial state and independent postconditions |
| Replay | Repeated tasks complete with deterministic flows and useful failure evidence | Installed-package flow runs on representative apps |
| Setup/recovery | Fresh setup, upgrade, existing setup reuse, signing errors and reconnect have actionable outcomes | Disposable install tests and free/paid signing with devices |
| Hosts | Codex, Claude, Cursor/Desktop and domestic hosts work through their actual tool and panel paths | WorkBuddy/Doubao candidate adapters now have protocol and installer checks; live host trust, rendering, reuse and task acceptance remain open |
| Viewing/control | Live view, human takeover, capture-hidden UI, gestures and pause/resume work reliably | Browser, MCP panel and iOS controller acceptance; measured bandwidth/latency |
| Deployment modes | USB, Wi-Fi, multiple phones, old supported iOS and simulator keep documented behavior | One iPhone/iOS27.2 local-network functional lane is recorded; USB, other versions/phones and longer sessions still need separate acceptance |
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
  acceptance is recorded below; cross-call physical continuation and app/session
  switches remain open beyond the same-App physical replacement fixture.
- Native postflight detects an observed focus/app change during a chunk and
  reports that chunk as unknown. The simulator covers this with a 20/180 split
  between two fields. This does not prove per-character isolation, rapid
  away-and-back focus detection or physical-device behavior.
- The inspected Xcode 27.0 Simulator client implements
  `XCTRunnerDaemonSessionEventRequest.invalidate` as a logging no-op. Calling
  that method cannot provide an in-flight cancellation guarantee. Keep this
  [artifact observation](../measurements/paired-pilot-2026-10-25/event-request-invalidation-27.0.json)
  separate from physical behavior and from other possible cancellation routes.
- Subsequent [physical character-event probes](../measurements/guarded-character-probes-2026-10-25/README.md)
  retain two rejected designs. Per-character text events reach the character-20
  focus fault without spilling to B, but fail ordinary replacement budgets.
  Key events fail the intended Unicode values and never reach their focus fault.
  Both prototypes were removed; neither resolves the default-path limitation.
- An [explicit selected-field clear-time recovery option](../measurements/selected-replacement-recovery-2026-10-26/README.md)
  subsequently completes the two tested 500-character handoffs. It requires
  verified original emptiness, current identity/app/binding, independent complete
  scene/overlap checks and at most one original-field tap before text starts.
  Default stopping remains; new content and occluders refuse, old Runners refuse
  requested recovery before replacement input. The same final lane still records
  A20/B180 on input-time focus change, so the segment-isolation gap remains.
- A subsequent [direct AX Value assignment experiment](../measurements/ax-setter-probe-2026-10-26/README.md)
  addresses unfocused fields and completes bulk Unicode replacements on a
  Simulator, but bypasses App delegate vetoes; TextView changes omit normal
  change notifications. Ordinary typing controls honor the same vetoes. That
  prototype was rejected for default input and is not shipped. Its focus fault
  triggers after 500 characters, so it does not close the character-20 gap.
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
- Physical evidence now covers the single iPhone 17 Pro Max/iOS 27.2 fixture
  lane linked above, including strict stopping and opt-in clear-time recovery.
  It does not establish physical cross-App continuation, a comparative speed
  win, broader devices/transports, actual model tasks or release acceptance.

The clearing candidate reads the original AX value and selection. Values of at
most 100 UTF-16 units whose selection reaches the end use only the deletion keys
required by the observed composed characters. Other positions/values require a
confirmed full selection before one delete. An acknowledged Select All whose
value and selection remain unchanged throughout readback can repeat once, after
rechecking the original binding and comparing the original value/range again.
Synthesis/read errors, partial selections and changed values stop immediately;
deletion and text are never replayed. Private retry state stays inside the Runner.
An App can still change focus or content during a current deletion/typing event.

Some AX providers return a placeholder string as the raw Value of an empty
TextField while both live snapshots correctly report no value. The full reader
normalizes that case only when the pre/post snapshots are empty and have the same
placeholder, and the raw value exactly matches it before clipping. It reports
`placeholder_shown: true` with zero content length. Literal content equal to the
placeholder keeps its real length and clipping metadata. Clear readback additionally
checks an empty caret and rechecks the original focused binding. Provider/physical
coverage beyond the recorded fixtures remains open.

## Gesture dispatch, in development

A synthesis error used to trigger a second coordinate gesture, including W3C
single-pointer actions. The candidate now chooses coordinate fallback only on
capability absence before synthesis invocation. Every error after invocation
remains unknown and stops, including errors whose text resembles a setup failure.
The same policy covers native taps/swipes/holds, selected-element focus taps
through `tapPoint`, alert taps and W3C plain taps. W3C delayed/held/moving/multiple
pointer paths cannot become a plain coordinate tap. This closes automatic native
gesture fallback replay; it is not proof about all server/host retries or in-flight
cancellation. The 312 native logic checks include effect-before-error and failed
public-path controls; they are not physical acknowledgement-loss injection.

The subsequent [actual HTTP/stdio MCP entry checks](../measurements/gesture-delivery-entry-2026-10-26/README.md)
pass 42 scenarios in each of default/full MCP output modes against a scripted
loopback Runner. Error replies, errors inside HTTP 200 and lost connections stay
unknown/non-retryable with one native POST. Batch prefixes retain their applied
count; the unsent suffix does not run. This is protocol-ledger evidence, not real
UIKit delivery or physical transport failure injection.

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
clear/resume and PNG fallback in both synthetic host modes. [Live Simulator viewing](../measurements/live-browser-2026-10-25/README.md)
subsequently verifies actual native/daemon/stdio-MCP/browser delivery of six
changing App markers in both modes, plus real private holds and no native input.
The host shell is synthetic. Installed product hosts, physical modes/rotation,
live outage-to-PNG recovery and controlled long soaks remain unverified.
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
