# Agent benchmark

Runs real tasks with `claude -p` against the installed `iphone-use-mcp` and
audits each run: execution checks, independent verification, tool calls by name
and in order, failed calls,
turns, time, tokens and cost. Use it to check that the tool descriptions lead a
model down the short path. Run it after you change a tool description, the
skill, or an output format, and compare the results with an earlier run.

It drives a real iPhone and spends model tokens, so it is a manual check and
does not run in CI.

A final answer, matching regex or successful API acknowledgement does not verify
the task. Runs without an independent postcondition check report `UNVERIFIED`.
Metrics remain available for those runs; they are not successful-task results.

```bash
scripts/agent-bench/run.py                                   # every task in tasks/
scripts/agent-bench/run.py --task settings-ios-version --model claude-sonnet-5-5
scripts/agent-bench/run.py --from-jsonl scripts/agent-bench/out/<run>/<task>.jsonl
```

- Claude gets only the iphone-use MCP server (`--strict-mcp-config`), and only
  `mcp__iphone-use__*` tools are allowed.
- Built-in tools are removed with `--tools ""`; skills, hooks, Chrome integration
  and session persistence are disabled for the requested benchmark profile.
  `--allowedTools` alone only pre-approves calls, as described in the
  [official CLI reference](https://code.claude.com/docs/en/cli-reference).
  The current prepared profile uses CLI 2.1.310's `--restricted` flag. Normal
  authentication remains available. This requested profile is not a capture of
  the entire effective vendor/global system prompt.
- All MCP schemas load upfront, with tool search disabled for both products.
  These runs measure the provided tool interface rather than default client
  discovery, skills or installed product-host rendering.
- `--timeout` defaults to 180 seconds and `--max-turns` to 12. A timeout stops
  the owned CLI process group and skips remaining selected tasks. A complete
  final message cannot turn a timed-out execution into a pass during replay.
- Task text goes over stdin, rather than into the process argument list.
- `--mcp <path>` (or `IPHONE_USE_MCP`) picks another build.
- Artifacts go to `out/<timestamp>/` (git-ignored): the stream JSONL per task
  and `results.json`.
- Offline replay applies the same task header as a live run. It infers the task
  from the trace filename, or accepts one explicit `--task NAME`. An unmatched
  trace cannot silently bypass the task rules.

A task is a Markdown prompt with an optional header:

```markdown
---
name: settings-ios-version
expect: "\d+\.\d+"   # answer format only; not proof of the actual version
max_tool_calls: 8    # call budget; not proof of task completion
---
Open Settings on my iPhone and tell me which iOS version it runs.
```

Keep tasks read-only or reversible. They run on a real phone.

After a separate harness or a person checks the task's postconditions, save a
receipt outside the model trace:

```json
{
  "task": "settings-ios-version",
  "trace_sha256": "<SHA-256 of settings-ios-version.jsonl>",
  "verified": true,
  "verifier": "independent-device-assertions",
  "evidence": "/path/to/postcondition-results.json"
}
```

The receipt records an independent check; this driver does not perform that
check itself. The check must cover both the requested answer and the on-device
postconditions. Do not generate it from the agent's answer or a tool's `ok:true`.
The exact task and trace digest must match. A failed check uses `verified:false`.

```bash
scripts/agent-bench/run.py --from-jsonl out/run/settings-ios-version.jsonl \
  --task settings-ios-version --returncode 0 --verification verification.json
```

Use the original process exit code, recorded as `process_returncode` in the live
run's `results.json`. If it is unknown for an old trace, omit `--returncode` and
keep the result unverified. Do not invent a zero exit code to obtain a pass.

Result schema 2 separates `checks_passed` from `verification`. `passed` is `null`
when verification or the original exit status is missing. Exit codes are 0 for
verified passes, 1 for failed checks or postconditions, 2 for invalid arguments
or receipts, and 3 for unverified results. Compare runs with the same model,
device, task, initial state and verification procedure.

## Paired products

The reference project uses the `iphone_use` MCP namespace and a Python command
with arguments/cwd; see its [pinned config](https://github.com/zhongerxin/iPhone-use/blob/3ce9c080534e89fab91a237bf1c53a4a7e9d80a7/.mcp.json).
`--mcp-config FILE` accepts exactly one local stdio server, preserving its args,
cwd and env. Use absolute paths in an ordinary CLI config, rather than the
plugin-only `${PLUGIN_ROOT}` placeholder. Only that server's tool namespace is
allowed. A trace calling outside tools fails its execution audit.

A reference config has this shape (no installation or phone connection is
performed by this example):

```json
{"mcpServers":{"iphone_use":{"command":"python3",
 "args":["/absolute/reference/server/iphone_use.py"],
 "cwd":"/absolute/reference"}}}
```

Each live trial records its label, exact task/prompt hashes, requested model and
model identity observed in the CLI init event. `--context FILE` adds operator
metadata. Metadata is an assertion to audit, not evidence that a device/build was
actually used. Do not put credentials or private account data in context files.
Use an opaque lab device id instead of publishing its UDID. For example:

```json
{
  "pair_id":"settings-01", "position":1,
  "device":"lab-phone-1", "ios":"27.0", "transport":"usb",
  "app_versions":{"com.apple.Preferences":"fixture-version"},
  "initial_state":"home-fixture-v1", "dataset":"synthetic-v1",
  "product_revision":"repository@commit-and-build-hash"
}
```

For the counterpart, retain the same conditions and pair id; use position 2 and
its own product revision. Repeat a second pair in the opposite order, resetting
and independently checking the same initial state each time. Run the products
separately. Source/runner/build identity, transport and initial-state evidence
must be collected outside the model trace too.

```bash
scripts/agent-bench/run.py --task settings-ios-version --model EXACT_MODEL_ID \
  --mcp /absolute/candidate/iphone-use-mcp --label candidate --context candidate-context.json
scripts/agent-bench/run.py --task settings-ios-version --model EXACT_MODEL_ID \
  --mcp-config reference-config.json --label reference --context reference-context.json
```

Artifact directories use unique private names (mode 0700), including runs started
in the same second. Their `mcp.json` copy is mode 0600 and is never embedded in
results; it may contain credentials. Raw traces can include screen content.
Neither raw artifacts nor configurations belong in public benchmark reports.

After an independent check produces the trace-bound receipt described above,
re-audit with `--run-results` to restore the **original** wall time, namespace,
exit status and trial conditions. It rejects trace/task drift, ambiguous matches
and conflicting exit codes. It does not rerun the task or invent missing timing.

```bash
scripts/agent-bench/run.py --from-jsonl out/RUN/settings-ios-version.jsonl \
  --run-results out/RUN/results.json --verification receipt.json --json > verified.json
# An older external trace can instead name its namespace explicitly:
scripts/agent-bench/run.py --from-jsonl reference/settings-ios-version.jsonl \
  --server-name iphone_use --returncode 0 --verification reference-receipt.json --json
```

`compare.py` combines re-audited result lists. Supply both products from at least
two opposite-order pairs for every task. Missing counterparts remain in attempt
denominators. Missing receipts or wall time leave `paired_data_ready:false`
(exit 3); they never become zero-duration passes. Mixed devices, OS, transports,
apps/data/initial states, models, task hashes or revisions within a label/stratum,
reused traces, and mismatched receipts are rejected (exit 2).

```bash
python3 scripts/agent-bench/compare.py candidate-01-verified.json reference-01-verified.json \
  candidate-02-verified.json reference-02-verified.json
```

The report retains failed/unverified attempts and shows all-attempt wall-time
medians separately from verified-success medians. CLI `num_turns` is reported as
`reported_turns`; it is not an independent count of model network requests.
Reported token/cost counters do not establish actual subscription billing.
`paired_data_ready:true` means the supplied trial records pass consistency gates,
not that either product wins or that the broader competitive goal is achieved.
These helpers do not perform independent postcondition checks themselves.

## Prepared owned-Simulator pilot

[controlled-pilot.md](controlled-pilot.md) defines three immutable task prompts,
two opposite-order pairs per task, tool profiles and independent App checks.
It requires explicit authorization before starting independent model sessions.
Preparation and the fixture transport smoke tests do not invoke a model.

Use `--fixture-only --task-dir pilot-tasks --task NAME` and a private `--out-root` outside the
repository to keep its project instructions out of the working-directory path.
User/global or managed context can still exist; the recorded benchmark prompt
hash identifies only the supplied neutral prompt. Context files may include
`deny_tools`, an exact list of fully qualified names in the selected MCP
namespace; the driver rejects other names. The requested runtime profile must
match across a paired comparison.
The fixture-only navigation/lifecycle constraint is opt-in; ordinary Settings,
Home-screen and Notes tasks keep their normal task-scoped phone navigation.
