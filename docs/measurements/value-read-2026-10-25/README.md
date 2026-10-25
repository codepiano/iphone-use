# Selected AX value reading, 2026-10-25

The owned iPhone 17 / iOS 27 fixture contains 6,015 characters. The old snapshot
and value attribute returned only 512. The fixture independently writes its
character count and SHA-256 from its own UITextField value, so a short AX preview
is not treated as input loss or as complete readback.

The candidate requests `XC_kAXXCAttributeValue` for one current native element.
`ipu:valueRead` negotiates support. The structured native GET, read-only
`POST /agent/value` and MCP `phone_read_value` return one bounded value with
source, UTF-16 counts and explicit complete/truncated booleans. Defaults are
32,768 UTF-16 units for native GET and 8,192 for agent/MCP; the maximum is 65,536.
An intentional cut preserves Unicode scalar boundaries. Bulk rows preserve the
provider's `value_truncated` marker without expanding every field. Older runners
or malformed contracts refuse rather than turn a preview into a full value.
Secure fields refuse. Exact selectors must resolve uniquely. The operation does
not tap, focus, wake, reconnect or take an owner lease. Foreground/identity checks
surround the native read; owner/privacy generations fence queued, in-flight and
late response publication. A late withheld body can retain HTTP 200 with
`ok:false`; MCP treats that body as an error.

## Actual candidate integration

[simulator-results.json](simulator-results.json) records the actual native Runner,
daemon and stdio MCP binaries, source hashes and independent fixture oracle.

- Complete 6,015-character attribute equals the App-owned SHA-256 through the
  compatibility attribute, structured native GET, daemon and MCP.
- A 128-unit limit returns 128 characters with truncated=true and total=6,015.
- Three UTF-16 units over `🙂🙂value` return one intact emoji (two units).
- The ordinary element preview remains 512 characters with value_truncated=true.
- Duplicate exact labels refuse; native and daemon secure reads refuse without
  the fixture secret. Read-only MCP emits the long value once, without a second
  structured copy. Owner state and focus remain unchanged.
- The test deletes its own Simulator, stops its Runner/daemon/MCP, removes token
  state and redacts fixture-token logs. Cleanup reported no errors.

[combined-simulator-results.json](combined-simulator-results.json) additionally
passes all 39 existing target-input, continuation, cancellation, privacy,
recovery, host-protocol, native-video and list cases with the same candidate
binaries. The real queued list request returns at 80.015 seconds with zero later
reads/swipes after the original input naturally completes. Both the App-owned
oracle and the AX attribute now read back 6,015 characters. No owner/privacy
transition was used to force the queue probe to stop. Raw TCP disconnect remains
an observation with unproven stop causality, not an accepted cancellation claim.

The source/binary hashes were checked independently against the candidate files.
A subsequent whitespace-only script cleanup is recorded separately in
[script-format-verification.json](script-format-verification.json); runtime
results retain the source hash that actually executed.
No personal phone, user app data or real client application was used.

## Software checks and retained attempts

[software-checks.json](software-checks.json) records terminal log hashes and
summaries: server 893 passed / 1 ignored plus 156 HTTP checks; MCP 247 passed /
1 ignored plus 29 stdio checks; 278 native logic checks; locked workspace Clippy
on Rust 1.96.0 with warnings denied. Candidate daemon/MCP and Simulator Runner
builds passed. The unsigned iOS device-architecture build and runner coherence
gate also passed; this is compilation only, without signing or installation.
The new HTTP cases cover selection, old/malformed contracts,
read-only access and withholding across in-flight and late privacy changes.

Retained checkpoints:

- [before-native-value.json](before-native-value.json): the independently seeded
  6,015-character value was exposed as 512 characters before the native change.
- [full-value-checkpoint.json](full-value-checkpoint.json): initial native full
  attribute read matched the App hash, before extended acceptance.
- [numeric-boolean-checkpoint.json](numeric-boolean-checkpoint.json): first
  structured attempt returned numeric 1/0 for complete/truncated; strict tests
  rejected it. The native response now uses actual JSON booleans.
- [stale-session-checkpoint.json](stale-session-checkpoint.json): full chain passed,
  but the final focus assertion reused a session replaced by the daemon and got
  404. The final test re-resolves a current session/element; no product guard or
  acceptance assertion was relaxed.

Prior-head CI (18d975e): PR checks and plugin security passed; Simulator smoke
40153146574 failed when `simctl terminate` of the owned gesture fixture exceeded
30 seconds after passing the preceding gesture cases and first typing case.
This is a harness/setup timeout, not a passing smoke run; no mutation was retried
or timeout assertion relaxed. A fresh candidate CI result is tracked separately.

## Limits

Complete means this API did not cut the returned AX attribute. It does not prove
that an app exposes its entire document or database, nor that arbitrary WebViews,
custom drawing, old iOS or physical devices behave the same. Physical USB/Wi-Fi,
actual host presentation, installed releases and paired reference task trials
remain open. This closes one reproducible native reading gap; it does not prove
the broader competitive goal.
