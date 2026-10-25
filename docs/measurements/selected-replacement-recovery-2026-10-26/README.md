# Verified original-field recovery after clear, 2026-10-26

Explicit `phone_set_value(..., recover_focus_after_clear:true)` now completes
both tested clear-time focus handoffs with the full requested 500 characters.
The default policy still stops. This closes that measured completion gap for
the opt-in selected-field operation; it does not resolve input-time segment
misdirection, establish a latency win or complete the competitive goal.

## Conditions and final records

- One physical iPhone 17 Pro Max, iOS 27.2, local-network connection. Only the
  owned fixture App and isolated test Runner identities were used.
- Source base `72f69ee06e7ec578f5908feeab6b2ed2890e365d` plus final native patch
  v8. [Provenance](provenance.json) verifies local/M4 source hashes and that the
  exact tested daemon/MCP binaries match the validated M4 binaries.
- Rust 1.96.0 debug daemon/MCP, Xcode 27.0 device build, local development
  signing and Xcode 27.2 beta 2 execution. [Candidate](build-receipt.json) and
  [old Runner](old-runner-build-receipt.json) receipts identify their executables.
- One new fixture binary adds fault markers and touch/action counters. Content
  is synthetic. Its own counts/hashes, PID, foreground/focus, selection commands
  and fault markers independently verify the final state. Public stdio MCP
  carries the original observation and explicit recovery policy.
- [Sixteen final records](results.json.gz), with native response-header profiles,
  pass the [state audit](final-summary.json). A refused requested replacement is
  not counted as a completed text task. No independent model session ran.

| Case | Final observed outcome |
| --- | --- |
| Ordinary A and originally unfocused B, 500 characters each | Both exact; other fields unchanged |
| App hands focus to B after clear, opt-in, twice | Both exact 500 in A; B's original six characters preserved; one App-recorded restoration touch each |
| Long empty replacement with opt-in | A empty; B focus retained; zero restoration touches; original clear verified |
| Same handoff with default policy | Stops after clear; A empty/B preserved; requested text incomplete |
| Old Runner with requested recovery | `replacement_focus_recovery_unsupported`, `not_sent`; unchanged hashes and zero edits |
| App repopulates A before restoration | Its 18-character value preserved; no restoration touch or replacement text |
| Original disabled, hidden or converted to secure | Each fault triggers; no restoration touch or replacement text; B preserved |
| New actionable button covers A | Overlay present, zero button actions and zero field touches; complete-scene guard executed |
| App repopulates A upon restoration | One touch, its 17-character value preserved; no second clear or replacement text |
| Ignored/partial Select All | Fault observed; unchanged hashes and zero editing events; selection/deletion is not replayed |
| App changes focus during text at character 20 | Still A20/B180, unknown/non-retryable; full request fails and no restoration occurs |

Native header receipts identify the two restoration taps and the empty-clear
verification. Reply times remain diagnostic: this small cohort has no resource
gate and is not a paired latency benchmark against reference. The preceding
[same-device reference comparison](../physical-iphone17-2026-10-25/README.md)
retains its original strict-policy results.

## Guards and retained failures

The [protocol contract](../../development/selected-replacement-recovery.md)
requires the same original AX field/PID/app/binding, verified empty value and
selection before restoration, and empty content again after at most one tap.
Neither deletion nor text is replayed. A current complete AX scene independently
rejects unrelated actionable controls covering the touch point; the check runs
before gesture setup and again immediately before dispatch.

An early build used an interface whose iOS implementation asserts that it is
macOS-only. A later point-query build did complete ordinary recovery, but the
overlapping-button case activated the fake button once. Refreshing only an
application snapshot did not fix that observed misclick. Those builds are not
the final implementation. A strict-mode read then showed both the original
field and overlapping button in the current scene; the independent scene guard
was added and the final case records zero button actions with that guard run.

[Rejected stages and the read-only scene diagnostic](retained-trials.json.gz)
retain these failures. Historical controller labels are not a substitute for
final executable/source provenance. [Executed controllers, fixture, auditor and
candidate patches](executed-harness.tar.gz) preserve the experiment; private
launch configuration, profiles, credentials and device identity inventories are
excluded. The archive is an audit record, not an installer.

## Validation, cleanup and limits

[Validation](validation.json), with [lossless test logs](validation-logs.json.gz):

- Server library: 897 passed, one existing ignored.
- MCP all targets: 303 passed, one existing ignored; includes the actual stdio
  policy-forwarding check. Production-target Clippy passes on Rust 1.96.0.
- Native device build and 296 device-independent checks pass.
- 29 existing input/owner/privacy/recovery Simulator checks pass on iOS 26.2
  with native v7; v8 adds the early opt-in scene check and a refusal-message
  clarification, leaving that default path unchanged. Two TCP-disconnect
  observations remain causally unproven and are not promoted to cancellation.

An initial fake recording test timed out handling SIGINT in the background
controller. The controlled launcher records ignored SIGINT before normalization
and default SIGINT afterward; its directed retry and subsequent full suite pass
without changing recording implementation. The initial failure log is retained.

[Independent cleanup](cleanup-audit.json) verifies removal of the two owned
test apps, original Runner/Phone Use Remote still installed, no test listeners
or header proxy, and the default daemon offline/unowned. Original-field checks
remain subject to the existing request boundaries. AX-hidden/custom-drawn
obstacles, rapid UI races, other Apps/versions/transports, actual models, real
installed hosts and downloaded-release acceptance require further evidence.
The known 200-character in-flight risk remains open.
