# Native panel video candidate

The MCP Apps panel can consume the native H.264 pipeline through its existing
app-only frame tool; WorkBuddy uses read-only resource reads. No daemon address,
password or bearer is sent to the iframe. The page retains its no-network CSP.
Unsupported decoders, older daemons and stream failures clear video and use PNG.

The relay checks opaque process/privacy scope before and after bounded reads,
requires a keyframe at each connection, bounds packet/buffer sizes, drops the
transport on cancellation and expires inactive subscriptions after two seconds.
The panel closes its decoder when hidden, clears canvas pixels and ignores late
callbacks. Keyframes reconfigure decoding, including same-codec size changes.

Software parser/transport and emulated panel tests cover fragmentation, keyframe
entry, malformed sizes/flags, cancellation, idle expiry, hide/unhide incarnations,
late decoder output and PNG fallback. Emulated WebCodecs output is not actual
codec decoding or real host rendering. `software-checks.json` retains exact summaries/log hashes: 892 server unit tests
(one ignored), 107 HTTP auth and six privacy cases; 242 MCP unit tests (one
ignored), 26 stdio cases; pinned 1.96.0 workspace Clippy and daemon/MCP builds.
The parser/relay cases include actual loopback HTTP, cancellation, idle expiry,
pre/post privacy transitions and credential-free public results/errors.

`simulator-results.json` records 33 passing actual XCTest/daemon/stdio cases on
an isolated iPhone 17 / iOS 27 Simulator, including the previous 31 cases. The
new resource path returns eight native packets (73,812 encoded bytes), decoded
independently by ffmpeg into the 602x1310 `native-panel.png`. Visual inspection
confirms the fixture title, text fields and keyboard; this is synthetic data.
`native-panel.h264` is retained for independent decoding. The daemon log confirms
pass-through from the runner's own H.264 encoder, rather than Mac transcoding.

The private on/off case clears the prior subscription, returns no old packets,
and obtains a fresh scope without native keyboard calls or changing the owner.
Exact source/binary and encoded/decoded hashes were independently checked.
The Simulator is absent from simctl inventory; ephemeral runtime/state folders
are deleted. The first 33-pass checkpoint is retained separately; the final run
also covers the later relay refactor and early release of reset connections.

`browser-check.json` records an attempted actual Chrome test that could not run:
chrome-use had no responsive relay or connected profile, and recorded no tabs.
The owned session was stopped and the loopback fixture server closed. No browser
codec/canvas acceptance is inferred. To repeat with a connected Chrome, extract
a single AU with `ffmpeg -f h264 -i native-panel.h264 -c copy -frames:v 1 -f h264
/tmp/panel-first.h264`, then serve it using
`scripts/serve-mcp-video-browser-fixture.py --packet /tmp/panel-first.h264` and
use chrome-use on the printed URL (`?resources=1` selects resource transport).

The previous input/admission candidate `a7bf898` passed every GitHub check:
PR checks 40141730998, security 40141731013 and Simulator smoke 40141731031.
Those results apply to that commit, not this subsequent video candidate.

## Subsequent browser acceptance

[Actual Chrome replay](../browser-video-2026-10-25/README.md) supersedes the earlier
unavailable-browser checkpoint for codec/canvas behavior only. It reproduces zero
output with repeated decoder recreation, fixes SPS/PPS reuse and bounded queue
pressure, and checks public/private/resume/PNG states with real VideoDecoder in
both synthetic host transports. It replays captured native data, not live phone
video, and does not establish real client application or physical acceptance.

## Remaining acceptance

Actual WorkBuddy/Doubao/Codex rendering, physical USB/Wi-Fi capture, orientation,
long sessions, bandwidth/FPS/latency and paired reference tasks are unverified.
No measured performance improvement or complete competitive superiority is
claimed. The full scope remains in `docs/development/competitive-acceptance.md`.
