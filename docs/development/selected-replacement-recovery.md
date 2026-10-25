# Selected replacement after an App-driven focus handoff

`phone_set_value` and HTTP `set_value` accept the optional boolean
`recover_focus_after_clear`. It defaults to false. This is a policy for an
explicitly selected original field, not for `phone_type`, implicit current-focus
input or continuation chunks.

When true, the daemon requires both `ipu:elementReplace` and the new
`ipu:replaceFocusRecovery` session capability. Missing support returns
`replacement_focus_recovery_unsupported` before replacement input; it does not
quietly fall back to an older clear/type path. The native capability also checks
that the runtime exposes the targeted-event and hit-test interfaces.

The Runner binds the retained original AX element before the initial focus
wait. A concurrent command/session invalidation cannot be overwritten by
minting a replacement binding afterward. A successful deletion may leave the
original field unfocused because the App advanced to another field. Before any
restoration, the Runner verifies:

- The same retained field, PID, kind and identifier (or original label when
  untagged), foreground process and unexpired binding remain valid.
- The original remains live, enabled and visible. Its full AX value is empty;
  two snapshots and an empty selection also confirm placeholder-backed emptiness.
- A PID-targeted tap hits the exact original AX element after gesture record
  setup. The dispatch callback independently requires a complete foreground AX
  tree, the same original handle, and no unrelated actionable node overlapping
  the touch point. AX point lookup alone proved insufficient in an actual
  overlapping-button fixture. A covered focus point, incomplete tree, unavailable
  hit test or changed target refuses; there is no ordinary gesture fallback.
- At most one restoration tap occurs. Original identity, focus, empty value and
  selection must be verified again afterward, before any text is sent. Content
  the App repopulates during restoration is preserved and stops replacement.

Deletion synthesis/read/selection failures stop. Recovery does not repeat a
delete or a text prefix. An empty replacement can verify the unfocused original
clear without restoring focus. The native response reports
`focusRestoredAfterClear`; its clear receipt headers retain whether a restoration
tap was dispatched. The daemon still checks the original field's final value.

Keep the default policy when focus changes should interrupt the operation. The
opt-in permits restoring the selected field after a verified clear; it cannot
distinguish every cause of a human/App focus change. Ownership/privacy checks
retain their existing request boundaries. A focus change during the current
text segment remains uncertain and stops subsequent segments; the known
200-character in-flight limitation is not resolved by this policy.

Acceptance must cover strict default stopping, complete opt-in replacement,
empty clear without refocus, unsupported old Runners, changed/disabled/hidden/
secure originals, an overlapping actionable control, App repopulation on
refocus, failed selection and mid-text focus change. App-owned hashes, injected
fault markers, touch counts and original-field readback are required; an error
acknowledgement alone is not an expected-refusal pass or task completion proof.
