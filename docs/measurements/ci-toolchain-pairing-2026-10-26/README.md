# Explicit Xcode/Simulator pairs after hosted read timeout, 2026-10-26

[Run 40228278897](https://github.com/leeguooooo/iphone-use/actions/runs/40228278897)
at branch 898d0ec passes all 16 existing gesture/input cases and reaches the
first recovery case after container resolution, App launch and explicit idle.
It then times out in the first actual MCP phone_elements call, before any
replacement text is sent. Pending delivery prevents reset/uninstall. The
[result](hosted-result.json.gz), [traceback](hosted-traceback.txt.gz) and
[selected build/runtime context](hosted-context.txt) retain this failure.

The job selected default Xcode 15.4/Simulator SDK 17.5 but the first precreated
iPhone was an iOS 18.2 runtime. The exact [runner image manifest](https://github.com/actions/runner-images/blob/macos-14-arm64/20260831.0302/images/macos/macos-14-arm64-Readme.md)
lists Xcode 15.4 with iOS 17.5 and Xcode 16.2 with iOS 18.2. This mismatch is a
candidate cause, not an established explanation of the read stall; logs also
contain AX server-not-found fallback observations and slow simulator operations.

The workflow now runs both matching pairs, with fail-fast disabled: 15.4/17.5
and 16.2/18.2. Each verifies its selected SDK, requires its explicit installed
runtime, creates/deletes only its own iPhone 15 Simulator and runs the same full
smoke script. Input assertions and request timeouts are unchanged; iOS 18.2
coverage is retained. No global Xcode selection or installation is changed.
This is a proposed environment correction requiring actual hosted results. The
existing macOS14 image itself is nearing retirement, so a durable host migration
remains separate work; this matrix is not a long-term host support claim.

Separately, [PR-check run 40228278959](https://github.com/leeguooooo/iphone-use/actions/runs/40228278959)
completed successfully at the same branch head. The new actual HTTP/stdio MCP
entry gate passes [default](http-mcp-default-result.json.gz) and
[full](http-mcp-full-result.json.gz) output modes with 42 scenarios each and
complete private-state/process/socket cleanup, using that CI build's binaries.
Those scripted-native transport results do not prove real UIKit, older-runtime
recovery, physical device or model-task completion.
