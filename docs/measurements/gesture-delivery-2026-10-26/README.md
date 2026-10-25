# Gesture delivery without uncertain fallback replay, 2026-10-26

The old native gesture helper attempted public XCUICoordinate input after any
private synthesis error. W3C plain pointer actions could likewise call tapPoint
and attempt another gesture. An error may follow delivered input, so this could
repeat a tap, swipe, hold or alert action.

The candidate chooses coordinate fallback only when synthesis capability is
absent before invoking synthesis. Every error after invocation stops with an
unknown outcome, including an error string resembling a setup failure. A W3C
hold, delayed/moving touch or multiple fingers cannot silently become a tap.
Remaining key input stops when the pointer action throws. This is a native
fallback policy, not a guarantee about every server/host retry or SDK internals.

`bash runner/unit-check.sh` passes 312 checks, including 16 new checks for
successful single execution, effect-before-error without replay, setup-looking
error collisions, public fallback on capability absence, public-path error
without synthesis retry, and incompatible W3C fallback shapes. The fault injection
uses the production pure dispatch helper with effect-counting closures; it does
not simulate an actual phone transport acknowledgement loss.

The separate complete M4 smoke passes 11 top-level checks: 16 UIKit-observed
gesture/input cases, 15 replacement-recovery observation contracts and the
following actual MCP Settings suite. Recovery contracts include expected stops
and the known A20/B180 text-focus limitation; they are not 15 completed tasks.
The new pre-launch container lookup takes about 0.36 seconds and App launch
about 0.45 seconds here. This iOS 26.2 result does not prove the hosted iOS 18.2
startup timeout is fixed. No model sessions or physical-phone operations ran.

[Gesture receipts](gesture-result.json.gz), [recovery receipts](recovery-result.json.gz),
[full smoke stdout](smoke.log.gz), [summary](summary.json) and
[cleanup](cleanup.json) retain the results. All native Swift/ObjC sources and
fixture scripts used on the M4 match the [candidate digests](native-source-sha256.json).
The remote checkout has an older git HEAD plus these verified overlays; its
raw source_commit must not be mistaken for the complete candidate identity.
The owned Simulator was independently absent after completion, daemon/Runner/
controller PIDs absent, managed record removed and controller exit status zero.
This is development validation, not downloaded-release or physical acceptance.
