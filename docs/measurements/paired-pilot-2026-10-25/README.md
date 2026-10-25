# Paired operation diagnostics, 2026-10-25

This is an exploratory, model-free Simulator comparison. It does not establish
physical-device behavior, end-to-end task superiority, model turns, performance
superiority or release acceptance. Participant failures remain in the records.
An experiment exit code of zero means the harness completed and cleaned up;
it does not mean all requested operations succeeded.

## Controlled inputs and independent receipts

- Reference: `zhongerxin/iPhone-use` at
  `3ce9c080534e89fab91a237bf1c53a4a7e9d80a7`, unmodified.
- Its pinned Appium WDA 16.14.0:
  `d17782422d55ff1e5e0ceb74eb1fd509cc0c35b6`, unmodified source.
- Native candidate: `32916100067bf0d6aa181038b799510abe18dbeb` plus
  the exact per-run `native-tracked.patch.gz`. The clear implementations differ
  between diagnostic versions; do not pool them as one candidate.
- Public stdio MCP operations, one backend at a time. Reference analytics were
  disabled. Both participants requested 60 characters/second; the reference's
  documented default is 30. No uncertain input was replayed.
- One owned iPhone 17 Simulator, one compiled fixture App per experiment.
  Fixture receipts independently record actual field counts/hashes, focus,
  editing-event counts, process ID and the injected focus-change trigger.
- The M4 lane uses Xcode 27.0 and iOS 26.2. Earlier local pilots use Xcode 27.1
  and iOS 27.0. These lanes are separate. Each result retains source, fixture,
  daemon, MCP and runner hashes, raw replies and cleanup results.

Untimed setup observations are retained in [the setup archive](setup-receipts.tar.gz),
with [per-receipt hashes and paths](setup-receipts-index.json). Failed setup
polls remain included; the archive keeps repeated observations out of the source
diff while preserving their original bytes.

## Completed ABBA functional pilot

See [raw results](remote-diagnostics/paired-v6-file-functional/results.json)
and [executed native patch](remote-diagnostics/paired-v6-file-functional/native-tracked.patch.gz).
Order: native, reference, reference, native; 24 records, including four warmups.
The fixture resets its own drafts between requests, within the same process.
Reset happens outside the measured operation and never during injected input.
Backend changes start a new fixture process. The final sources match the initial
hashes, all prior services stopped before the next backend, and cleanup reports
no errors.

| Operation | Native V6 | Reference |
| --- | --- | --- |
| Inventory of all four fields, full output | 2/2 complete | 2/2 complete |
| Read the seeded 6,015-character field | 2/2 complete, App hash matches | `pua_find` returns 512 characters in both runs |
| Replace a short draft with 500 characters | 1/2 complete; one unconfirmed Select All, original text unchanged | 2/2 complete |
| Switch A to B at character 20 during a 500-character input | Both stop after the current 200-character chunk, reporting unknown; B receives 180 characters | Both continue; B receives 480 characters |
| Input into the secure field | Both refuse, field hashes/events unchanged | Both refuse, field hashes/events unchanged |

The focus-injection runs are failed requested-text postconditions for **both**
products. Native postflight prevents the remaining 300 characters from being
sent, but does not provide per-character field isolation. Reference calls used
`verify=false`; its response explicitly defers verification. A non-error reply
must not be interpreted as an independently verified successful task.

This proves a useful full-value reader and a working native chunk boundary,
while exposing our weaker replacement reliability. It does not prove that the
reference cannot obtain long content through another operation. Samples are
small and CPU load was uncontrolled (one-minute load 37–96); timings are retained
for diagnosis and are ineligible for a latency-win claim.

## Failed pilots and unresolved clearing

Earlier local pilots and the remote diagnostics are retained, including rejected
AX setter experiments, resource-gate aborts, a post-operation diagnostic timeout,
and fixture initialization failures. The rejected AX setters are not the V6
implementation. V6 uses a process-targeted keyboard event and checks the original
AX value and full selection before allowing one delete. An unconfirmed selection
stops without delete or replacement text.

Relaunch pilots show that a focused field is not sufficient evidence that the
system keyboard is ready. The later fixture records keyboard notification and
its own selected range. The reference relaunch control also failed fixture
readiness after a prior long input. These setup failures are not participant
task failures, and no operation was sent after a failed setup.

Even with a keyboard-ready receipt, native Select All remains intermittent,
including the final ABBA native replacement. The old three-character value and
zero editing events are preserved in that failure. Neither the process-tracker
change nor a successful individual replacement establishes a relaunch fix.

The V7 targeted Clear-key experiment also leaves the original text unchanged;
it is a failed experiment, not an adopted clearing implementation. V8 chooses a
bounded short-field deletion sequence before sending any input. Its relaunch
pilot completes the replacement and triggers the injected focus change, and
the [separate integration run](remote-diagnostics/native-clear-v8-regression/results.json)
passes 34 cases with no cleanup errors. This is an intermediate candidate:
caret position, composed characters and length boundaries need additional
checks before accepting the final deletion plan.

The first local inventory check used native slim output, which intentionally
omits some unique-label identifiers. Later full-output runs return all fields.
The original strict slim check remains a failure in the pilot record; this is
an output-mode difference, not evidence of a missing AX TextView.

Physical transports, real client hosts, wider App coverage, healthy-resource
timing trials, actual model tasks and downloaded-release acceptance remain open.
