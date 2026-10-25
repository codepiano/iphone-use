# Physical iPhone operation checks, 2026-10-25

The candidate now has physical-device evidence on one iPhone 17 Pro Max running
iOS 27.2, connected over the local network. Ordinary replacement succeeds for
both participants. Our dedicated reader returns the complete 6,015-character
field; the tested reference `pua_find` returns 512. Reference completes the
clear-time focus-change task that our guarded default stops. Neither participant
keeps all text in the original field during an input-time focus change.

These are small, model-free operation cohorts in an owned fixture App. They do
not establish overall task, latency, physical-device coverage or model superiority.

## Conditions

- Candidate source: `e73f777c73b0bd40c9ba841c830a530d99a87039`. Native Runner
  sources match the previously compiled device candidate byte for byte; the
  [source hashes](runner-source-hashes.json) retain that check. The daemon/core
  source is unchanged from `4f70209e89ed8d369ff1952568842cfd52034968`.
- Reference MCP: `zhongerxin/iPhone-use` at
  `3ce9c080534e89fab91a237bf1c53a4a7e9d80a7`, using its pinned WDA 16.14.0 at
  `d17782422d55ff1e5e0ceb74eb1fd509cc0c35b6`. Source trees are unmodified.
- Device bundles were compiled on the verified M4 build host with Xcode 27.0,
  iPhoneOS 27.0, arm64. Signing and execution used the current Mac; execution
  used Xcode 27.2 beta 2. Both Runner packages received isolated bundle IDs and
  development signatures, without changing their source implementations.
  [Native](build-receipt.json) and [reference](wda-build-receipt.json) receipts
  identify the unsigned/signed test executables. [The manifest](manifest.json)
  also identifies the daemon, MCP and fixture binaries/source.
- One compiled fixture binary is reused throughout. Resets affect only its
  synthetic fields. Its independent receipts retain field hashes/counts,
  foreground state, process ID, focus, selection commands and edit events.
- Public stdio MCP calls, matched typing frequency 60, reference settle zero
  and `verify=false`. Reference analytics are disabled. No independent model
  sessions were started. Reference acknowledgements are distinct from the
  independently checked requested-text postcondition.
- This is a functional lane without a host-load gate. Host/network overhead,
  Debug builds and a small sample make response times diagnostic only.

## Paired operations

The first four blocks are native, reference, reference, native, with four
operations per block. A separate native/reference pair probes input-time focus
change. [Summary](paired-summary.json), [lossless replies and App receipts](paired-results.json.gz).

| Operation | Native candidate | Reference |
| --- | --- | --- |
| Fresh title and all four required field identifiers | 2/2 | 2/2 |
| Read the seeded long field | 2/2 exact, 6,015 characters | Both tested `pua_find` reads return 512 |
| Replace the focused field with 500 characters | 2/2 exact; other fields unchanged | 2/2 exact; other fields unchanged |
| App focuses B when clear empties A | Both stop; A empty, B's six characters preserved | Both re-focus A and finish 500 characters; B preserved |
| App changes focus at character 20, separate pair | A gets 20, B gets 180; remaining 300 not dispatched | A gets 20, B gets 480 |

Clear-time focus change remains a task-recovery advantage for reference. Both
participants preserve B, so this is not a reference safety failure. Input-time
focus change fails the full requested-text postcondition for both products.
Native's current 200-character segment can still reach a different field;
stopping subsequent segments is not per-character isolation. The long-read
comparison describes the tested operation, not every possible reference method.

## Additional native entry and fault checks

[Twelve native cases](native-summary.json), with
[lossless replies](native-results.json.gz), check the new `phone_set_value`
entry point and clear/read behavior:

- Originally unfocused B receives exactly 501 characters through one MCP call;
  A, multiline and secure dummy field hashes remain unchanged.
- Middle-caret, Unicode-seeded and first-Select-All-ignored replacements each
  produce exactly 64 requested characters. The ignored-first case records two
  selection commands. These four ordinary replacements are 4/4 exact.
- The dedicated reader returns all 6,015 characters, matching the App's hash.
  Clearing that long value leaves A empty and the other fields unchanged.
- Ignoring all Select All commands stops after two commands with unchanged
  field hashes and zero edit events. Partial selection stops after one command,
  also without an edit. Both retain an unknown/non-retryable protocol verdict;
  the test does not replay the text.
- An App-driven same-length value change is preserved; the App records its
  single edit and one selection command. Secure input is refused before input,
  with unchanged hashes and zero edit events.
- Clear-time and input-time focus changes reproduce the limitations above.

Expected refusals and observed guarded stops are not counted as successful
requested replacements. In particular, matching the expected 20/180 diagnostic
does not turn misdirected input into a successful safety test.

## Startup, cleanup and remaining coverage

The first launch timed out enabling automation mode. After the user handled
the phone-side readiness state, the Runner became ready; this does not prove
which setting or prompt caused the first failure. A separate controller attempt
was rejected before input because `/tmp` resolves through a symlink; using
`/private/tmp` fixed that harness prerequisite. [Both failed attempts](retained-startup-failures.json)
remain separate from the completed input cases.

The [executed harness](executed-harness.tar.gz) retains native controllers,
paired controller, auditors, fixture and protocol helpers. Private credentials,
provisioning profiles, device serial/UDID inventories and raw environment logs
are excluded. Some executed scripts contain local artifact paths and depend on
the private launch configuration; this is an audit record, not an installer.

[Cleanup](cleanup-audit.json) independently verifies that all three owned test
apps were removed, the original Runner and Phone Use Remote remain installed,
test listeners are absent, and the default daemon remains offline/unowned.
No daily App was used for a test task. USB, rotation, long sessions, other Apps,
older iOS versions, actual model tasks, installed host panels and downloaded
release acceptance remain open. The broader competitive goal is not complete.

A later [opt-in selected-field recovery lane](../selected-replacement-recovery-2026-10-26/README.md)
completes the two tested clear-time handoffs with additional original-field and
scene guards. Keep its explicit policy and newer fixture/provenance separate
from this strict-policy cohort. Input-time segment misdirection remains open.
