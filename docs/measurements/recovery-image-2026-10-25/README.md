# Failure recovery images

The candidate enriches selected UI failures from `/agent/input` and
`/agent/actions` with a newly requested screenshot and recovery advice. It keeps
the original HTTP status, error, delivery outcome, retry safety and batch counts.
The image is a later observation, not proof of what the screen showed at failure.
It carries capture request/receive times, source, pixel dimensions and normalized
coordinate guidance. A screenshot never authorizes replay of an uncertain action.

Capture requires the same named owner incarnation, live lease, unchanged privacy
generation and no release, lifecycle transition or human handoff. These conditions
are checked before and after capture. An explicit private hold on/off during
capture fences the image even if privacy is clear again when capture finishes.

There is one 2-second total capture budget, a bounded response-size budget and no
cached image fallback. Header `X-Phone-Recovery-Image: none` and environment
`IPHONE_USE_RECOVERY_IMAGES=0` opt out. MCP lifts the payload into exactly one image
block before applying full/slim/off structured output; text and structured JSON
retain metadata without repeating base64.

## Software evidence

Server library: 883 passed, 1 ignored. Related HTTP entry tests: 42 passed,
including four new recovery tests. They verify single/batch missing-target
failures, a seeded stale cache, capture failure/timeout, response-size limit,
opt-out, subsecond private hold, ownership change and a privacy on/off race.
Capture failure and withholding preserve the original action verdict. The tiny
budget test runs in a separate child process to isolate its environment setting.

The new stdio cases cover full/slim/off output, single/batch failures, exactly one
image block and invalid image payloads. MCP library: 232 passed, 1 ignored; real stdio: 18 passed.
`software-checks.json` records test summaries and complete local log hashes.
The candidate daemon and MCP binaries build successfully. The existing
Simulator runner artifact is reused because native runner sources did not change
in this recovery increment.

## Limits

This is candidate source and simulator evidence, not a release, physical-device
acceptance or a head-to-head performance result. Dedicated `scroll_find` and
`collect` endpoint recovery, real popups/custom-drawn screens, host rendering and
physical transports still require acceptance. No overall superiority is claimed.

## Combined Simulator run

`simulator-attempt-1.json` records 23 passed cases using the actual candidate
daemon, XCTest runner and stdio MCP on a disposable iPhone 17 / iOS 27 simulator.
Source and daemon/MCP executable hashes were checked after the run. Cleanup
completed without errors. The three added checks verify a fresh failure image
with its original not_sent/retry-safe verdict, no image under a private hold,
and one MCP image block with the original batch verdict. The prior 20 native
input/continuation/cancellation cases also pass. No physical device was used.
