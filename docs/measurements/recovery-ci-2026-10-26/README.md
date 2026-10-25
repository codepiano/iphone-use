# Recovery in the Simulator CI path, 2026-10-26

The modified Simulator smoke path completes all eleven top-level checks on an
owned iPhone 17 Simulator/iOS 26.2 with Xcode 27.0 on M4. It includes sixteen
existing gesture/input cases, fifteen new selected-recovery observations, and
the following MCP Settings suite. This is scripted Simulator acceptance, not
physical-device, independent-model, release or general superiority evidence.

[Summary](summary.json), [recovery receipts](recovery-result.json.gz),
[gesture receipts](gesture-result.json.gz), [logs](logs.json.gz), and
[independent cleanup](cleanup-audit.json) retain the run. The managed record was
removed, the owned Simulator is independently absent, and fixture cleanup
reports no errors. The phone was not used.

The first attempt stopped before the new recovery check: the old scroll/tap
fixture selected row 8 but observed no scroll. [Its failed record](scroll-failure.json)
is retained. The fixture now publishes its actual UIKit window/table geometry.
The controlled run reports a table at `[0,246,402,542]` in a 402×874 window: the
old viewport-middle anchor `.65` produces a down point near y=793, outside the
table's y=788 bottom. The new planner chooses a down point inside the table,
preserving `dy=300` and its 450-point viewport travel. All three scroll/tap cases
then report real offsets above 20; the first is 440. The scroll and exact-row
postconditions were not removed, and the product gesture implementation was
not changed to make this pass.

The new recovery judge requires independent hashes, process/trial identity,
actual fault markers, touch/edit counts and refusal semantics. It rejects the
retained real overlapping-button misclick, missing text despite a completion
ACK, changed unselected fields and untriggered faults. The late-focus record
remains a known limitation with incomplete requested text; it is not counted
as a successful text task. A future safer segment can improve that observation
without the test requiring the current 180-character spill forever.

After execution, the final judge additionally rejects a success classification
when B changed even if A appears complete. Actions/setup are unchanged; all
fifteen captured records were re-adjudicated with this stronger verdict. The
summary retains distinct executed/final harness hashes rather than calling the
two files identical. Five focused recovery-verdict tests and sixteen gesture-
verdict tests pass offline.

CI triggers cover the relevant server/MCP/native sources, fixture and helpers.
The new result/traceback/MCP log paths are preserved as artifacts. The standalone
script requires explicit loopback base URL, Simulator UUID, owner, managed
record and candidate MCP binary; it creates no model sessions, reconnects or
device selection. The full competitive goal and current input-time focus risk
remain open.
