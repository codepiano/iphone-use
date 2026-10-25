# Paired product benchmark preparation

The existing driver only selected our binary/server namespace. The reference's
[pinned MCP config](https://github.com/zhongerxin/iPhone-use/blob/3ce9c080534e89fab91a237bf1c53a4a7e9d80a7/.mcp.json)
uses Python arguments/cwd and the `iphone_use` namespace. Reference HEAD remains
`3ce9c080534e89fab91a237bf1c53a4a7e9d80a7` at this checkpoint.

The driver now accepts one explicit stdio server, restricts tools to its actual
namespace and records task/prompt hashes, CLI model identity and operator trial
conditions. Unique private artifact directories and a mode-0600 config copy
prevent same-second overwrite and public configuration exposure. Results do not
embed MCP command/args/env. Offline receipt attachment restores original timing,
namespace and process status only for the exact task/trace, rejecting drift and
conflicting metadata.

The comparison helper rejects mixed devices, OS, transport, app/data/initial
state, model/task versions, changed product revisions and reused traces. It
requires balanced opposite-order pairs and independent receipt state. Orphans,
failed audits and unknown postconditions stay in denominators; absent wall time
is never zero. All-attempt timing is separate from verified-success timing.
Consistency readiness is not a product-superiority verdict, metadata assertions
are not hardware evidence, and CLI turn/cost counters are not network-request or
billing measurements.

`software-checks.json` retains source hashes and exact output of the existing
benchmark regression and the new paired regression, plus Python compilation.
The new check runs the real driver subprocess path with an owned fake `claude`
executable, then exercises replay and comparison using synthetic traces and
metadata. It never invokes an installed agent, starts an MCP server, uses a
phone or spends model tokens. Both scripts are added to PR CI. Their synthetic
100/200 timing fixtures must not be quoted as product performance.

`environment.json` retains only redacted availability facts: no connected Chrome
relay/browser, the configured phone service refusing connection, four remembered
device tunnels disconnected and three iPhone USB metadata probes returning
not-attached (exit 3). No runner was reconnected, phone screen read or input
sent. Raw device records and identifiers are not committed. A question about
preparing a test phone/browser was sent while independent tooling work continued.

The previous native-video candidate `2de3657` passed all GitHub checks:
PR checks 40144773845, security 40144773855 and Simulator smoke 40144773860.
Those checks apply to that commit; this benchmark-only change needs its own CI.

No actual paired product task trial, physical acceptance or real-host rendering
was performed here. The complete objective and remaining requirements stay in
`docs/development/competitive-acceptance.md`.
