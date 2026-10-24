# Continuous native panel viewing

The preceding video candidate passed its initial-frame checks but continuous
viewing exposed two failures. The idle-expiry worker briefly locked the same
mutex used as foreground admission, causing a false `operation would block`
refusal after roughly two seconds (`before-idle-race.txt`). After separating
that gate, the 15-second HTTP deadline still stopped continuous video
(`before-http-expiry.txt`). Both failures are retained.

The relay now separates foreground admission from idle state cleanup and
rotates the connection after ten seconds, before its absolute deadline. Each
new subscription enters through a keyframe. Privacy incarnation checks still
precede rotation, so renewal cannot revive a revoked subscription. Same-scope
renewal retains the previous permitted canvas until the new decoder produces
pixels; privacy changes clear it. Parsing also bounds skipped packets per poll.

Three seconds without a native packet causes fallback. Independently, the
panel clears stale pixels after three seconds without decoded output, even if
packets continue to arrive. Codec capability checks have a 2.5-second timeout.
Hidden/teardown/watchdog generation changes discard late in-flight batches,
while decoder identity prevents old orientation output replacing newer pixels.

Loopback HTTP tests include viewing across the real 15-second deadline, two
independent subscriptions, idle-cleanup contention and stalled transport.
Actual panel JavaScript checks use an emulated host/decoder; they cover the
watchdog, portrait-to-landscape dimensions, late output and PNG fallback.
These are not actual host or browser-rendering acceptance.

`software-checks.json` retains log hashes and exact passing summaries: 246 MCP
unit tests (one ignored), 26 stdio cases, pinned 1.96.0 workspace Clippy and
candidate daemon/MCP builds. No server source changed in this checkpoint.

`simulator-results.json` records 35 passing combined cases through the actual
XCTest runner/daemon/stdio MCP on a disposable iPhone 17 / iOS 27 Simulator.
Continuous resource reads run 20.14 seconds, receive 132 access units and cross
the absolute HTTP deadline with one automatic rotation and zero PNG fallbacks.
The rotation is checked for keyframe entry. These counts are not render FPS.

Two separate MCP processes receive native keyframes. While B keeps polling, A
reconnects and exits; B's subscription is not reset. Once both independent
processes stop and the original reader becomes idle, viewer_count returns to
zero. Neither case sends keyboard requests or changes the control owner.
The preceding 33 input/privacy/recovery/video cases also pass, including
independent ffmpeg decode and native runner pass-through.

All listed source, daemon/MCP and media hashes were independently rechecked.
The Simulator is absent from simctl inventory; disposable runtime/state folders
were removed and cleanup reports no errors.

 The prior candidate facb3e8 passed all GitHub checks: PR checks
40143685374, security 40143685515 and Simulator smoke 40143685536. That CI result
applies to that exact commit, not the subsequent continuity changes.

Long physical sessions, real browsers/hosts, actual orientation presentation,
more than two viewers, native video bandwidth/FPS/latency, recovery under weak
networks and paired reference tasks remain open. Twenty seconds of continued
packet delivery is not an hours-long soak test or a rendering-rate measurement.
The full competitive objective remains incomplete.
