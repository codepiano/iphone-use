# Real-browser H.264 panel validation, 2026-10-25

Actual Chrome 155 supported the captured native Main-profile H.264 access unit
and decoded it to 602x1310 with an independent decoder/flush. The original panel
produced zero frames while repeatedly closing/recreating its decoder: the saved
probe observed 4,517 configurations and zero outputs. Reconfiguring every IDR
can discard buffered output before it is delivered. A second issue rejected a
bounded multi-packet batch when the decoder queue passed six. A private hold
also incorrectly entered the 30-second video-failure cooldown.

The candidate reuses a decoder while the bounded SPS/PPS signature is unchanged.
Changed parameters reconfigure it, retaining old-callback exclusion. Queue
pressure yields to decoding for at most one second before fallback. Private
holds clear pixels/decoder but do not count as a codec failure; public video
can resume on the next ordinary poll. Parameter parsing has bounded NAL and
parameter sizes. No codec or frame is simulated in the browser acceptance.

## Actual browser evidence

[browser-observations.json](browser-observations.json) records real WebCodecs
callbacks and canvas state for tools and read-only resources. The host bridge is
synthetic: it replays the same captured native AU eight times per response,
with a configured 100ms host delay. This is component/codec acceptance, not live
transport, a native encoder FPS/latency result, or actual WorkBuddy/Doubao/Codex.

- Tools: one decoder configuration, 312 chunks submitted, 311 frames emitted;
  resource mode: one configuration, 528 submitted/emitted, zero decoder errors.
- Resource mode observed 134 resource reads and zero tools/call messages.
- Both modes displayed a 602x1310 canvas. The exported rendered pixels are in
  [browser-video.png](browser-video.png); manual inspection shows the owned test
  App, Chinese draft and keyboard. Neither mode's image contains personal data.
- Privacy tests hid the image and reset/hid the canvas to 1x1, then both resumed
  video. Observed UI-command-to-render intervals were about 2.1 seconds in this
  synthetic fixture; this is not a transport or competitor latency benchmark.
- Explicit video-unavailable responses switched both modes to a fully decoded
  602x1310 PNG, with video hidden. No unavailable video was called successful.

[pixel-comparison.json](pixel-comparison.json) compares browser canvas RGB with
ffmpeg decoding of the same AU: each channel's mean absolute difference is
below 2/255. The two transport modes exported identical PNG hashes. The native
AU and fallback PNG are retained for replay. [source-manifest.json](source-manifest.json)
records exact panel/fixture/test/probe/native-stream hashes and the upstream
Runner binary hash. Diagnostic probes wrap real VideoDecoder callbacks and
never synthesize output frames.

`chrome-use canvas capture` did not find the canvas in the selected iframe;
export used the same-origin iframe's actual canvas.toDataURL via eval --frame.
No persistent browser configuration was changed. [cleanup.json](cleanup.json)
records verified absence of the owned tab/session and termination of the owned
loopback fixture server. Other browser sessions were left untouched. No new
Simulator or personal phone was operated in this browser run.

## Reproduction and checks

Serve `scripts/serve-mcp-video-browser-fixture.py --packet
 docs/measurements/browser-video-2026-10-25/native-keyframe.h264 --png
 docs/measurements/browser-video-2026-10-25/fallback.png --batch-packets 8
 --interval-ms 100`, then open its printed URL with chrome-use in an owned
session. `?resources=1` selects read-only resource transport. Hide/Show verifies
clear/resume; Use PNG verifies fallback. The included probes can record real
decoder callbacks; install after page load, then Hide/Show to create a measured
new decoder. Finish the owned browser session and stop the fixture server.

The emulated panel checks retain same-codec SPS/PPS changes, decoder reuse,
forced queue pressure and bounded timeout, private resume without advancing a
30-second cooldown, late callbacks, rotation, stalled decode, PNG fallback and
hidden teardown. These emulated checks remain separate from real rendering.
[software-checks.json](software-checks.json) records 247 MCP unit checks passed /
1 ignored, 51 integration checks including 29 stdio cases, both panel/host modes,
locked Rust 1.96.0 workspace Clippy, the candidate MCP build and eight isolated
named-install checks. [packaged-panel.json](packaged-panel.json) additionally
reads both panel resources from the actual stdio binary and verifies an exact
match to the current source template after normal host/version substitutions.
Prewarm is disabled and no phone/daemon is contacted for that packaging check.

Prior replacement head 5fbd558 passed Simulator smoke 40159417499 and security
40159417491, but PR checks 40159417490 failed in the named-install test at a
printf | grep -q pipeline under pipefail. grep's early successful exit can break
the producer. Source checks now use here-strings, preserving every assertion
without an upstream writer. The named-install fake identity/auth cases pass;
product installer behavior was not changed. New-head CI is tracked separately.

## Remaining acceptance

Actual client products and their sandbox/trust behavior, live native-to-MCP-to-
browser transport, physical USB/Wi-Fi, physical orientation, long sessions and
controlled paired tasks remain open. A recorded AU replay cannot establish task
success, live throughput or complete competitive superiority. The full scope
remains in docs/development/competitive-acceptance.md.
