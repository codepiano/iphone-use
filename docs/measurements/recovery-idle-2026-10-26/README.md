# Recovery harness waits for proven native idle, 2026-10-26

[Hosted run 40225138468](https://github.com/leeguooooo/iphone-use/actions/runs/40225138468)
at branch head 05a26fb passed all 16 original gesture/input cases. On its iOS 18.2
Simulator the moved pre-launch container query completed in 4.23 seconds and App
launch returned in 2.98 seconds. The recovery lane then aborted at the first
idle check before any case/reset/input. Its raw result preserves zero cases and
a subsequent 120-second fixture-uninstall timeout. The old check rejected any
busy/non-false status immediately; it retained neither the status payload nor
the active native operation, so the exact cause is unproven.

The Runner marks all main-thread requests busy, including metadata/health reads.
The harness now polls only owned, nonprivate status for at most a 15-second setup
budget, requires an explicit boolean busy:false and then permits the distinct
fixture setup. An outstanding MCP reply aborts immediately. Permanent busy,
missing/nonboolean state, ownership or privacy change still abort; no input or
clear is replayed. The initial installation lookup is bounded too. Per-case
start/verdict and busy-wait phases are printed for subsequent hosted diagnosis.
All 15 original state/hash/fault assertions remain unchanged.

`python3 scripts/test-replacement-recovery-verdict.py` passes ten tests: the five
existing receipt/misclick controls plus settling startup, permanent busy budget,
pending MCP, malformed idle state and owner/privacy changes. A fresh owned M4
Simulator/iOS 26.2/Xcode 27.0 run of the exact recorded script passes all 15
observation contracts with no harness/cleanup error. These include expected
stops and A20/B180, not 15 completed replacements. This normal different-runtime
run is not proof that the hosted startup problem is solved.

[Hosted result](hosted-result.json.gz), [traceback](hosted-traceback.txt.gz),
[failed-step stdout](hosted-failed.log.gz), [M4 result](m4-result.json.gz) and
[run stdout](m4-run.log.gz) preserve both outcomes. The M4 owned Simulator,
controller/Runner/daemon PIDs and managed record are independently absent;
[cleanup](cleanup.json) records zero exit and the exact executed script hash.
The remote checkout still reports an older git HEAD plus verified development
overlays; its raw source_commit is not the complete candidate identity. No
physical phone, model task, release or comparative speed acceptance ran.
