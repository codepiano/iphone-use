# Live native-to-browser viewing, 2026-10-25

An owned iPhone 17 / iOS 27 Simulator now drives the actual native Runner,
daemon and two candidate stdio MCP processes into the packaged HTML panel in
Chrome. Unlike the earlier captured-AU replay, this bridge forwards real MCP
frame replies without replacing video bytes. The containing MCP host shell is
still synthetic; actual WorkBuddy, Doubao and Codex applications are not tested.

The App changes a test-only title marker and independently writes its receipt
from inside its own data container. These commands use an explicit fixture
launch flag and file hook, not an automation input API. They establish fresh
viewing, not agent task completion or the ability to edit a real user's app.
Ordinary input fixtures do not start that timer or read those command files.

## Actual observations

[markers.json](markers.json) and the six retained canvas PNGs record local Vision
OCR and App receipts for each new marker. Every accepted image is 588x1280;
manual inspection also confirms the title changes. The observer requires the
expected marker with confidence >=0.9. It never accepts a backend ACK alone.

| Actual MCP path | Browser markers | Native video packets received by bridge | PNG fallback frames |
| --- | --- | --- | --- |
| Generic frame tool | 1001, 2002, then 3003 after private hold | 1,379 | 0 |
| Read-only frame resources | 4004, 5005, then 6006 after private hold | 2,390 | 0 |

The bridge recorded 1,292 frame tool calls and 2,291 resource reads, with zero
resource-mode tool calls and zero MCP errors. Packet/call counts are evidence
of the live path, not encoder/browser FPS or competitor latency measurements.
The daemon logs confirm native H.264 pass-through. Both HTML hashes match the
actual candidate binary's packaged resources verified in the earlier browser run.

[Generic privacy isolation](generic-private-isolation.json) holds packet count
at 1,040 across a 2,009ms post-clear observation while the App changes to 3003.
[Resource privacy isolation](resource-private-isolation.json) similarly holds
1,457 packets across 2,016ms while the App changes to 6006. Private-clear replies
continue during both windows, so this is not just a stopped reader. In the actual
browser, private mode hides images and resets/hides the canvas to 1x1. Resuming
produces the new marker, not the previous public frame. Already delivered data
and any interval before the observed clear are outside this assertion.

Initial generic reads leave owner=None. The explicit fixture hold controller
then owns the hold; frame viewing does not send phone input. The Runner log
records zero POSTs to native keys, atomic text, actions, clear or replacement.
[All native POST paths](native-post-paths.json) additionally contain only one
session setup and seven appium/settings requests; this is HTTP-route evidence,
not a global OS input-event trace.
The App/system UI may change independently; zero input requests does not mean
that nothing on the device can change.

## Scripts and evidence boundaries

`serve-mcp-live-browser-fixture.py` creates only its own Simulator and private
instance, checks the video listener, starts real peers, serves their exact HTML,
and forwards only frame-tool/frame-resource reads. The same-origin host has
fixture-only hold/counter/stop controls; daemon and Runner credentials stay in
the Python process/environment/private files, not the iframe. Its ready-serving deadline and
requested stop both trigger cleanup. A ready URL or zero exit code is not browser
acceptance; the image/receipt observations above supply that evidence.

`read-live-panel-counter.py` only observes the owned page's actual canvas. It
keeps mismatched observations and bounds the full CLI/OCR wait. Compile
`ocr-panel-image.swift` locally with xcrun swiftc and Vision, then pass that binary
with --ocr. [observer-deadline.json](observer-deadline.json) injects a delayed fake
CLI, contacts no browser, and confirms failure after about 206ms for a 200ms
budget. This is a separate hermetic timing check, not real rendering evidence.

[early-read.json](early-read.json) retains an initial read after the App accepted
5005 that still showed 4004. It was rejected; only subsequent read observations
were retried, without rewriting the counter. A later real canvas contained 5005.
No task latency claim is inferred from these manually orchestrated samples.

[aborted-setup.json](aborted-setup.json) retains an intentionally interrupted
pre-browser attempt whose copied configuration disabled the video listener.
It exited 130 and is not accepted. The live run uses a dedicated video port.
[live-results.json](live-results.json) keeps that run's executed source hashes.
Two stronger startup assertions were subsequently added for exact instance,
UDID and live process identity; [startup-results.json](startup-results.json)
checks the final harness, App receipt and packaged HTML only, with no browser
frame reads. The native/daemon/MCP binaries are the same. Source reconstruction
and final hashes are explicit in [source-verification.json](source-verification.json).
[daemon-identity.json](daemon-identity.json) independently confirms the live
run targeted its own Simulator and named instance.

Both successful runs stopped on request and reported no cleanup errors.
[cleanup.json](cleanup.json) independently verifies the owned tab is absent,
both Simulators and private credential/runtime folders are removed, and no
native input was dispatched. Other browser sessions/devices were not changed.
Current device inventory has no connected physical target; private device names
and identifiers are not published in this evidence.

## Reproduction

Build the candidate Runner for Simulator, plus daemon and MCP. Run
`python3 scripts/serve-mcp-live-browser-fixture.py --xctestrun <candidate.xctestrun>
--daemon target/debug/iphone-use --mcp target/debug/iphone-use-mcp --out <new-dir>`.
Open its printed URL with an owned chrome-use session; ?resources=1 selects the
resource path. Same-origin JSON POST /counter controls only this App fixture;
compare its receipt with actual canvas OCR, not only the response status. Private
hold/Resume test the real daemon hold. POST /stop after closing the owned tab.
The startup-only confirmation is not a substitute for these image checks.

## Still open

Actual product hosts and their trust/sandbox behavior, physical USB/Wi-Fi,
physical orientation, live failure-to-PNG recovery, long controlled soaks,
installed releases and same-condition reference tasks remain unverified.
The earlier PNG replay checks verify that component, not a live transport outage.
This work establishes owned-Simulator live viewing, not complete superiority.
