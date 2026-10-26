# Complete-value input boundaries, 2026-10-26

The isolated character Runner now completes the public stdio MCP/daemon cohort's
**17 observations** on the owned iPhone17/iOS26.2 Simulator: eight completed
tasks/controls and nine exercised expected stops. [Independent audit](independent-audit.json)
checks App hashes, reached fault markers, unrelated fields and Return events.
This does not mean 17 successful replacement tasks or physical-device acceptance.

The earlier long-field failure has a direct readonly explanation. Both fresh
Native snapshots report 512 UTF-16 units and `value_truncated:true`, while the
complete AX value reports 6015 units. Snapshot and full values differ, and the
original field is focused on both sides of the diagnostic. Comparing the two
truncated snapshot strings therefore cannot establish that input was refused.
The original method sends one character and stops despite the App reaching 6016.
[Before/after records](before-after.json.gz) preserve that failure.

The revised private boundary checker uses the ordinary snapshot value only when
its completeness is explicitly reported (`value_truncated:false`). Truncated or
unknown completeness requires the retained original's complete AX value, bounded
at 65536 UTF-16 units. It requires a complete, nontruncated result; empty/placeholder
normalization remains conservative. Two complete identity, type, process, enabled,
visible, focus, foreground and binding checks surround the full read. The last
remote operation before the next dispatch is again its final foreground check.
Failure stops with unknown/non-retryable delivery and no refocus, text replay or
fallback. An unavailable/truncated full value is not progress.

The public 501-character append to the seeded 6015-character field reaches
**6516 scalars with the exact expected App hash**, in about 14.56 seconds for the
whole MCP request. Each native chunk keeps its existing ten-second experimental
budget, and the public request deadlines are unchanged. The extra reads cost
latency; no comparative speed win is claimed. Short complete-snapshot fields keep
the existing observation path.

The same cohort preserves:

- Exact ordinary 501-character, Unicode, multiline, selected replacement and
  clear-time handoff results, with unrelated fields unchanged.
- Reached character-20/221 stops with A20/B0 and A221/B0, including full/default
  MCP batch receipts and no post-failure refocus.
- Reached App delegate vetoes with preserved values.
- Zero Return events after failed batches, and one event in the explicit Return
  positive control. The nonmodifying pause is the completed batch prefix;
  snapshot-bound replacement remains its first modifying action.

[Experimental source patches/controllers](experimental-sources.tar.gz) are
outside the product Native source tree. No new default capability or keyboard
path is shipped. [Cleanup](cleanup.json) independently confirms eight owned
Simulators/services absent and product Native sources unchanged. No physical
phone, model session, real host, merge, release, installed package or downloaded
artifact acceptance ran here.

Before promotion, this path still needs physical public-path latency/completion,
long-field veto/formatting races, supported-version capability negotiation,
App/session/owner/privacy switches, rotations and longer representative runs.
The full comparison/acceptance matrix remains open.
