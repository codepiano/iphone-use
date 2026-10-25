# Paired operation diagnostics, 2026-10-25

The final functional candidate completes 12/12 ordinary 500-character replacements
on the owned Simulator; the unmodified reference completes 12/12. Our dedicated
reader returns the seeded 6,015 characters, while the tested reference `pua_find`
returns 512. Native postflight stops later input chunks after a focus change,
but the current chunk can still reach another field. These are operation-level
results, without a conclusion of overall task, physical-device or model superiority.

## Conditions and evidence

- Reference: `zhongerxin/iPhone-use` at
  `3ce9c080534e89fab91a237bf1c53a4a7e9d80a7`, with its pinned Appium WDA 16.14.0
  `d17782422d55ff1e5e0ceb74eb1fd509cc0c35b6`. Both repositories remain unmodified.
- Candidate: `4f70209e89ed8d369ff1952568842cfd52034968` plus the
  [executed patch](final/paired/native-tracked.patch.gz). Actual source and binary
  hashes identify each lane. The daemon/MCP are debug builds; XCTest bundles
  use Debug configuration.
- One owned iPhone 17 Simulator, Xcode 27.0, iOS 26.2, one compiled fixture App
  per experiment. Backend order is native, reference, reference, native. Only
  one controller serves at a time. Drafts reset inside the fixture between
  requests, outside operation timing. Backend changes start a new App process.
- Actual public stdio MCP calls, 60 characters/second for both participants and
  reference settle zero. Reference's documented default is 30 characters/second;
  these are matched configurations rather than default-configuration timings.
  Reference analytics are disabled. No uncertain deletion or text is replayed.
- The App independently records counts/hashes, focus, editing events, process
  identity and injected-fault triggers. A successful harness exit means the
  experiment finished and cleaned up; participant postconditions are separate.

[Manifest](final/manifest.json), [readable paired records](final/paired/summary.json),
[lossless raw replies](final/paired/results.json.gz) and the
[executed harness](final/paired/executed-harness.tar.gz) preserve the trial.
All six recorded lanes report no cleanup errors; [the cleanup audit](final/cleanup-audit.json)
also finds their six owned Simulators absent from the device inventory.
Sources remain unchanged within the paired run.
The [acceptance audit](final/acceptance-audit.json) independently checks recorded
postconditions and artifact hashes. [Setup receipts](final/paired/setup-postconditions.json.gz)
retain App field hashes and foreground process identity; readiness replies and
process environments are omitted.

## Final functional results

There are 48 records, including four warmups. Ordinary replacement uses six
initial states, twice per participant: short text, a middle caret, Chinese/emoji
and a combining character, 100/101-character boundaries, and the 6,015-character
field. Each requested replacement is 500 characters.

| Operation | Native candidate | Reference |
| --- | --- | --- |
| Inventory of all four field identifiers, full output | 2/2 complete | 2/2 complete |
| Read the seeded 6,015-character field | 2/2 exact, App hash matches | Tested `pua_find` returns 512 in both runs |
| Ordinary 500-character replacement | 12/12 exact | 12/12 exact |
| Switch A to B at input character 20 | Both runs stop after the current 200-character chunk; B gets 180, outcome unknown | Both continue; B gets 480 |
| App focuses B when clear empties A | Both stop, leaving A empty and B's original six characters untouched | Both re-focus A and finish its 500 characters; B remains untouched |
| Input into the secure dummy field | Both refuse, hashes/events unchanged | Both refuse, hashes/events unchanged |

The mid-input focus injection fails the requested-text postcondition for both
products. Native prevents the remaining 300 characters from being dispatched;
it does not provide per-character isolation. Reference was called with
`verify=false` and explicitly defers verification. Its non-error acknowledgement
is not an independently verified successful task.

The clear-time focus case is a policy observation with separate stop-policy and
requested-text verdicts, excluded from an aggregate pass score. Reference
completes the requested replacement in this fixture; our guarded default stops.
This remains a task-recovery gap. Our result must not be described as an overall
completion-rate advantage. The long-read result describes the tested operation,
not every possible way the reference could obtain long content.

The functional lane has no resource gate; one-minute host load ranges from
3.10 to 86.72. Its response times remain diagnostic and cannot establish a speed
win.

## Resource-gated operation timings

The [separate timing lane](final/performance/summary.json) has 68 records,
including four warmups, on the same 10-core M4/16 GiB host. It waits 180 seconds
after boot and admits each tool operation only at one-minute host load <=8.
Observed dispatch-time load ranges from 2.79 to 7.75; swap is zero in both
[preflight](final/performance/preflight.json) and
[postflight](final/performance/postflight.json). The benchmark driver uses the
ordinary MCP call envelope; host-load instrumentation stays local.

Each inventory additionally requires the trial's changing App title in the
response. Both participants satisfy all ten fresh-title/required-field reads
and all twelve ordinary replacements. Source and fixture hashes are retained,
with [statistics](final/performance/statistics.json) and
[lossless replies](final/performance/results.json.gz).

| Metric | Native candidate | Reference |
| --- | --- | --- |
| Fresh required-field inventory response, median (range), 10 samples | 47.79 ms (27.51–65.60) | 50.73 ms (45.38–53.23) |
| 500-character replacement response, median, 12 samples | 9.648 s | 9.401 s |
| Independent replacement postcondition observed, median | 10.046 s | 9.788 s |
| Inventory normalized reply JSON size, median | 7,016 bytes | 4,842 bytes |
| Exact long-field reads | 10/10, 6,015 characters | 0/10, tested `pua_find` returns 512 |

The replacement observation includes the same approximately 350 ms stable-state
window for both products. Read response ranges overlap, and native replacement
is slightly slower in this cohort. These data establish no general speed win.
Long-read latency is not compared as equivalent work because only one participant
satisfies that requested value.

The legacy `wire_bytes` field counts replies reserialized with the same JSON
encoder; it is not a transport-byte or billed-token measurement. Native uses
full structured output for the identifier task. Its inventory replies contain
13 or 68 rows, versus 61 reference nodes, so this is a task-complete required-field
comparison with different extra UI content, rather than a pixel-matched full-tree
throughput test. Native text is shorter but the full reply is larger here;
effective model cost still needs measurement in actual hosts.

## Native clearing and empty-value checks

The candidate plans only the deletion keys required by a short field's observed
value/selection, bounded to 100 UTF-16 units. Other caret positions or larger
values require a confirmed full selection before one delete. An acknowledged
Select All with unchanged value and selection across readbacks may repeat once,
after rechecking the original binding and comparing the exact original state.
Synthesis/read failures, changed values and partial selections stop immediately.
The private retry value is neither serialized nor logged. A current event can
still cross an App-driven focus/content change.

[Repeated short/middle-caret input](final/repetitions/summary.json) completes
40/40 replacements using 64-character atomic input across two Runner/App
processes. [App-driven selection faults](final/selection-faults/summary.json)
cover each mode twice:

| Fixture behavior | Observed result |
| --- | --- |
| Ignore the first Select All | Both complete; App records two selection commands |
| Ignore every Select All | Both stop after two commands; no edit events or replacement text |
| Change the value to a different string of the same length | Both stop after one command; only the App's one edit event, changed value preserved |
| Select only part of the value | Both stop after one command; original value and zero edit events preserved |

These negative cases retain failed requested-text postconditions alongside the
independent expected-refusal evidence. They are not added to an ordinary task
completion score.

The [selected-replacement lane](final/selected-replacement/summary.json) passes
the existing eight groups: native prefix/tail, invalid newline and secure
refusal, target invalidation, a 501-character daemon replacement, empty clears,
mid-prefix focus interruption and privacy interruption. It adds independent
placeholder counterexamples. With `max_utf16=1`, literal `Draft placeholder`
remains real 17-character content, returning `D` with explicit truncation. After
clearing, the App reports zero characters and the reader returns empty/complete
with `placeholder_shown=true`. The raw comparison flag never reaches the public
result. Both states match App-owned hashes.

[Input/permission/recovery integration](final/input-regression/summary.json)
passes 34 cases. [Build validation](final/build-validation.json) records 278
separate device-independent logic checks and an unsigned iOS build. These checks
do not replace the actual AX/keyboard fixture runs.

## Selected replacement through the MCP entry point

The new `phone_set_value` tool exposes the daemon's selected-field operation to
MCP clients. A separate [actual stdio receipt](selected-mcp-entry.json) records
one invocation on an owned Simulator: the caller passes the exact observation
token and B's index while A initially has focus. B receives all 501 requested
characters; App-owned hashes confirm A, the multiline field and the secure dummy
remain unchanged. This is a single entry-point acceptance case, not an additional
paired/model benchmark. The MCP binary was built with Rust 1.99.1; its hash is in
the receipt. The controller reports no cleanup errors and independently finds
its owned Simulator absent afterward.

The tool forwards the original snapshot without substituting or refreshing it,
defaults to observed output and retains daemon delivery verdicts. Its stdio
regressions cover Unicode forwarding, default observation/empty clearing,
rejection before dispatch and no mutation replay after an unknown outcome.
The [local validation record](selected-mcp-validation.json) records Rust 1.96.0
MCP all-target tests (302 passed, one existing ignored) and all-target Clippy.
Supporting native Runners retain the original field across clear/chunks; older
Runners keep their existing clear/type behavior.

## Retained failures and limits

The [earlier ABBA candidate](remote-diagnostics/paired-v6-file-functional/results.json)
completed only 1/2 ordinary replacements, versus reference 2/2; it failed before
delete and preserved the original value. Later failures include ineffective
forward-delete events, an acknowledged Select All with no effect, and the
empty-field regression where raw AX Value returned a placeholder while the App
and snapshot reported empty. The final candidate addresses the observed cases;
it does not identify one proven cause for every OS/key-event miss.

[Intermediate diagnostics](intermediate-native-diagnostics.tar.gz), with
[per-file hashes](intermediate-native-diagnostics-index.json), preserve V9–V14
trials and failures. Earlier rejected AX setter experiments, resource-gate
aborts, a post-operation diagnostic timeout and initialization failures remain
in `remote-diagnostics/`. Rejected setter/Clear-key experiments are not the final
implementation. Earlier setup receipts remain in [their archive](setup-receipts.tar.gz)
with [an index](setup-receipts-index.json).

Local pilots used Xcode 27.1/iOS 27.0 and a heavily loaded 16 GB Mac; they remain
a separate lane. One slim-output inventory check intentionally lacked a
unique-label TextView identifier and remains a strict-check failure. Subsequent
full output returns all fields; the slim result does not establish missing AX
content. Relaunch controls also exposed keyboard readiness failures in both
products; no task is dispatched after failed fixture setup.

Physical transports, real installed hosts, wider App/provider/version coverage,
broader performance acceptance, actual model tasks and downloaded-release
acceptance remain open. The broader competitive goal is not complete.
