# Target-bound AX character probes, 2026-10-26

The per-grapheme prototype reaches the same character-20 focus fault on both an
owned Simulator and the physical iPhone 17 Pro Max/iOS 27.2 with **A20/B0**.
Every next grapheme requires the retained original, current focus, enabled/type/
identifier/visibility, foreground App and unchanged binding before and after
input. App vetoes reached on the requested focused TextField/TextView preserve
values and stop after one refused input. Unicode, caret and multiline samples
retain independent App hashes/callback counts. This is promising safety evidence,
not a shipped backend or a general per-character immediate-stop guarantee.

**Physical 501-character requests do not complete in the unchanged ten-second
experimental budget.** The first RPC character cohort writes 206, 198 and 195
characters in its three long cases. A profiled cohort writes 251 and 194. Removing
only the duplicate foreground query inside each check, while retaining checks
before/after every character, improves the two measured long cases to 322 and
281, still incomplete. All stop unknown/non-retryable. Simulator long cases
complete exactly (roughly 6.4–6.6 native seconds initially and 4.7–4.9 in two
optimized samples); these uncontrolled native-route timings are not public MCP,
reference, model or physical speed wins. The experimental 501-in-one-request
budget also differs from the existing public 200-character chunk pipeline.

A 64-character hardware profile takes about 1.87 native seconds: ActiveApps
720ms, view-service checks 122ms, insertion 325ms, with the remainder mainly
field snapshot/validation work. Direct local snapshot/attribute queries fail
with kAXErrorServerNotFound; a separate SpringBoard/FrontBoard readonly query
returns zero valid foreground results. Neither shortcut is adopted. No identity,
focus, enabled, visibility, App or binding condition is dropped to make a timing
pass. Existing production typing and its A20/B180 limitation remain unchanged.

The earlier stages are retained too:

- AXElement.insertText honors a focused field's veto, but redirects an unfocused
  B/TextView request into focused A. Pointer identity alone does not bind dispatch.
- Intercepted SDK calls identify action 2056 and the actual target. Calibration
  forwards no actions and has unchanged App fields and zero edit events; its fake
  acknowledgement is not a completed input task.
- Sending that action to the original UI element fixes the redirect, but an
  unfocused field can be changed without its delegate. In the unfocused TextView
  veto sample all 501 characters land with zero requested-field callbacks. Bulk
  bound dispatch is therefore rejected for default input.
- The guarded character version instead sends the action through the existing
  XCAXClient.performAction route, retaining the original XCAccessibilityElement.
  The requested TextField/TextView veto controls actually run and stop. An
  unfocused precondition refusal is not credited as an exercised veto.

[Simulator cohorts](simulator-results.json.gz), [physical cohorts](physical-results.json.gz)
and [independent audit](audit.json) preserve failures, unknowns and independent
App state. API ACK counts and experiment_complete are not substitutes for final
App hashes. Retained physical startup trials execute zero input when the fixture
is not confirmed foreground. A CoreDevice installation reports a placeholder
launch identifier; passing it as Base64 fails, so the later harness validates
that optional identity and otherwise uses normal bundle launch. The user
reconfirmed the phone was unlocked/available before the successful later cohort.

[Prototype sources/controllers](prototype-sources.tar.gz) are audit records tied
to owned fixture identities, not product routes/installers. Raw SDK metadata,
method interception and ordinary LLVM inspection supplied the action/ABI facts;
REA supplied no native decompilation. The observed action constant is not a
negotiated cross-version product capability. Direct read/foreground failures
remain failures; no system restriction or App validation is disabled.

Device products use Xcode27.0 compilation, local development signing and
Xcode27.2 beta2 execution; [binary identities](build-identities.json) exclude
profiles, credentials and device identifiers. All six owned Simulators and
service PIDs are independently absent. Every physical cohort's owned apps are
absent and pre-existing apps preserved; final test ports are closed and the
original default service stays offline/unowned. Native sources on the M4 are
restored to the branch hashes in [cleanup](cleanup.json). No independent model,
personal-app input, merge, release or downloaded-artifact acceptance ran.
