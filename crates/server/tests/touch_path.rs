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
    request_as(state, method, path, body, "touch-test").await
}

async fn request_as(
    state: &Arc<AppState>, method: &str, path: &str, body: Value, owner: &str,
) -> (StatusCode, Value) {
    let req = Request::builder()
        .method(method)
        .uri(path)
        .header("x-phone-owner", owner)
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
            {
                let mut a = action("snapshot");
                a["context"] = json!({"application":"Fixture", "present":[]});
                a
            },
            {
                let mut a = action("snapshot");
                a["context"] = json!({"application":"Fixture", "present":["Target"], "ignore_all":true});
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
                    "privacy_revoked" | "scoped_privacy_revoked" => {
                            state
                                .privacy_epoch
                                .fetch_add(1, std::sync::atomic::Ordering::AcqRel);
                        }
                    "owner_revoked" | "scoped_owner_revoked" => {
                            state
                                .owner_epoch
                                .fetch_add(1, std::sync::atomic::Ordering::AcqRel);
                        }
                        _ => {}
                    }
                }
            }
            let read = reads.load(std::sync::atomic::Ordering::SeqCst);
            let mut source: Value = serde_json::from_str(&tree(case.ends_with("covered"))).unwrap();
            if case.contains("tab_proxy") {
                let root = &mut source["value"];
                let target = json!({"type":"XCUIElementTypeOther","label":"Target",
                    "rect":{"x":100,"y":200,"width":120,"height":44}});
                let button = json!({"type":"XCUIElementTypeButton",
                    "label":if case.ends_with("different_label") {"Unrelated"} else {""},
                    "rect":{"x":100,"y":200,"width":120,"height":40}});
                let mut bar = json!({"type":"XCUIElementTypeTabBar","label":"Tabs",
                    "rect":{"x":0,"y":190,"width":430,"height":70},"children":[button.clone()]});
                if case.ends_with("ambiguous") { bar["children"].as_array_mut().unwrap().push(button); }
                let background = json!({"type":"XCUIElementTypeOther","children":[{
                    "type":"XCUIElementTypeCell","rect":{"x":0,"y":150,"width":430,"height":650}}]});
                root["children"] = json!([background,bar,target]);
                if case.ends_with("overlay") || case.ends_with("foreground_cell") {
                    root["children"].as_array_mut().unwrap().push(json!({
                        "type":if case.ends_with("foreground_cell") {"XCUIElementTypeCell"} else {"XCUIElementTypeButton"},
                        "label":"Real overlay","rect":{"x":100,"y":200,"width":120,"height":44}}));
                }
                if case.ends_with("outside_button") {
                    root["children"][1]["children"][0]["rect"] = json!({"x":110,"y":200,"width":110,"height":40});
                }
            }
            if case.contains("background_cell") || case == "foreground_cell" {
                let root = &mut source["value"];
                let mut target = root["children"][0].clone();
                target["type"] = json!("XCUIElementTypeOther");
                let cell = json!({"type":"XCUIElementTypeOther", "children":[{
                    "type":"XCUIElementTypeCell", "rect":{"x":0,"y":190,"width":430,"height":150}}]});
                root["children"] = if case == "foreground_cell" { json!([target, cell["children"][0].clone()]) }
                    else { json!([cell, target]) };
            }
            if case.contains("layout_bar") {
                let mut wrapper = json!({"type":"XCUIElementTypeToolbar","label":"Toolbar",
                    "rect":{"x":0,"y":0,"width":430,"height":932}});
                if case.ends_with("child") {
                    wrapper["children"] = json!([{"type":"XCUIElementTypeButton","label":"Overlay",
                        "rect":{"x":100,"y":200,"width":120,"height":44}}]);
                }
                source["value"]["children"].as_array_mut().unwrap().push(wrapper);
            }
            if matches!(case, "large_keyboard" | "large_button" | "fixed_bar" | "partial_layout_bar") {
                let (kind, x, y, width, height) = match case {
                    "large_keyboard" => ("Keyboard", 0, 0, 430, 932),
                    "large_button" => ("Button", 0, 0, 430, 932),
                    "partial_layout_bar" => ("Toolbar", 130, 0, 300, 932),
                    _ => ("Toolbar", 0, 200, 430, 44),
                };
                source["value"]["children"].as_array_mut().unwrap().push(json!({
                    "type":format!("XCUIElementType{kind}"), "label":"Cover",
                    "rect":{"x":x,"y":y,"width":width,"height":height}}));
            }
            if case.starts_with("scoped_") || case == "strict_dynamic" {
                let root = &mut source["value"];
                if case == "scoped_app" && read > 1 { root["label"] = json!("Other"); }
                let children = root["children"].as_array_mut().unwrap();
                children.push(json!({"type":"XCUIElementTypeStaticText","label":"Context page",
                    "rect":{"x":20,"y":90,"width":120,"height":20}}));
                if case == "scoped_anchor" && read > 1 { children.last_mut().unwrap()["label"] = json!("Other page"); }
                let timer = json!({"type":"XCUIElementTypeStaticText","label":format!("Countdown {read}"),
                    "rect":{"x":120,"y":if case=="scoped_corridor" {220} else {500},"width":80,"height":20}});
                if case == "scoped_index_shift" && read > 1 { children.insert(0, timer); }
                else { children.push(timer); }
                if read > 1 {
                    match case {
                        "scoped_moved" => children[0]["rect"]["x"] = json!(101),
                        "scoped_state" => children[0]["isEnabled"] = json!(false),
                        "scoped_replaced" => children[0]["label"] = json!("Replacement"),
                        "scoped_duplicate" => {
                            let mut duplicate = children[0].clone();
                            duplicate["rect"]["x"] = json!(300); children.push(duplicate);
                        },
                        "scoped_warning" => children.push(json!({"type":"XCUIElementTypeStaticText",
                            "label":"请完成安全验证","rect":{"x":20,"y":600,"width":180,"height":20}})),
                        "scoped_overlay" => children.push(json!({"type":"XCUIElementTypeButton",
                            "label":"Overlay","rect":{"x":80,"y":180,"width":160,"height":80}})),
                        _ => {},
                    }
                }
            }
            return Some((Duration::ZERO, source.to_string()));
        }
        if request.starts_with("POST ") && request.contains("/actions ") {
            let body = request.split("\r\n\r\n").nth(1).unwrap();
            seen.lock()
                .unwrap()
                .push(serde_json::from_str(body).unwrap());
            if case.ends_with("lost_reply") {
                return None;
            }
        }
        Some((Duration::ZERO, r#"{"value":null}"#.into()))
    });
    let state = build_state_with_runner(runner.url());
    *state_holder.lock().unwrap() = Some(state.clone());
    if case.starts_with("scoped_") && case != "scoped_unclaimed" {
        let (status, _) = request(&state, "POST", "/agent/owner", json!({"claim":true})).await;
        assert_eq!(status, StatusCode::OK);
    }
    let (status, screen) = request(&state, "GET", "/agent/elements", Value::Null).await;
    assert_eq!(status, StatusCode::OK, "{screen}");
    let mut body = action(screen["snapshot"].as_str().unwrap());
    body["element"] = json!(screen["elements"].as_array().unwrap().iter()
        .position(|r| r["label"] == "Target").unwrap());
    if case == "scoped_expired" { tokio::time::sleep(Duration::from_millis(5050)).await; }
    if case == "scoped_released" {
        request(&state, "POST", "/agent/owner", json!({"release":true})).await;
        request(&state, "POST", "/agent/owner", json!({"claim":true})).await;
    }
    if case.starts_with("scoped_") {
        body["context"] = json!({"application":"Fixture","present":["Context page"],"absent":["Wrong page"]});
    }
    match case {
        "stale" => body["snapshot"] = json!("stale"),
        "viewport" => body["path"]["viewport"]["width"] = json!(932),
        "outside" => body["path"]["samples"][1]["x"] = json!(300),
        "unbound" => {
            body.as_object_mut().unwrap().remove("element");
        }
        "scoped_unbound" => { body.as_object_mut().unwrap().remove("element"); },
        "tab_proxy_outside_button" => {
            body["path"]["samples"][0]["x"] = json!(105);
        },
        "scoped_bad_token" => body["snapshot"] = json!("not-observed"),
        "scoped_viewport" => body["path"]["viewport"]["width"] = json!(932),
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

#[test]
fn scoped_contacts_tolerate_only_unrelated_live_updates() {
    block(async {
        for case in ["scoped_valid", "scoped_index_shift", "scoped_unbound"] {
            let (status, value, writes) = exercise(case).await;
            assert!(status.is_success(), "{case}: {value}");
            assert_eq!(writes.len(), 1, "{case}");
            let actions = writes[0]["actions"][0]["actions"].as_array().unwrap();
            assert_eq!(actions.iter().filter(|s| s["type"] == "pointerDown").count(), 1);
            assert_eq!(actions.iter().filter(|s| s["type"] == "pointerUp").count(), 1);
        }
        let (status, value, writes) = exercise("strict_dynamic").await;
        assert_eq!(status, StatusCode::CONFLICT, "{value}");
        assert_eq!(value["error"], "stale_element_snapshot");
        assert!(writes.is_empty());
    });
}

#[test]
fn scoped_contacts_reject_changed_context_and_unobserved_baselines() {
    block(async {
        for (case, error) in [
            ("scoped_moved", "touch_context_changed"),
            ("scoped_state", "touch_context_changed"),
            ("scoped_replaced", "touch_context_changed"),
            ("scoped_anchor", "touch_context_changed"),
            ("scoped_app", "touch_context_changed"),
            ("scoped_corridor", "touch_context_changed"),
            ("scoped_overlay", "touch_context_changed"),
            ("scoped_duplicate", "touch_target_changed"),
            ("scoped_warning", "touch_context_blocked"),
            ("scoped_covered", "element_occluded"),
            ("scoped_bad_token", "touch_context_expired"),
            ("scoped_unclaimed", "touch_context_expired"),
            ("scoped_released", "touch_context_expired"),
            ("scoped_expired", "touch_context_expired"),
            ("scoped_viewport", "viewport_changed"),
        ] {
            let (status, value, writes) = exercise(case).await;
            assert!(status.is_client_error(), "{case}: {value}");
            assert_eq!(value["error"], error, "{case}: {value}");
            assert_eq!(value["outcome"], "not_sent", "{case}: {value}");
            assert!(writes.is_empty(), "{case}: {writes:?}");
        }
    });
}

#[test]
fn scoped_contact_still_obeys_privacy_and_owner_revocation() {
    block(async {
        for case in ["scoped_privacy_revoked", "scoped_owner_revoked"] {
            let (status, value, writes) = exercise(case).await;
            assert!(!status.is_success(), "{case}: {value}");
            assert!(writes.is_empty(), "{case}: {writes:?}");
        }
    });
}

#[test]
fn a_scoped_lost_reply_is_not_replayed() {
    block(async {
        let (status, value, writes) = exercise("scoped_lost_reply").await;
        assert!(status.is_server_error(), "{value}");
        assert_eq!(writes.len(), 1);
        assert_eq!(value["retry_safe"], false, "{value}");
    });
}

#[test]
fn reserving_an_owner_neither_drives_nor_takes_over_or_clears_privacy() {
    block(async {
        let contacts = Arc::new(Mutex::new(0));
        let count = contacts.clone();
        let runner = mock_runner(move |_, _| { *count.lock().unwrap() += 1; None });
        let state = build_state_with_runner(runner.url());
        *state.private_until.lock().unwrap() = Some(std::time::Instant::now() + Duration::from_secs(60));
        let (status, _) = request(&state, "POST", "/agent/owner", json!({"claim":true})).await;
        assert_eq!(status, StatusCode::OK);
        let (status, _) = request_as(&state, "POST", "/agent/owner", json!({"claim":true}), "other").await;
        assert_eq!(status, StatusCode::CONFLICT);
        let (status, _) = request(&state, "POST", "/agent/owner", json!({"claim":true,"release":true})).await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert!(state.private_until.lock().unwrap().is_some());
        assert_eq!(*contacts.lock().unwrap(), 0);
    });
}

#[test]
fn layout_bar_wrappers_do_not_occlude_but_real_controls_still_do() {
    block(async {
        for case in ["layout_bar", "scoped_layout_bar"] {
            let (status, value, writes) = exercise(case).await;
            assert_eq!(status, StatusCode::OK, "{case}: {value}");
            assert_eq!(writes.len(), 1, "{case}");
        }
        for case in ["layout_bar_child", "scoped_layout_bar_child", "large_keyboard",
            "large_button", "fixed_bar", "partial_layout_bar"] {
            let (status, value, writes) = exercise(case).await;
            assert_eq!(status, StatusCode::CONFLICT, "{case}: {value}");
            assert_eq!(value["error"], "element_occluded", "{case}: {value}");
            assert_eq!(value["outcome"], "not_sent");
            assert!(writes.is_empty(), "{case}: {writes:?}");
        }
    });
}

#[test]
fn a_background_list_cell_does_not_cover_a_later_footer_control() {
    block(async {
        for case in ["background_cell", "scoped_background_cell"] {
            let (status, value, writes) = exercise(case).await;
            assert_eq!(status, StatusCode::OK, "{case}: {value}");
            assert_eq!(writes.len(), 1);
        }
        let (status, value, writes) = exercise("foreground_cell").await;
        assert_eq!(status, StatusCode::CONFLICT, "{value}");
        assert_eq!(value["error"], "element_occluded");
        assert_eq!(value["outcome"], "not_sent");
        assert!(writes.is_empty());
    });
}

#[test]
fn tab_accessibility_proxies_share_the_native_button_but_not_real_overlays() {
    block(async {
        for case in ["tab_proxy", "scoped_tab_proxy"] {
            let (status, value, writes) = exercise(case).await;
            assert_eq!(status, StatusCode::OK, "{case}: {value}");
            assert_eq!(writes.len(), 1, "{case}");
        }
        for case in ["tab_proxy_overlay", "scoped_tab_proxy_overlay", "tab_proxy_foreground_cell",
            "tab_proxy_different_label", "tab_proxy_ambiguous", "tab_proxy_outside_button"] {
            let (status, value, writes) = exercise(case).await;
            assert_eq!(status, StatusCode::CONFLICT, "{case}: {value}");
            assert_eq!(value["error"], "element_occluded", "{case}: {value}");
            assert_eq!(value["outcome"], "not_sent");
            assert!(writes.is_empty(), "{case}: {writes:?}");
        }
    });
}
