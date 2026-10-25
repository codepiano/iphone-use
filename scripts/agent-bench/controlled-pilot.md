# Controlled MCP model pilot

Prepared only. No model session has been run. Starting the twelve independent
CLI sessions requires the user's explicit authorization under this session's
agent-delegation rule. This is an owned-Simulator MCP ergonomics pilot; it does
not replace physical-device, installed-host, default-skill or release acceptance.

The native core candidate is `c350a26769256a68919d1f8d200ad6c1381c57c5`.
Reference remains `3ce9c080534e89fab91a237bf1c53a4a7e9d80a7` with unmodified WDA
`d17782422d55ff1e5e0ceb74eb1fd509cc0c35b6`. Record actual daemon/MCP/runner and
fixture hashes from the started fixture; a source label alone is insufficient.

| Task | Initial state | Required independent outcome |
| --- | --- | --- |
| `fixture-long-count` | A contains the long synthetic seed; B/multiline empty; secure dummy intact | Correct full UTF-16 length, supported by complete tool content or reliable length metadata; all field hashes unchanged |
| `fixture-first-draft` | A is `old`; other fields at their fixture defaults | Exact immutable 500-character task value in A, other field hashes unchanged, correct completion answer |
| `fixture-second-draft` | Same short initial state, A focused | Exact immutable 128-character task value in B, A/multiline/secure unchanged, correct completion answer |

The prompts live in `pilot-tasks/`, separate from normal real-phone tasks. Do not
edit a prompt after observing outcomes and combine the trials with its old hash.
The long-read prompt does not disclose the expected answer. Clipboard, Photos,
other Apps and host commands are outside this pilot's allowed operations.

Use one owned Simulator and one compiled fixture App. Run the backends in
native/reference/reference/native order. Each block runs the same three tasks
in fresh CLI processes, making twelve sessions total. Reset/check the fixture
before every task. The operator owns backend lifecycle; models do not release,
reconnect, install or publish anything. Preserve failures and unknown attempts.

`compare-native-wda-simulator.py --operator-hold --reset-mode file` keeps each
backend sequentially available without launching any model. Each block writes
a private `operator/ready.json` with App/device identity, available tool names,
the stdio wrapper argv, fixture Documents path and the block's `done` sentinel.
The wrapper takes a unique trial id plus a comma-separated tool profile, keeps
credentials in a private file and supervises its child process group. Only
create the block's sentinel after all local CLI clients have exited. A timeout
or uncertain transport delivery aborts the cohort: stop the operator fixture,
retain the incomplete records, and do not reset into another live trial.

For native read-only tasks expose `phone_status`, `phone_elements`,
`phone_read_value`, `phone_screenshot`. Write tasks may additionally expose
`phone_tap_element`, `phone_tap_label`, `phone_type`, `phone_run_steps`. Native
profiles are enforced by the MCP server. For reference allow `pua_ready`,
`pua_observe`, `pua_find`; write tasks may add `pua_tap`, `pua_type_text`,
`pua_batch`, `pua_wait`. Derive an exact CLI `deny_tools` list from all other
names in the reference's ready manifest. No reference source is modified.
This is a task-specific tool surface rather than a default all-tools profile.

Use the currently configured Claude CLI default, record its reported full model
identity in every init trace and reject a mixed-model cohort. The prepared
client is CLI 2.1.310 with MCP-only built-ins-disabled/restricted settings,
upfront schemas, no skills/hooks/session persistence, a neutral benchmark
system prompt, at most twelve turns and a 180-second per-session wall deadline.
Existing model quota is consumed. No global CLI/MCP configuration is changed.

Every trial context must carry `trial_id`, `fixture_pid`, an opaque shared lab
device id, OS/transport, fixture source/binary and CLI versions, initial-state
and dataset ids, pair id/position and the exact per-product build/tool-profile
identity. These are operator assertions. Separately capture the App's
`paired-state.json` and a fresh runner active-App read after the model exits.
Keep only the own fixture; verify the same PID/bundle and settled field state.

`verify-fixture.py` reads the original trace/results and that independent
postcondition file, checks trial/task/trace/device/process binding, then writes
a standard trace-bound receipt. It never invokes a model or phone. Re-audit
with `run.py --run-results ... --verification ...` and compare both opposite
orders with `compare.py`. Keep raw configurations/traces private; publish only
reviewed aggregates and synthetic postcondition evidence. CLI-reported turns,
tokens and costs are not independent network-request or billing measurements.
