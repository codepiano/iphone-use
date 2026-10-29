# Physical-device Xcode UI recording probe (2026-10-30)

## Result

Xcode 27.1 UI recording received interactions performed directly on the paired,
wired iPhone. It generated cross-app XCTest source without using this fork's
input API or replaying the resulting test. This establishes a useful semantic
workflow recorder; it does **not** establish a raw touch or timing recorder.

The saved sample contains 23 action statements, including application activation,
tap/double-tap, directional swipes and Home events. It covers SpringBoard,
Settings navigation and a Dianping activation/window interaction. Action-statement
count is not a physical-touch count: the recorder groups gestures and can add
application activation; startup/system events cannot all be attributed to the
person. Direction/query alternatives in generated comments also show that the
output is an interpretation of the interaction, not a raw sample stream.

The person clarified that they operated elsewhere. A complete Dianping
search/detail/back unit with controlled 5-second and 10-second pauses was **not**
collected, so this probe does not accept that specific workflow or its timing.

## Timing limitation

The exported Swift contains no per-action timestamps, sleep/wait statements,
elapsed intervals or sampled touch coordinates/times. The probe's associated
DerivedData logs contain build/signing records but no recording `.xcresult`.
A bounded query of Xcode's ordinary recording-related unified logs produced
provisioning messages, not a per-touch timeline. These checks are not an
exhaustive investigation of every internal Xcode artifact or recording protocol.

Consequently, the exported source alone cannot reconstruct the person's actual
inter-action pauses, contact duration, drift or swipe speed curve. No timing
values were guessed from file modification times or automation API defaults.
A future comparison needs a separately synchronized observation timeline/video
for workflow cadence, or an instrumented calibration receiver for touch samples.
Whether Xcode's recording protocol exposes additional usable event timestamps
remains unverified.

## Post-update repeat (2026-10-30)

The repeat used macOS 27.2, iOS 27.2 and Xcode 27.1. After the host update,
Xcode required its official system components to be installed again. The global
developer directory pointed at Command Line Tools; commands used a per-process
`DEVELOPER_DIR` override rather than changing that global setting. CoreDevice
reported a wired, paired, booted device with Developer Mode enabled and device
services available.

The former temporary project had disappeared from `/private/tmp` during the
update/reboot. A new, separate blank probe was created in private local storage,
using the same probe bundle prefix and separate build products/module cache.
`build-for-testing` passed before recording. Neither the installed PUA service
nor the candidate daemon/Runner was started. Xcode entered **Recording UI Test**
on the physical phone, and the person reported completing the requested
Dianping navigation before explicitly requesting that recording stop.

After removing recorder query-alternative comments, the saved Swift contains
26 action statements: 17 taps, 3 double-taps, 4 directional swipes, 1 app
activation and 1 Home event. These are generated statements, not a count of
physical touches. The source includes Dianping interactions and back-image
targets, but many targets are generic windows or indexed elements, and no
search text was exported. The person's completion report and the generated
source therefore do not independently establish which exact store/result/detail
each ambiguous target represented. This is not an accepted replayable business
unit, and no replay was attempted.

A passive local observer read only the saved source file every 50 ms during
the manual sample. It retained five distinct source states, with cumulative
action counts of 1, 14, 21, 24 and 26. The later states were first observed
about 21.115, 36.652, 53.361 and 71.632 seconds after its initial state.
Multiple statements arrived in each saved revision. Those times describe
file visibility on the Mac, not touch occurrence: polling resolution does not
remove Xcode's batching/save delay. They cannot recover individual action
intervals or validate the requested 5-second and 10-second pauses.

The final Swift still has no exported timestamps, waits, contact durations or
sampled touch coordinates. The isolated CLI build contains no `.xcresult`.
Thus the post-update repeat passes device connectivity and direct physical
semantic recording, but still does not pass human timing/trajectory capture.
An independently synchronized screen/event timeline remains necessary for
cadence comparison; this repeat did not implement or validate that capture.

After the person's completion reply, Xcode's **Stop** was pressed and observed
disabled, the source was saved, and the workspace was closed. The project test
was replaced with an unconditional `XCTSkip`. The raw source survives only as
private plain text alongside the private observation log and summary, outside
this repository. The observer exited; no `xcodebuild`, relay or candidate
control process remained. No captured code was rebuilt or replayed, no agent
business mutation was sent, and batch collection remains paused.

## Synchronized video repeat (2026-10-30)

**Result:** simultaneous QuickTime iPhone-screen capture and Xcode physical UI
recording worked. For this short sample, manual inspection can associate four
visible page transitions with four ordered input statements and measure their
approximate visual cadence. This does not supply raw input timestamps, prove
every physical touch was recorded, or validate an automatic alignment system.

The person directly performed two result/detail/back cycles for the same venue.
QuickTime captured the wired phone's **Screen** source, with the phone audio
source selected rather than the Mac microphone. Video began before Xcode's
recorder, and both channels were confirmed active before the manual sample.
The blank probe passed isolated `build-for-testing`; no captured test was run.
The recording instructions requested approximate pauses, not a calibrated
external clock or a precise touch-timing ground truth.

The original movie is 74.399617 seconds, 1290 x 2796, H.264, with an average
rate of about 59.297 fps. Variable frame rate is suspected; the original was
preserved, and timing analysis uses video presentation times rather than
frame number divided by 60. The near-silent AAC stereo track is not a usable
audio sync marker. There is no subtitle track. The media check had no failures
and reported those three warnings (VFR, near-silent audio, missing subtitles).

After removing query-alternative comments, Xcode exported one app activation
and four input statements. Scene detection (threshold 3, ratio 1.5, minimum
scene 0.2 seconds) proposed the following video times. A 16-frame contact sheet
and additional frame pairs at 34/35, 48/49, 58/59 and 64/65 seconds were inspected
to confirm the transition identities; the 49-second frame is visibly in the
return animation, rather than already a stable results page.

| Ordered input statement | Visible transition | Candidate video time | Since preceding transition |
| --- | --- | ---: | ---: |
| `element.tap()` (generic window) | Results to venue detail, first visit | ~34.5 s | Not measured from a manual start marker |
| Back-image `tap()` | Detail to results, first return | ~48.9 s | ~14.4 s |
| `element.tap()` (generic window) | Results to the same detail, second visit | ~58.4 s | ~9.5 s |
| `element.doubleTap()` (generic window) | Detail to results, second return | ~64.2 s | ~5.8 s |

These values are scene-change candidates associated by order and visible
content, not the exact start of an animation or finger-down/up times. They
include UI response/loading/animation and capture effects, so they do not
establish pure human dwell time or confirm the nominal requested pauses.
The initial video segment also contains setup and instruction-reading time;
its 34.5-second duration is not a five-second pause measurement.

The two generic window taps cannot identify their original physical hit
coordinates. The final return is interpreted by Xcode as a generic window
double-tap; the video confirms a return transition, but neither source proves
the exact tap count, hit position or spacing inside that gesture. No synthetic
second tap, corrected semantic selector or inferred touch timestamp was added
to the evidence. This sample supports coarse workflow/cadence comparison only;
unchanging-screen touches and precise contact trajectories remain unresolved.

The passive source-file observer again saw batched revisions, so its timestamps
were not substituted for video times. Host start/stop request bounds were saved
only as supporting local metadata; they are not a calibrated mapping from
every video PTS to the phone's touch-event clock.

On the person's completion reply, QuickTime was stopped first, then Xcode was
stopped and observed with its Stop control disabled. The movie was saved to
private local storage and observed paused, and the Xcode workspace was closed.
The captured source was archived as `.swift.txt` and the project test replaced
with unconditional `XCTSkip`; the local observer exited. All raw video, frames,
source, host timing metadata and private alignment JSON remain outside Git in
a mode-0700 directory (top-level artifacts mode 0600). Only this sanitized
report is committed. No device actions were replayed, no automated business
mutation was sent, no control service was started, and batch collection remains
paused. The recorder project/build/cache were isolated from the installed
control path and the fork's source/build outputs.

## Manual sample versus generated policy (2026-10-30)

This comparison uses the existing synchronized sample and current source only.
No recording was replayed, no phone service was started, and no pacing or tap
parameters were changed. The opt-in generated path has not been physically
measured against this sample. In particular, the requested 5/10/5/3-second
pauses make this a guided recording, not an unprompted personal behaviour
baseline. Four interpreted input statements and three intervals cannot fit a
personal timing distribution, error rate or position/contact model.

### Rhythm

The sample's consecutive visible-transition intervals are 14.403, 9.519 and
5.818 seconds (first detail/return, results/reopen, second detail/return).
They vary substantially within this recording, but no claim about the cause
(reading, familiarity, hesitation or checking) can be established from video.
They include display response and animation rather than pure decision time.

The controller uses the same `2.0 + U[0,1.5)` second post-verification wait for
all supported actions, independent of whether the next step reads a detail,
returns immediately or opens a previously seen page. This is additive pacing,
not a full dispatch-to-dispatch interval. Each pre/postcondition needs two
matching snapshots with a one-second polling interval. In an immediately
stable, zero-network-latency fixture, consecutive input starts therefore include
the preceding contact duration, one postcondition poll, the pacing wait and one
next precondition poll: approximately 4.06 to under 5.64 seconds with defaults.
Real transport, native execution, screen settling and caller/model time add to
that idealized calculation; slower actual operation is not excluded.

An offline virtual-clock calculation ran a copied controller with the real
external planner 0.4.0, a fake phone object, synthetic button geometry, one
navigation unit and deterministic entropy seed 20261030. No `HttpPhone` was
instantiated and the fake transport only changed local fixture state. Its four
generated contacts lasted 92, 74, 133 and 98 ms; consecutive virtual dispatch
gaps were 4.421629, 4.574642 and 4.750743 seconds. These values illustrate the
current policy, not observed phone timings or measured human coordinates.
The manual visual intervals and virtual dispatch gaps have different measurement
bases; no speed ratio, significance test or claimed behavioural match is derived.

There are also explicit task-boundary rules: at least ten seconds between
completed items, and thirty additional seconds every third completed item.
The recording contains two visits to one venue and no completed collection
items, so it provides no evidence to validate those round/break settings.

### Click method and unsupported comparisons

| Dimension | Manual recording evidence | Current opt-in generated policy |
| --- | --- | --- |
| Gesture grouping | Xcode interprets three taps and one double-tap; final return is visible, exact touch count unresolved | One contact per tap, one down/up pair; no spontaneous double-tap, noise input or automatic retry |
| Landing point | Not captured; three inputs target a generic window in generated source | Fresh unique target; center-biased random landing within 15% inset |
| Contact duration | Not measured by source or ordinary screen video | Default 60–140 ms; varies per action seed |
| Contact drift | No raw coordinate samples | At most one logical point by default; may be stationary |
| Behaviour after input | Video establishes page changes; it does not reveal the person's internal decision rule | Two unchanged snapshots and explicit anchors; uncertainty latches paused |

The current generator already avoids a mandatory exact-center landing, but its
position/duration/drift distributions are engineering presets. This recording
cannot tell whether they match the person's hand. A finger moving between
buttons above the glass is not an on-screen contact trajectory; adding a
screen drag between unrelated tap targets would change the interaction.

For context, the installed original PUA's ordinary selector path calls the
element `/click`, and coordinate taps call `/wda/tap` with supplied coordinates.
Those paths do not explicitly apply this planner's per-action position/contact
variation. The source computes target centers for suggested tap points and
preview bookkeeping, which alone does not prove the native `/click` always
lands at that exact center. The separate preview-pointer path has a fixed
50-ms contact, but that is not the ordinary agent tap path and is not used as
its duration baseline here. There is no synchronized original-agent sample in
this recording, so its actual cadence or touch duration is not reconstructed.

The clearest design difference is **role-independent wait rules versus the
different visible intervals in this guided unit**. A future calibration can
separately describe page readiness, explicit task-required dwell and actions
that need no reading. It should preserve single-delivery/uncertainty handling;
this result does not justify adding noise, copying the ambiguous double-tap,
claiming avoidance of platform restrictions or fitting a distribution to this
single instructed sample. Parameters remain unchanged pending better evidence.

The private offline calculation and its source copy remain outside Git in a
separate analysis directory. Only this sanitized comparison is committed.

## Procedure and boundaries

1. Created a separate temporary UI-test project, with a distinct bundle identity,
   build products and compiler caches. Its initial test contained only a trivial
   assertion, with no app launch, tap, swipe or typing code.
2. `build-for-testing` succeeded. It did not execute recorded interactions.
3. Released only this chat's previously started temporary validation Runner,
   relays and daemon after confirming there was no active owner, so Xcode could
   use its own recording session. The installed PUA plugin was not restarted.
4. Opened Xcode's **Start Recording UI Test** on the selected physical device.
   The person used the phone; generated code appeared in Xcode.
5. On the person's explicit completion reply, pressed **Stop**, saved the source
   and confirmed the recording indicator/active Stop action were gone. Never
   pressed Run/Test on the captured source.
6. Archived the raw source locally as a private `.swift.txt` file, closed the
   probe window, and replaced its test with an unconditional `XCTSkip` guard.
   No captured code was rebuilt or replayed. A device app inventory query found
   no installed app matching this probe's bundle prefix.

Raw source, app/device metadata, signing output and logs remain local and are
excluded from this repository. No extra noise clicks were added, no business
mutation was sent by the agent, and batch collection remains paused. The former
temporary validation service stays stopped after this recording handoff; this
probe does not deploy or activate the fork.

## References

- [Apple: Recording UI automation for testing](https://developer.apple.com/documentation/xcuiautomation/recording-ui-automation-for-testing)
- [Apple WWDC25: Record, replay, and review](https://developer.apple.com/videos/play/wwdc2025/344/)

Apple documents recording interactions across installed apps. The device-specific
results and limits above come from this local probe, rather than assuming all
recording features preserve the person's original timing.
