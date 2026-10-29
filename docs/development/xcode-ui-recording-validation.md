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
