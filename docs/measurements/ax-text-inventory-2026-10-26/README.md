# Readonly native AX text interface inventory, 2026-10-26

On an owned iPhone 17 Simulator/iOS 26.2 with the Xcode 27.0 native Runner,
Objective-C runtime metadata reports `AXElement` and its `insertText:`,
`insertText:asUndoableAction:`, `textOperations`, selection and element-reference
methods. `XCAccessibilityElement.AXUIElement` and
`AXElement.elementWithAXUIElement:` expose compatible AX-reference encodings.
The queried AX C action/parameterized-attribute symbols are loaded too.

This is a useful next probe after direct Value assignment bypassed App vetoes,
not a usable replacement implementation. **No insertion, deletion, selection or
other text action was invoked.** Method availability does not prove dispatch
entitlement, selected-field targeting, delegate validation, Unicode correctness,
completion, focus isolation or performance. In particular, helpers named
`elementForTextInsertionAndDeletion` may redirect to another element; their
semantics still need independent App receipts and fault/veto tests.

[Inventory](inventory.json.gz) retains selector/type encodings for four selected
classes and six explicitly queried symbols. A name filter and 256-method bound
were used; this is not an exhaustive private-API inventory. The
[temporary metadata-only route](metadata-probe.patch.gz) and
[executed reader](executed-read.py.gz) are audit records, not product routes or
installers. The owned Simulator and managed record are independently absent,
owned service PIDs stopped, controller exit zero and original native sources
restored with matching hashes in [cleanup](cleanup.json). No physical phone or
model session ran. Ordinary runtime introspection supplied this evidence; REA
provided no native decompilation.
