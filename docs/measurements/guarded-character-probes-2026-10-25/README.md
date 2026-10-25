# Rejected native character-event probes, 2026-10-25

Neither prototype is suitable for the default input path. The original Runner
source was restored locally and on the M4 build host. These experiments narrow
the next implementation choice; they do not resolve the competitive goal.

One physical iPhone 17 Pro Max/iOS 27.2 over the local network ran the same owned
fixture as the [preceding functional comparison](../physical-iphone17-2026-10-25/README.md).
The native candidate was `417aae4` plus each retained experimental patch. Both
prototypes were disabled by default and enabled only in private test launches.
Device bundles used Xcode 27.0, local signing, and Xcode 27.2 beta 2 execution.
Each experiment keeps independent App field hashes/counts. No independent model
task session was started.

| Prototype and request | Observed result | Decision |
| --- | --- | --- |
| Text event per composed character, replace 64 characters | 40 characters, then budget expiry/unknown | Reject incomplete ordinary replacement |
| Same, replace originally empty B with 501 characters | 41 characters, then budget expiry/unknown | Reject incomplete ordinary replacement |
| Same, App changes focus at character 20 | A20/B0, trigger reached, unknown | Useful diagnostic; full requested replacement still fails |
| Key event per composed character, 501-character mixed value | B13, unknown | Reject failed text semantics |
| Same, eight Unicode scalars including Chinese, emoji and combining text | B0, value not applied | Reject failed Unicode task |
| Same, input-time focus probe | A17/B0, trigger **not reached** | Not a passed focus-fault test |

The text-event experiment scopes the SDK's implicit confirmation interval to
zero for each event and restores its previous value afterward. It retains
original-field pre/post checks, never falls back after dispatch, and stops at
a ten-second native prefix budget. Character granularity removes the observed
180-character spill in the reached focus fixture, but its ordinary-input
throughput is unacceptable. It is not a general per-character isolation proof.

The key-event experiment additionally tries targeted `typeKey` events, retaining
checks and a maximum dispatch rate of 60 Unicode scalars/second. The App does not
receive the intended mixed/Unicode values. Its zero spill cannot be credited
when the configured focus fault never triggers. Neither patch is shipped.

An [eight-character text-event profile](header-profiles.json) completes exactly,
with nine synthesis calls including the focus tap: native processing 2,386 ms,
actual synthesis wait 2,064.6 ms, declared event hold 1,810 ms. Declared event
duration is not measured elapsed time. A separate profiled middle-caret case
stops during Select All before text, with unchanged field hashes and zero edit
events; its cause remains unconfirmed. No uncertain operation was replayed.
These small, uncontrolled-load profiles establish no comparative latency win.

[Summary](summary.json), [lossless replies](results.json.gz),
[text-event patch](text-event-prototype.patch.gz),
[key-event patch](key-event-prototype.patch.gz), and
[executed controllers](executed-harness.tar.gz) retain the rejected designs.
The [SDK inspection](sdk-static-inspection.json) uses ordinary LLVM tools on the
Xcode 27.2 beta 2 iPhoneOS arm64 client. Its event-request invalidation method
still logs a no-op. This is not proof about every runtime/cancellation route or
the exact framework loaded by the Xcode 27.0-built Runner. REA did not provide
decompilation: its retained Hopper-document cleanup remained unconfirmed; no
analyzer setup or user application shutdown was performed.

[Cleanup and rollback](cleanup-audit.json) verifies removal of the owned test
apps, presence of the original Runner/remote App, absence of test listeners,
and matching restored source hashes. Launch credentials, profiles and device
identifier inventories are excluded. The harness is an audit record requiring
private local configuration, not an installer. Native Unicode input with
original-field checks and acceptable throughput, clear-time recovery, broader
physical/host/model coverage and release acceptance remain open.
