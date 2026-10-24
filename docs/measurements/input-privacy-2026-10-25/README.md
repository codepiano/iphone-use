# Input privacy generations

Four new HTTP regression functions failed on the previous candidate: saved
continuation remained usable after private on/off; long input continued after
the current chunk; queued short input still ran; and a private change during
session setup did not stop its following text request. The complete synthetic
failure run is retained in `reproduction-before.txt`. No personal phone was used.

## Contract

The request captures privacy generation before validation and owner incarnation
from the authenticated lease, before preparation and the runner lock. A separate
regression reproduced queued input running after owner A-to-B-to-A; restored
names now neither authorize that old request nor renew a new incarnation. Text preflight, session discovery, target binding, clear and each
later chunk recheck that generation and active privacy. An already dispatched
native chunk/atomic request may finish; its authoritative acknowledgement is
preserved. No per-character immediate-stop claim is made.

A private hold invalidates a pending continuation across explicit unhide and
natural expiry, even for the same owner/session/field. Resuming cannot rebind to
current focus or send a native request. An interrupted request issues no new
continuation. Ordinary non-private holds remain compatible.

A confirmed clear followed by a privacy stop reports partial, zero confirmed
characters and `detail.clear_applied:true`; the batch remains partially_applied
and retry_safe:false. It never claims the whole operation was unsent. An input
refused before clear/text remains not_sent. Confirmed chunks and uncertain
native failures retain their separate counts.

Current short input keeps its single native atomic request, with no extra
native round trip for a cached session. Compatible short input retains its old
failure/deadline behavior and now checks between active-field lookup, clear and
keys. A refused/failed clear never falls through to typing.

## Checks

Server library: 886 passed, 1 ignored. Related HTTP entry tests: 51 passed
(20 action outcomes, 4 schema, 1 guarded text, 16 continuation, 6 capture privacy,
4 short text). The extended queued-owner test also passes separately for short
and long input without changing the restored incarnation's lease timestamp.
MCP library: 233 passed, 1 ignored; actual stdio: 24 passed. Exact CI Clippy
1.96.0 `--workspace --locked -- -D warnings` and candidate binary builds pass.
`software-checks.json` retains complete log hashes, summaries and failed checkpoints.
HTTP cases include private start/on-off/expiry, queued short text, delayed session
and binding, confirmed clear, legacy active-field lookup, in-flight continuation,
unchanged non-private hold and no later batch step. A queued A-to-B-to-A test covers both short and long
text and checks the restored owner lease timestamp stays unchanged. MCP tests verify that the
confirmed-clear privacy stop stays partial and unsafe to replay in full/slim/off.

The Simulator fixture writes a synthetic count-only marker on its first editing
callback. The privacy hold begins only after that event, distinguishing actual
text delivery from a still-running read-only binding request. No phone content
or credential is stored in the marker, and its disposable Simulator is deleted.

## Actual runner integration

`simulator-attempt-1.json` records 27 passed cases at checkpoint `ef7d5b3` on a disposable iPhone 17 /
iOS 27 Simulator using the actual daemon, XCTest runner and stdio MCP binaries.
All prior 25 cases remain passing. The two added cases verify:

- A private hold blocks new text, invalidates the pre-hold token and causes no
  extra native keyboard request, with independent field readback unchanged.
- After the fixture actually receives its first character (marker count 1), a
  private on/off transition stops further chunks. Exactly one native keyboard
  request completes, 200 characters are acknowledged, none uncertain, no token
  is issued and independent AX readback is exactly those 200 characters.

Listed source and executable hashes match. Cleanup completed without errors and
Simulator deletion was independently checked. This is Simulator integration,
not a physical-device stop-latency or per-character isolation result.

## Expired deadline normalization

Further positive checks found two over-revocations: clearing an already expired
private deadline invalidated continuation started after expiry, and it dropped
newer video subscribers. The follow-up normalizes inactive deadlines without a
new privacy generation, preserving fresh work and caches. Pre-private work stays
revoked. Subscriptions admitted while still private are counted separately and
cannot gain capture authority through later expiry. Failed/passing checks and
the final combined run are retained separately below.

The normalized source passes server library 888/1 ignored and 172 related HTTP
checks (107 auth/HTTP, 20 batch outcomes, 4 schema, 1 guarded text, 17 continuation,
6 capture privacy, 4 recovery, 1 overlay, 8 sized screenshot, 4 short input).
All 22 video unit checks also pass with deterministic expiry setup; actual timed
expiry is covered independently through HTTP and the Simulator. Exact Clippy
1.96 workspace checks and rebuilt candidate binaries pass. MCP code is unchanged
from the preceding 233/1 ignored library and 24 stdio checks.

`simulator-attempt-2.json` passes all 28 cases with the normalized source. It
retains the 27 previous checks and adds real timed private expiry followed by
new input, an ordinary hold and continuation to an independently read-back 500
characters. Listed source/binary hashes match; cleanup and Simulator deletion
were verified. The first run stays immutable at `ef7d5b3`.

## Remaining acceptance

This increment covers public agent text, not every mutation/read path. Separate
editing keys/set_value, other agent actions, mutation/batch observation payloads,
vault operations and other metadata still need audit. Physical devices, old iOS,
real host UI behavior and paired same-device task/latency trials remain open.
The overall comparative goal is not complete.
