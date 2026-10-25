# Matched hosted SDK/runtime lanes completed, 2026-10-26

[Simulator run 40231278110](https://github.com/leeguooooo/iphone-use/actions/runs/40231278110)
at branch head d9c3e67 completes both full lanes: Xcode 15.4/iOS 17.5 and
Xcode 16.2/iOS 18.2. Independent downloaded artifacts confirm 16 gesture/input
cases and 15 recovery observation contracts per lane, with no harness/cleanup
errors. The recovery contracts include expected stops and the existing A20/B180
limit, not 15 complete input tasks.

This verifies the explicitly paired environments. Compared with the retained
Xcode15.4/iOS18.2 failures it supports the pairing correction, without proving
that toolchain mismatch was the sole cause of earlier stalls. Artifact source_commit
is the PR merge checkout; the branch identity above is from the Actions run.
The separate [PR-check run 40231278103](https://github.com/leeguooooo/iphone-use/actions/runs/40231278103)
completed successfully too. No experimental per-character AX backend is included
in this branch head, and this is not physical-device or release acceptance.
