//! Real HTTP router -> scripted Runner: timing, guards and no replay.
mod support;
use axum::body::Body;
use axum::http::{Request, StatusCode};
use http_body_util::BodyExt;
use serde_json::{json, Value};
use server::http::AppState;
use std::sync::{Arc, Mutex};
use std::time::Duration;
use support::{block, build_state_with_runner, mock_runner};
use tower::ServiceExt;

fn tree(covered: bool) -> String {
    let cover = if covered {
        r#",{"type":"XCUIElementTypeButton","label":"Overlay","rect":{"x":80,"y":180,"width":160,"height":80}}"#
    } else {
        ""
    };
    format!(
        r#"{{"value":{{"type":"XCUIElementTypeApplication","label":"Fixture","rect":{{"x":0,"y":0,"width":430,"height":932}},"children":[{{"type":"XCUIElementTypeButton","label":"Target","isEnabled":true,"rect":{{"x":100,"y":200,"width":120,"height":44}}}}{cover}]}}}}"#
    )
}

async fn request(
    state: &Arc<AppState>,
    method: &str,
    path: &str,
    body: Value,
) -> (StatusCode, Value) {
    let req = Request::builder()
        .method(method)
        .uri(path)
        .header("x-phone-control", "1")
        .header("content-type", "application/json")
        .body(if method == "GET" {
            Body::empty()
        } else {
            Body::from(body.to_string())
        })
        .unwrap();
    let result = server::http::router(state.clone())
        .oneshot(req)
        .await
        .unwrap();
    let status = result.status();
    let bytes = result.into_body().collect().await.unwrap().to_bytes();
    (status, serde_json::from_slice(&bytes).unwrap())
}

fn action(snapshot: &str) -> Value {
    json!({"type":"touch_path","snapshot":snapshot,"element":1,"path":{
        "viewport":{"width":430,"height":932}, "hold_before_ms":20,"hold_after_ms":30,
        "samples":[{"x":140,"y":220,"t_ms":0},{"x":140,"y":220,"t_ms":17},
            {"x":141,"y":220,"t_ms":53},{"x":141,"y":221,"t_ms":100}]}})
}

#[test]
fn validates_before_runner_contact() {
    block(async {
        let contacts = Arc::new(Mutex::new(0));
        let count = contacts.clone();
        let runner = mock_runner(move |_, _| {
            *count.lock().unwrap() += 1;
            None
        });
        let state = build_state_with_runner(runner.url());
        for invalid in [
            json!({"type":"touch_path"}),
            {
                let mut a = action("snapshot");
                a["path"]["samples"][1]["t_ms"] = json!(0);
                a
            },
            {
                let mut a = action("snapshot");
                a["allow_occluded"] = json!(true);
                a
            },
            {
                let mut a = action("snapshot");
                a.as_object_mut().unwrap().remove("snapshot");
                a
            },
        ] {
            let (status, value) = request(&state, "POST", "/agent/input", invalid).await;
            assert_eq!(status, StatusCode::BAD_REQUEST, "{value}");
            assert_eq!(value["outcome"], "not_sent");
        }
        assert_eq!(*contacts.lock().unwrap(), 0);
    });
}

async fn exercise(case: &'static str) -> (StatusCode, Value, Vec<Value>) {
    let writes = Arc::new(Mutex::new(Vec::new()));
    let seen = writes.clone();
    let state_holder = Arc::new(Mutex::new(None::<Arc<AppState>>));
    let revoke = state_holder.clone();
    let reads = Arc::new(std::sync::atomic::AtomicUsize::new(0));
    let runner = mock_runner(move |request, _| {
        if request.starts_with("POST /session ") {
            return Some((
                Duration::ZERO,
                r#"{"value":{"sessionId":"SESSION"}}"#.into(),
            ));
        }
        if request.contains("/window/size") {
            return Some((
                Duration::ZERO,
                r#"{"value":{"width":430,"height":932}}"#.into(),
            ));
        }
        if request.starts_with("GET /session/SESSION ") {
            return Some((
                Duration::ZERO,
                json!({"value":{"capabilities":{"ipu:timedDragPath":case!="old_runner"}}})
                    .to_string(),
            ));
        }
        if request.contains("/source?format=json") {
            if reads.fetch_add(1, std::sync::atomic::Ordering::SeqCst) > 0 {
                if let Some(state) = revoke.lock().unwrap().as_ref() {
                    match case {
                        "privacy_revoked" => {
                            state
                                .privacy_epoch
                                .fetch_add(1, std::sync::atomic::Ordering::AcqRel);
                        }
                        "owner_revoked" => {
                            state
                                .owner_epoch
                                .fetch_add(1, std::sync::atomic::Ordering::AcqRel);
                        }
                        _ => {}
                    }
                }
            }
            return Some((Duration::ZERO, tree(case == "covered")));
        }
        if request.starts_with("POST ") && request.contains("/actions ") {
            let body = request.split("\r\n\r\n").nth(1).unwrap();
            seen.lock()
                .unwrap()
                .push(serde_json::from_str(body).unwrap());
            if case == "lost_reply" {
                return None;
            }
        }
        Some((Duration::ZERO, r#"{"value":null}"#.into()))
    });
    let state = build_state_with_runner(runner.url());
    *state_holder.lock().unwrap() = Some(state.clone());
    let (status, screen) = request(&state, "GET", "/agent/elements", Value::Null).await;
    assert_eq!(status, StatusCode::OK, "{screen}");
    let mut body = action(screen["snapshot"].as_str().unwrap());
    match case {
        "stale" => body["snapshot"] = json!("stale"),
        "viewport" => body["path"]["viewport"]["width"] = json!(932),
        "outside" => body["path"]["samples"][1]["x"] = json!(300),
        "unbound" => {
            body.as_object_mut().unwrap().remove("element");
        }
        _ => {}
    }
    let (status, value) = request(&state, "POST", "/agent/input", body).await;
    let recorded = writes.lock().unwrap().clone();
    (status, value, recorded)
}

#[test]
fn sends_one_contact_with_original_timing_through_guarded_router() {
    block(async {
        for case in ["valid", "unbound"] {
            let (status, value, writes) = exercise(case).await;
            assert_eq!(status, StatusCode::OK, "{value}");
            assert_eq!(writes.len(), 1);
            let steps = writes[0]["actions"][0]["actions"].as_array().unwrap();
            assert_eq!(steps[2], json!({"type":"pause","duration":20}));
            assert_eq!(steps[3], json!({"type":"pause","duration":17}));
            assert_eq!(steps[4]["duration"], 36);
            assert_eq!(steps[5]["duration"], 47);
            assert_eq!(
                steps
                    .iter()
                    .filter_map(|x| x["duration"].as_u64())
                    .sum::<u64>(),
                150
            );
        }
    });
}

#[test]
fn refuses_stale_screen_changed_viewport_occlusion_and_target_escape_without_touch() {
    block(async {
        for (case, error) in [
            ("stale", "stale_element_snapshot"),
            ("viewport", "viewport_changed"),
            ("covered", "element_occluded"),
            ("outside", "touch_outside_target"),
            ("old_runner", "runner_upgrade_required"),
        ] {
            let (status, value, writes) = exercise(case).await;
            assert!(status.is_client_error(), "{case}: {value}");
            assert_eq!(value["error"], error, "{case}: {value}");
            assert!(writes.is_empty(), "{case}: {writes:?}");
            assert_eq!(value["outcome"], "not_sent");
        }
    });
}

#[test]
fn a_lost_touch_reply_is_unknown_and_never_replayed() {
    block(async {
        let (status, value, writes) = exercise("lost_reply").await;
        assert!(status.is_server_error(), "{value}");
        assert_eq!(writes.len(), 1);
        assert_eq!(value["retry_safe"], false, "{value}");
    });
}

#[test]
fn privacy_or_owner_revocation_during_preparation_never_dispatches_contact() {
    block(async {
        for case in ["privacy_revoked", "owner_revoked"] {
            let (status, value, writes) = exercise(case).await;
            assert!(!status.is_success(), "{case}: {value}");
            assert!(writes.is_empty(), "{case}: {writes:?}");
        }
    });
}
