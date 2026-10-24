# Privacy transition validation

Three scripted-runner checks failed on the prior candidate. A private hold
starting during a screenshot still returned 200; a hold beginning and ending
before completion also returned 200; a later screenshot reused the old settled
frame. `reproduction-before.txt` preserves the original failed run. It contains
only synthetic fixtures, not phone data.

## Candidate behavior

Screenshot, overlay/re-encoding, element and OCR responses are fenced by the
privacy generation captured at entry. Active privacy returns 423/screen_private;
a completed private transition returns 423/screen_privacy_changed. Work is
cancelled without retry; an already sent native capture can still finish. A
queued body is checked again outside timing middleware when published and
fails with a read error if privacy changed after handler completion. Rejected
reads clear unserved snapshot baselines. Settled image reuse is fenced and its
background producer is cancelled/generation-checked across a hold. Normal cache
reuse without a transition remains available.

MJPEG/H.264 HTTP feeds retain their opening generation and end even if privacy
is lifted before the next frame arrives. The video producer and asynchronous
VideoToolbox callback use a generation-bound publication sink; private changes
and publication share a lock. Old callbacks and JPEGs cannot enter the next
generation. Old subscribers cannot authorize a restart or extend capture linger;
a new subscriber can restart after the old producer drains. The hold and hub
change are serialized before publishing the new private state to readers.

MCP capture HTTP 423 now clears the panel's previous frame, including when a
parallel status read still said the screen was open. This uses the typed HTTP
status rather than searching an error message. Generic/Doubao tool frames and
WorkBuddy resource frames share the behavior.

## Software checks

- Server library: 886 passed, 1 ignored. Related HTTP checks: 126 passed
  (107 auth/HTTP, 6 privacy, 4 recovery, 1 overlay, 8 sized screenshot).
- Six privacy test functions cover six delayed image/overlay/AX cases,
  settled-cache invalidation, two real HTTP streaming paths, queued publication
  and cancellation of a stalled capture. Private holds
  are taken/lifted through the actual router, not by changing global environment.
- Three new video unit cases cover a delayed publication callback, JPEG reuse,
  subscriber accounting/linger and a new viewer during an old producer's delayed
  HTTP handshake. The two-connection source sends distinct old/new timestamps;
  the fresh subscriber receives only the new timestamp.
- MCP library: 233 passed, 1 ignored; real stdio: 23 passed. The added case
  races an open status with a 423 capture through both tool and resource paths.
- The actual panel script clears its prior image for that raced refusal in both
  simulated host modes, as well as for an active private status.

The queued-body prototype initially prevented timing middleware from adding its
JSON timing field. The existing auth/HTTP regression caught it. The publication
fence now runs outside that middleware; all 107 auth/HTTP cases pass again.
`software-checks.json` retains both passing log hashes/summaries and that failed
checkpoint. No failed check is counted as acceptance.

## Actual daemon / runner integration

`simulator-attempt-1.json` records 25 passed cases through the candidate daemon,
XCTest runner and stdio MCP on a disposable iPhone 17 / iOS 27 Simulator. The
prior 24 input/continuation/cancellation/recovery/host checks still pass. The new
case verifies a WorkBuddy resource frame during a real private hold: frame=null,
clear_frame=true, then a valid PNG from a new read after unhide, without keyboard
input. Listed source and executable hashes match; cleanup and simulator deletion
were checked. This is backend integration, not actual WorkBuddy UI acceptance.

## Limits

These race checks use scripted runner/video sources and synthetic bytes. They
are not physical-device timing, VideoToolbox hardware or actual-host acceptance.
Data already delivered before a hold cannot be withdrawn. The fences cover these
read/stream paths; mutation and batch observation payloads, other metadata reads,
pending continuations across private holds, installed packages and all
transport/device modes still require their own audit.
The broader comparative goal remains incomplete.
