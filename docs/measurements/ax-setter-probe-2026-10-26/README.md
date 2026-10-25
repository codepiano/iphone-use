# Rejected direct AX Value assignment, 2026-10-26

Direct `XCAXClient_iOS setAttribute:value:element:outError:` can address the
retained original AX element without routing text through keyboard focus. The
owned iPhone 17 Simulator/iOS 26.2 experiment completes Unicode, 501-character
focused/unfocused replacements and a multiline assignment with exact App hashes.
TextField receives one editingChanged event and one textDidChange notification.
This is promising for target addressing but is **not suitable for default input**.

The second cohort equips the App with real UITextField/UITextView delegates,
text-change notification observers and a policy that rejects every edit. AX Value
assignment still replaces both rejecting fields with 501 characters: neither
shouldChange callback runs. Ordinary native typing controls invoke each delegate
five times, receive five refusals and preserve the original values. TextView AX
assignment changes its text without textViewDidChange or textDidChange notifications.
A correct value hash and a successful API acknowledgement do not establish that
the App accepted normal editing semantics. No experimental route is shipped.

The focus-shift diagnostic commits all 500 characters before its editingChanged
handler moves focus; its trigger is 500, not 20. It does not pass the existing
character-20 in-flight fault or resolve the current native A20/B180 limitation.
Native route elapsed times are uncontrolled single-cohort diagnostics, not an
end-to-end MCP, model or comparative speed result. No physical phone was used.

[Initial receipts](initial-result.json.gz), [delegate/veto receipts](delegate-result.json.gz),
[summary](summary.json), [rejected prototype](rejected-prototype.patch.gz) and
[executed harness](executed-harness.tar.gz) preserve the actual experiment. The
harness is an audit record tied to an owned disposable instance, not an installer.
The first two setup attempts failed before input (import/readiness); both were
cleaned up. Two subsequent cohorts completed. All four owned Simulators were
independently absent afterward; managed services stopped, instance record absent,
and the three experimental native source files restored to the branch hashes in
[cleanup](cleanup.json). Compiled experiment products remain isolated private
build cache and are not distribution artifacts. No model sessions were started.

Local LLVM inspection found the setter forwarding the element/value to the
remote accessibility interface. Its iPhoneOS Xcode 27.2 beta2 binary differs
from the executed Xcode 27.0 Simulator client; method names alone prove no runtime
semantics. REA still reported pending cleanup and supplied no native decompilation.
No analyzer configuration, framework bytes or global Xcode selection changed.
