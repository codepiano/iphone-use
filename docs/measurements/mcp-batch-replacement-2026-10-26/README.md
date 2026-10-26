# Public MCP replacement batches, 2026-10-26

`phone_run_steps` now accepts snapshot-bound `set_value`, including its original
field index/snapshot, a complete value of up to 1000 Unicode scalars, optional
`recover_focus_after_clear`, and `after_ms`. HTTP batching already supported the
action; MCP previously rejected it during parameter deserialization. The codec
checks every step before sending the request. Unknown options, nonboolean
recovery, empty/oversized snapshots and oversized values refuse the batch.

A modifying step invalidates an earlier observation even when the page looks
similar. Put snapshot-bound replacement before other modifying actions. Earlier
pilots that tapped first correctly received `stale_element_snapshot`, with no
replacement input or Return. Those refusals are retained in
[earlier verdicts](earlier-cohort-verdicts.json), not counted as exercised focus
faults. Snapshot-bound live steps do not make durable saved-flow targets.

The [latest actual stdio MCP/daemon pilot](public-result.json.gz) uses an
experimental character Runner in a separate source tree, with product Native
sources unchanged. [Independent audit](independent-audit.json) verifies **16 of
17 observations**: seven completed controls/tasks and nine reached expected
stops. This is not 16 completed replacement tasks.

- Ordinary seeded/empty 501-character input, Unicode, multiline, selected
  replacement and clear-time handoff have exact App hashes. Unrelated fields
  remain unchanged; handoff restores the original once after clear.
- Character-20 and character-221 faults reach their markers with A20/B0 and
  A221/B0. Caller-selected replacement and focused typing both stop without
  refocusing. Reached App vetoes preserve values.
- Full/default MCP replacement batches use a nonmodifying pause before the
  snapshot-bound action. They retain completed=1, applied_actions=0, the unknown
  failed step, confirmed/uncertain/unsent character counts and clear receipt.
  The App's Return counter stays zero after failure. An explicit Return positive
  control increments it once, proving the suffix detector was exercised.
- Appending 501 characters to an existing 6015-character field fails: only one
  character lands (6016 total), and the API reports an unknown chunk. The
  existing experimental progress check is insufficient for this field. Its
  exact cause and a safe, performant correction remain open; this Runner is
  not adopted as the default backend.

The recovery gate now checks the real public `device_state:"degraded"` enum.
The previous code compared the internal advice name `read_failing`, so its
fixture-only tests missed the runtime mismatch. Actual sanitized metadata
samples are retained. Status-only waiting keeps the original 15-second budget;
strict ownership, privacy, target, lock and drivable admission remains before
input/reset. No text or unknown launch is replayed.

The [cold-launch sample](cold-launch.json.gz) independently verifies API success,
foreground bundle/PID and the owned App receipt in about 1.59 seconds, with no
text input. The earlier 1.76-second API-positive sample lacks its independent
postcheck because the first harness omitted the Runner record alias; it remains
incomplete. These runs use M4/Xcode27.0/iOS26.2 at normal runtime priority, with
compilation alone at background QoS. The earlier slow M5/iOS27.2 sample has a
different host/runtime; this is not a controlled QoS comparison or proof of a
production cold-start speed win. Input/request timeouts are unchanged.

[Validation](validation.json): server core 902 passed/1 ignored, MCP 306 passed/
1 ignored, recovery-gate verdicts 13 passed. The replay mock's lifetime now follows
its bounded request after client/runtime initialization; its arbitrary independent
five-second receive cutoff is removed, while the existing 20-second request
bound and exact-one-request assertion remain. Background `nohup` inherited
ignored SIGINT and broke a shell-based recording fixture; foreground recording
and the same concurrent core suite pass without changing the recording timeout.

[Cleanup](cleanup.json) confirms all six owned Simulators/services are absent.
[Experimental sources](experimental-sources.tar.gz) preserve the fixture's Return
counter and the SDK Runner patches; they are not product defaults or signed
packages. No real iPhone, independent model, actual domestic host, merge,
release or installed/downloaded artifact acceptance ran here. The long-field
failure and broader acceptance matrix keep the overall objective open.

A later [complete-value boundary followup](../complete-value-boundaries-2026-10-26/README.md)
identifies the truncated snapshot and completes this same protocol cohort in an
isolated revised Runner. The failed records above remain failures; promotion
still requires physical/public-path and compatibility evidence.
