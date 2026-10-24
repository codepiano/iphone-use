# Candidate host adapter validation

Reference source was refreshed at `zhongerxin/iPhone-use` commit
`3ce9c080534e89fab91a237bf1c53a4a7e9d80a7`. Its
[WorkBuddy adapter notes](https://github.com/zhongerxin/iPhone-use/blob/3ce9c080534e89fab91a237bf1c53a4a7e9d80a7/workbuddy/README.md)
report app tool-forwarding and process-lifecycle differences;
[Doubao notes](https://github.com/zhongerxin/iPhone-use/blob/3ce9c080534e89fab91a237bf1c53a4a7e9d80a7/doubao/README.md)
report a different tool path. These are reference implementation claims, not
independently verified host behavior here. MCP Apps officially supports
[view-side resource reads](https://github.com/modelcontextprotocol/ext-apps/blob/main/docs/overview.md).

Our candidate reuses the existing daemon and XCTest runner. Explicit
`IPHONE_USE_MCP_HOST=workbuddy` routes panel frames through a read-only resource;
`doubao` keeps frame tools. Both advertise only `phone_screen` as a panel opener,
with distinct host-specific page URIs. WorkBuddy adds its panel surface metadata.
Only bounded frame size and cache nonce are addressable through resources. No
Home, tap, unlock or owner operation is exposed there. Tool allowlists still gate
frame access; a newly started bridge process reads the same daemon without a
worker launch or control request. No additional socket or network source is added.

## Software evidence

- MCP library: 233 passed, 1 ignored. Real stdio: 22 passed.
- Installer client-config tests: 10 passed, in disposable HOME directories only.
  WorkBuddy registration preserves other connectors, backups, instance selection,
  conflicting entries and malformed config; repeat install and opt-out are covered.
- The actual panel JavaScript runs against a simulated host that rejects all
  app tool calls in WorkBuddy mode. Both modes draw a frame, clear a prior image
  for privacy, obey their control paths and stop polling when hidden.
- Independent bridge processes read one scripted daemon using GET status/frame
  only. Invalid resource paths, other host modes and a profile excluding frames
  are refused before contacting it. Private and failed captures yield no pixels.
- A process-local GUI proxy environment reproduced a real loopback connection
  failure before the fix. The fixed client directly connects parsed loopback
  authorities, including IPv6, while remote URLs retain proxy settings. The same
  parsed boundary prevents a remote userinfo URL from borrowing the local token.
  No test mutates the parent process environment or changes the user's proxy.
- Candidate daemon and MCP binaries build successfully. Native runner sources
  are unchanged in this increment. `software-checks.json` preserves local log
  hashes, passing summaries and the failed proxy reproduction summary.

## Actual daemon / runner integration

`simulator-attempt-1.json` records 24 passed cases using the actual candidate
daemon, XCTest runner and MCP binaries on a disposable iPhone 17 / iOS 27
simulator. The previous 23 input/cancellation/recovery cases remain passing.
The added host case starts two separate WorkBuddy-mode MCP processes against
the same daemon: both return a valid PNG through resources/read, the original
owner remains unchanged and no keyboard request is recorded. Source and
binary hashes match; cleanup and simulator deletion were verified.
This is real backend integration, with a protocol client substituting for the
WorkBuddy application. It does not establish WorkBuddy UI acceptance.

## Remaining acceptance

WorkBuddy and Doubao are not installed on this machine. Trust UI, actual panel
rendering/reuse, host restrictions, skill import, full tasks and physical phones
remain unverified. The panel still uses the existing sized PNG polling with a
2 fps ceiling; reference streaming/batch playback and our native video pipeline
are not integrated into these host adapters yet. This is not a latency win or
proof of overall superiority. See [host setup](../../mcp-hosts.md) and the
[full acceptance matrix](../../development/competitive-acceptance.md).
