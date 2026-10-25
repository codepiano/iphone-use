# Bound selected-field replacement, 2026-10-25

The former `set_value` path logged a failed clear and continued to type. That
could append to stale text instead of replacing it. Clearing and typing also
used separate legacy calls that could focus a different field between requests.

The candidate negotiates `ipu:elementReplace`. A new native prefix request
checks a live, enabled, geometrically visible nonsecure text target in the foreground, focuses
that explicitly selected element once, checks its identity again, then binds
clear and a bounded text prefix. Remaining chunks retain the original token and
check focus/process/identity; no fallback refocus or whole-action replay occurs.
Each prefix/chunk is at most 200 Unicode scalars. Conservative grapheme boundaries
are reused; a cluster that cannot fit refuses before prefix dispatch. The agent
entry keeps its existing 1,000-scalar replacement limit. Newlines in single-line
fields and secure replacements refuse before any clear/focus mutation. Legacy
runners retain their older typing mechanism, but clear failure is now terminal.

The current prefix/chunk can finish after a host-side owner/privacy change.
Subsequent requests are denied. Native request acknowledgement counts describe
requests, not a per-character delivery or rollback guarantee. A refused later
request cannot erase an acknowledged prefix. Final value readback that changed
unexpectedly or became unavailable is unknown, not retry-safe no_effect. An
unchanged original value after an acknowledged write can report value_not_applied.
Unknown transport/native outcomes
remain unknown, with separate confirmed/unknown request counts and no whole
replay advice. Successful prefix acknowledgement without a target token also
stops; it cannot trigger the legacy path.

## Actual candidate integration

[simulator-results.json](simulator-results.json) passes eight replacement groups
through the actual native Runner and daemon on an owned iPhone 17 / iOS 27
Simulator. The same run also rechecks complete-value reads through native,
daemon and read-only stdio MCP before any mutation.

- Native clear/prefix plus original-token tail gives the requested text.
- Single-line newline refuses before clear; secure refusal preserves focus.
- An external click invalidates the native token without appending elsewhere.
- Daemon replacement writes exactly 501 characters, verified by fresh AX and the
  App's own count/SHA-256 (`a7ff01017548ca392191a040cbfb8ebbe04d5295544867489b3c7d02a34f4344`).
- Empty replacement clears successfully and accepts an explicit null attribute.
- App-driven focus change during the first 200-character prefix leaves 20
  characters in the first field and 180 in the second, reports unknown, and
  dispatches no tail. This detects the change; it does not prevent every
  character of the current prefix from landing in the other field.
- A private hold starts after the fixture observes its first input event. The
  current prefix finishes with one confirmed native request, zero unknown and
  no tail; the original field contains 200 characters. The action remains
  partial and not safe to replay wholesale.

[verification.json](verification.json) records independent source/binary/fixture
hash checks and removal of the owned Simulator and private token/state folders.
Cleanup reported no errors. These are real Runner/daemon interactions with a
synthetic fixture, not a physical phone or real-client-host acceptance.

## Retained attempts

[first-attempt.json](first-attempt.json) retains the first actual Simulator
attempt. Native prefix/tail, newline refusal, secure refusal and external-command
binding invalidation executed, but the daemon replacement test addressed a
nonexistent row `element` property. Elements are addressed by their index in the
returned array. The harness stopped before daemon replacement, cleaned up its
resources and did not pass overall. The corrected harness retains that indexed
selection and uses independent post-operation reads and native route counters.

[null-clear-checkpoint.json](null-clear-checkpoint.json) records a subsequent
attempt: 501-character replacement matched a fresh AX read and the App-owned
count/hash, then an empty replacement incorrectly reported unknown because the
server collapsed a successful null attribute and a failed read into one None.
The final path preserves that distinction; malformed scalar responses refuse.
This attempt was not accepted. Its empty AssertionError string also exposed a
harness bug: the process exited 0 because it tested error text for truthiness.
The harness now checks error_type and requires all requested replacement cases.
[harness-negative.json](harness-negative.json) injects exactly an empty
AssertionError before fixture creation and verifies exit 1 with no Simulator or
child process launched.

[software-null-failure.json](software-null-failure.json) retains two parallel
library failures in the unedited setup coordination test; its three isolated
tests passed. CLOEXEC closes descriptors at exec, so other tests between fork
and exec can temporarily retain the descriptor. The test now explicitly checks
FD_CLOEXEC and requires reacquisition within two seconds while its already-exec'd
10-second child is still alive. It never accepts release from that child's exit.
The product lock code was not changed. Final parallel library/HTTP gates are
recorded separately below.

## Software checks

[software-checks.json](software-checks.json) records final log hashes and summaries:
893 server unit checks passed / 1 ignored; 170 HTTP checks passed, including
eight new replacement tests and their single/batch/failed-prefix permutations.
Locked workspace Clippy on Rust 1.96.0 passed with warnings denied. Candidate
Rust binaries, Simulator Runner and unsigned iOS device-architecture build passed;
the runner coherence gate and 278 native logic checks passed. No device was signed
or installed by the unsigned gate.

[prior-ci.json](prior-ci.json) separately records all three passing CI workflows
for prior full-value head f17d0c9. Replacement-head CI is tracked separately;
prior success is not acceptance of subsequent edits.

## Reproduction

Build a Simulator Runner and candidate binaries, then run
`scripts/test-value-read-simulator.py --xctestrun <candidate.xctestrun>
--daemon target/debug/iphone-use --mcp target/debug/iphone-use-mcp --replacement
--out <new-private-output-directory>`. The harness creates only its own disposable
iPhone 17 / iOS 27 Simulator. Mutation calls explicitly carry X-Phone-Control;
ordinary full-value reads and the read-only MCP phase do not. It keeps failed
results, removes its token directories and Simulator, and records the fixture,
Runner, daemon, MCP and relevant source hashes.

## Acceptance boundary

Actual integration, software results and exact source/binary identities are
recorded alongside this file. Physical devices, old iOS,
occluded or AX-poor fields, real client hosts, installed release artifacts and
paired reference task trials
remain outside this Simulator/software evidence. Earlier input cancellation,
privacy, video and list evidence remains separate. The competitive goal is not
complete.
