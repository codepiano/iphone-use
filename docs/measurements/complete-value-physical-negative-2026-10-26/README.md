# Physical negative input boundaries, 2026-10-26

Four public stdio MCP `phone_type(clear:false)` requests on the isolated private
character Runner exercise **expected stops** on the authorized iPhone 17 Pro Max,
iOS 27.2. These are four reached negative scenarios, not four completed typing
tasks. The App's independent receipts show:

| Reached App event | Independent resulting value |
| --- | --- |
| Focus moved after character 20 | A20 / B0 |
| Focus moved after character 221 | A221 / B0 |
| App delegate vetoed insertion | Original A hash preserved, B0; veto counter reached |
| App delegate moved focus to B | Original A hash preserved, B0; handoff counter reached |

All four public operations return `ok:false`, `text_partially_typed`, a partial
delivery receipt and `retry_safe:false`. No failed operation is replayed. Other
fixture fields remain unchanged, Return/submit events are zero, and independent
stable readback follows each completed response. [Sanitized evidence](summary.json)
retains public counts and App hashes/callback markers without field text.

The first attempted focus trial omitted the fixture's required sentinel prefix,
so the App never triggered the fault and ordinary input completed in A. The
harness rejected that trial; it is retained as an excluded setup diagnostic and
is not a product negative result or acceptance success. The corrected cohort
includes the required prefix and explicit 20/221 thresholds; both markers were
independently observed.

Independent cleanup confirms both owned apps absent, all 21 preexisting apps
preserved, relay/daemon ports closed, no pending input and the default service
still offline, unowned and without a private hold or human handoff. The signed
private Native hash matches the preceding [two positive physical
cases](../complete-value-physical-2026-10-26/README.md).

This makes six planned physical observations: two completed appends and four
expected stops. It does not establish the entire 17-observation Simulator cohort
on hardware, physical selected replacement/multiline/clear faults, old iOS
compatibility, comparative speed or the product default path. The private Native
implementation remains outside the released default implementation.
