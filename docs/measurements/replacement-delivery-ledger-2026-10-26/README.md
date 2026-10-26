# Replacement delivery receipts, 2026-10-26

Received replacement delivery errors now retain acknowledged Unicode scalar
counts, the uncertain current segment, the never-sent suffix and the clear
receipt. A successful prefix followed by a refusal does not erase the prefix or
authorize repeating the whole replacement. Native combined replacement and the
legacy clear/type path both retain their earlier effects. `/control`,
`/agent/input`, `/agent/actions` and MCP carry the same non-retryable receipt;
batches stop before their successor actions.

Existing request-level admission already protected agent actions from whole
replacement replay. This change adds character-level detail, preserves its native
request counters and keeps unknown current requests unknown. For example, the
integration fixture's 501-scalar value splits before a family emoji: 199 scalars
are acknowledged, a failed next segment has up to 200 uncertain scalars and 102
remain unsent. A before-dispatch refusal of that segment instead leaves 302
unsent. Counts describe Runner request acknowledgements, not independent App
postconditions. Ownership/privacy revocation keeps its existing scope receipt;
no replacement continuation token or automatic append advice is introduced.

HTTP 200 W3C error envelopes now retain a bounded typed reason and their existing
human-readable message format. They never become successful writes or a 400
no-input refusal. Malformed prefix acknowledgements confirm neither that prefix
nor its clear. Browser adapter regression covers an actual delivered-prefix
failure falling through to `unsupported_control`; the final adapter returns the
receipt instead.

[Validation records](validation.json) retain passing and failed checkpoints:

- The server core library passes 902 tests, with one ignored. A broad server run
  reaches the final wait integration binary with one timing failure. The same
  3000ms slow-probe test passes alone in 2.68 seconds; the full 16-case wait
  integration subsequently passes without changing its deadlines or assertions.
- The final replacement integration passes 11 tests, including native/legacy
  single and batch failures, HTTP 200 error envelopes, 400 refusals, HTTP 500,
  disconnects, original reason preservation, Unicode counts and browser control.
  Its existing unknown/native-counter assertions remain unchanged.
- MCP passes 304 tests, with one ignored. Its compact failed-batch output retains
  replacement counts/clear status and does not suggest ordinary append recovery.
- Thirteen recovery-gate checks pass. A same-owner, nonprivate, unlocked owned
  Simulator in `read_failing` waits only on status within the existing 15-second
  setup budget. No screen read, reset, input or reconnect is sent while waiting;
  strict `drivable:true` admission resumes before the next action. Owner, privacy,
  target, lock, handoff, release and malformed-state changes still stop.

The [public MCP pilot](public-cohorts.json.gz) uses an isolated target-bound
character Runner, **outside the product Native sources**. Two remote ordinary
501-character records and three local records have independently verified App
hashes; the latter are seeded/empty 501-character inputs and Unicode input.
[Hash audit](app-hash-audit.json) checks unrelated fields too. These five records
include repeated tasks across two lanes; they are not five independent benchmark
scenarios or a passed adversarial cohort.

All four pilot cohorts remain incomplete. The remote lane stops on an unstable
Unicode receipt. The first local lane receives the character-20 failure response,
then its old strict health gate aborts before saving App readback; it receives no
A20/B0 credit. A later reset fails before task input, and its App setup receipt
was not retained. The following public-launch setup retains an unknown response:
the client times out at roughly 20 seconds while the Native route reports HTTP
200 at roughly 20.98 seconds. Its late body and independent launch postcondition
were not captured. [Cold-launch record](cold-launch.json) is not a successful
launch or a completed input task. The final controller now retains setup
observations, but that failing launch never reaches its warmup/task loop.

The revised gate has offline coverage; a complete public character cohort with
that gate still needs runtime acceptance. App/session switches, existing long
field content, reached vetoes, continuation and physical public-path stability
remain open. No default Native keyboard change, comparative speed/model-turn
win, physical-device test, merge or release is claimed by this pilot.

[Cleanup](cleanup.json) independently confirms three local and two remote owned
Simulators and service processes are absent; local test ports are closed. Product
Native source hashes match the branch. [Source/runtime identities](source-binary-identities.json)
retain 172 Rust/build-file hashes and the actual controller-recorded binary
hashes. Those `target/debug` products were absent during the later audit; this
record does not establish an installed or downloaded release artifact.
[Experimental patches/controllers](private-prototype-sources.tar.gz) exclude
credentials, signing profiles, signed products and SDK binaries. The installed iOS27.1 runtime
did not advertise iPhone 17 support locally, so the pilot explicitly verified
the available iPhone 17 / iOS27.2 pair and used Xcode27.2 beta2. Its successful
records are Simulator evidence, not physical iPhone acceptance.
