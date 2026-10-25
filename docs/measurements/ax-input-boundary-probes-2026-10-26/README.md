# AX input boundary probes, 2026-10-26

An isolated prototype completes one independently verified 501-character append
on the physical iPhone 17 Pro Max/iOS 27.2 in 8.286 native seconds (8.359 seconds
for the native HTTP route). The original field contains exactly `old` plus the
501 requested characters; the other fields remain unchanged. Its character-20
focus fault reaches A20/B0, its focused TextView sample matches the requested
multiline value, and the requested TextField's delegate veto stops after one
callback with unchanged fields. This is one successful long-input sample, not a
passed physical cohort, a paired latency win or a shipped backend.

Both incomplete physical cohorts are retained in
[physical records](boundary-physical.json.gz):

- The first long request loses its response after a CoreDevice/Mercury connection
  invalidation. XCTest attempts to restart its test process. The controller sends
  no replacement input, stops its processes and removes its fixture. No final App
  receipt was preserved, so delivery remains unknown. The diagnostics do not
  establish whether the prototype caused a crash; filtered device crash-list
  metadata returned no matching report, and the interrupted xcresult had no root
  ID for diagnostics export.
- A fresh installation and fresh trials complete the four records described
  above. The subsequent empty-field case receives a native response, but its
  foreground postcheck changes before the response/App receipt is persisted.
  The harness stops. That request remains unverified; it is not a second passed
  long task. The improved controller preserves an in-flight descriptor before
  sending and attempts an owned-container readback on a lost response, without
  converting unknown delivery into success or replaying input. This later
  foreground-refusal path still lacks its final response/readback artifact.

The optimization changes observation placement. The previous private prototype
reads the full target and foreground both after one character and again before
its immediate successor. This prototype takes one complete live check before
its first action and after every action, then uses the same boundary observation
for the immediately following dispatch. Only local value comparison, registry
renewal, deadline and binding/generation checks intervene. There is no wait,
run-loop pump, asynchronous work or other remote operation between that
observation and the next dispatch. Observations are never reused across requests,
errors or a recovery operation. The existing identity, process, type, enabled,
visibility, focus, foreground and binding predicates remain. This ordering does
not establish atomic isolation against an arbitrary asynchronous App change.

The [Simulator records](boundary-simulator.json.gz) retain 17 cases, including
expected refusals and ordinary typing controls. Three 501-character samples
finish exactly in 3.145–3.241 native seconds, each with 502 live boundary checks;
the character-20 fault uses 21 and reaches A20/B0. Reached focused field vetoes
retain unchanged values and one refused callback. The ten-second experimental
budget is unchanged. These native experimental requests still differ from the
public MCP/daemon 200-character chunk pipeline.

A separate [readonly attribute schema probe](attribute-schema.json.gz) compares
three samples on each of three fixture fields. App fields/edit events remain
unchanged. Batched remote attributes are faster in these samples, but raw
`ElementType` is a UIKit class string; the numeric XCTest type is `AutomationType`.
Keyboard focus/enabled state require traits interpretation, while native focus
alone remains false for the focused field. That alternative is not substituted
for snapshots or adopted in the product.

[Audit](audit.json), [binary identities](build-identities.json) and
[executed source patches/controllers](prototype-sources.tar.gz) retain the
sample boundaries. [Cleanup](cleanup.json) independently confirms both owned
Simulators and their service processes are absent, M4 native sources restored,
both physical installations removed, all 21 pre-existing Apps preserved and test
ports closed. The original default service remains offline/unowned. Credentials,
profiles, device identifiers, signed products and diagnostic archives are excluded.

Latest source-base CI run [40243760599](https://github.com/leeguooooo/iphone-use/actions/runs/40243760599)
has a retained [first-attempt failure](ci-attempt-1.json.gz): iOS 17.5 passes;
iOS 18.2 passes 13 gesture/input cases, then times out reading AX while preparing
first-focus-typing-0, whose case directory has no receipt. Its recovery suite
never runs. The failed job's
[second attempt](ci-attempt-2-ios18.2.json.gz) passes all 16 gesture/input and 15
recovery observation contracts. iOS 17.5's first attempt passes the same counts.
The recovery contracts include expected stops and retained known limitations;
they are not 15 successful replacement tasks. The [exact artifact ID](ci-artifact-identity.json)
matters: both attempts have the same artifact name, and name-based download
selected the older failed artifact. Earlier paired CI success remains separate.

The accompanying simulator harness change records preparation/postcondition
failures as failed cases, with their phase and whether input may have been
attempted. It preserves a received reply when a subsequent read fails. Eighteen
offline verdict checks pass, including zero sends on preparation failure and
exactly one possibly delivered batch after response loss. Assertions, timeouts
and retry rules are unchanged. The new harness revision still needs its own
hosted run; these downloaded CI artifacts precede that diagnostic-only change.
No default input change, model session, merge or release ran here.
