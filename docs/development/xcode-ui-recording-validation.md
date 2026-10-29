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
