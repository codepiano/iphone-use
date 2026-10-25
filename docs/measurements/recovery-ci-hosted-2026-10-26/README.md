# Hosted Simulator recovery startup failure, 2026-10-26

[GitHub run 40222158985](https://github.com/leeguooooo/iphone-use/actions/runs/40222158985)
tested branch head `a727d99` through its PR merge commit on macos-14, iOS
17.5 Simulator SDK build/iOS 18.2 iPhone 15. All 16 gesture/input fixture cases
passed, including the three 440-point scrolls. The selected recovery harness
then failed before its first case: `simctl get_app_container` after fixture
launch exceeded 120 seconds. The [traceback](traceback.txt.gz) and
[result](result.json.gz) preserve zero executed recovery cases and no cleanup
errors. This is not evidence that recovery input failed or passed on iOS 18.2.

Commit `2eed167` moves the readonly container lookup before App launch and MCP
startup, bounds it to 30 seconds, and logs both lookup and launch phases. It
keeps every original input assertion, owner/privacy check and no-replay rule.
The prior timeout alone does not establish its root cause or prove the change
fixes it; the hosted rerun must establish that. The separate M4/iOS 26.2 smoke
remains a successful different-runtime run, not a substitute for this failure.
