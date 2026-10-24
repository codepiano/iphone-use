//! Diagnostic recovery never changes the original action's fate or authorizes replay.
use serde_json::Value;

pub fn advice(body: &Value) -> Option<&'static str> {
    if body.get("ok") != Some(&Value::Bool(false)) {
        return None;
    }
    let code = body.get("error")?.as_str()?;
    match code {
        "element_not_found" | "ambiguous_element" | "stale_element_snapshot" | "invalid_element_target" =>
            Some("Inspect the fresh image for the current page, target and overlays; choose a fresh visible target before another action. A missing tree match does not prove absence."),
        "element_occluded" | "element_not_visible" =>
            Some("Inspect the fresh image for an overlay or an off-screen target. Handle a visible overlay or select a suitable scroll region before acting; old coordinates are not proof the target is reachable."),
        "wait_for_timeout" | "postcondition_failed" =>
            Some("Inspect the actual page and result before planning remaining work. A failed expectation does not undo earlier actions; never replay a submission or the whole batch automatically."),
        "no_scroll_progress" | "scroll_no_progress" =>
            Some("Inspect the current list, region, overlays and end marker before deciding whether to scroll again. No progress does not prove an empty or complete list."),
        "outcome_unknown" | "text_partially_typed" => {
            let message=body.pointer("/runner_error/message").or_else(||body.pointer("/detail/runner_error/message"))?.as_str()?;
            message.contains("input target changed").then_some("Input may have reached a different field. Inspect the original and current fields and enter only confirmed missing work; never resend the full input or resume an unknown chunk.")
        }
        _=>None,
    }
}
