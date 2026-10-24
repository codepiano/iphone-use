//! Token-only continuation through actual HTTP entry points. The runner is synthetic and no
//! physical device is touched. Each test records all native calls, including refused attempts.
mod support;
use axum::body::Body;
use axum::http::{header, Request, StatusCode};
use http_body_util::BodyExt;
use serde_json::{json, Value};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use support::{block, build_state_with_runner, mock_runner, MockRunner};
use tower::ServiceExt;

struct Fixture {
    _runner: MockRunner,
    state: Arc<server::http::AppState>,
    calls: Arc<Mutex<Vec<String>>>,
    text: Arc<Mutex<String>>,
    failure: Arc<Mutex<Option<&'static str>>>,
}
impl Fixture {
    fn new(guarded: bool) -> Self {
        Self::with_capabilities(guarded, guarded)
    }
    fn with_capabilities(guarded: bool, continuation: bool) -> Self {
        let calls = Arc::new(Mutex::new(Vec::new()));
        let text = Arc::new(Mutex::new(String::new()));
        let failure = Arc::new(Mutex::new(None));
        let (seen, typed, fail) = (calls.clone(), text.clone(), failure.clone());
        let runner = mock_runner(move |request, _| {
            seen.lock().unwrap().push(request.to_string());
            let response = if request.starts_with("POST /session ") {
                json!({"value":{"sessionId":"SESSION","capabilities":{"ipu:guardedInput":guarded,"ipu:inputContinuation":continuation}}})
            } else if request.contains("/wda/input-target") {
                json!({"value":{"token":"bound-field"}})
            } else if request.contains("/wda/keys") {
                let body: Value =
                    serde_json::from_str(request.split("\r\n\r\n").nth(1).unwrap()).unwrap();
                assert_eq!(body["inputTarget"], "bound-field");
                match *fail.lock().unwrap() {
                    Some("transport") => return None,
                    Some("focus") => {
                        let body = r#"{"value":{"error":"invalid argument","message":"input_target_focus_changed; nothing was sent"}}"#;
                        return Some((Duration::ZERO,format!("HTTP/1.1 400 Bad Request\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",body.len(),body)));
                    }
                    _ => {}
                }
                typed
                    .lock()
                    .unwrap()
                    .push_str(body["value"][0].as_str().unwrap());
                return Some((
                    Duration::from_millis(250),
                    json!({"value":null}).to_string(),
                ));
            } else if request.contains("/source") {
                json!({"value":{"type":"XCUIElementTypeApplication","label":"Fixture","rect":{"x":0,"y":0,"width":390,"height":844},
                    "children":[{"type":"XCUIElementTypeTextField","label":"Draft","value":typed.lock().unwrap().clone(),
                        "isFocused":"1","isEnabled":"1","rect":{"x":10,"y":100,"width":300,"height":50},"children":[]}]}})
            } else if request.contains("/window/size") {
                json!({"value":{"width":390,"height":844}})
            } else {
                json!({"value":null})
            };
            Some((Duration::ZERO, response.to_string()))
        });
        let state = build_state_with_runner(runner.url());
        Self {
            _runner: runner,
            state,
            calls,
            text,
            failure,
        }
    }
    async fn call(
        &self,
        path: &str,
        owner: Option<&str>,
        body: Option<Value>,
        takeover: bool,
    ) -> (StatusCode, Value) {
        let mut request = Request::builder()
            .method(if body.is_some() { "POST" } else { "GET" })
            .uri(path)
            .header("x-phone-control", "1")
            .header(header::CONTENT_TYPE, "application/json");
        if let Some(owner) = owner {
            request = request.header("x-phone-owner", owner);
        }
        if takeover {
            request = request.header("x-phone-owner-takeover", "1");
        }
        let response = server::http::router(self.state.clone())
            .oneshot(
                request
                    .body(Body::from(body.map(|b| b.to_string()).unwrap_or_default()))
                    .unwrap(),
            )
            .await
            .unwrap();
        let status = response.status();
        let bytes = response.into_body().collect().await.unwrap().to_bytes();
        (
            status,
            serde_json::from_slice(&bytes).unwrap_or(Value::Null),
        )
    }
    async fn start(&self, batch: bool) -> String {
        let action = json!({"type":"text","text":"字".repeat(500),"budget_ms":6000});
        let payload = if batch {
            json!({"steps":[{"kind":"action","action":action},{"kind":"action","action":{"type":"home"}}]})
        } else {
            action
        };
        let (status, body) = self
            .call(
                if batch {
                    "/agent/actions"
                } else {
                    "/agent/input"
                },
                Some("a"),
                Some(payload),
                false,
            )
            .await;
        assert_eq!(status, StatusCode::BAD_GATEWAY, "{body}");
        assert_eq!(body["characters_confirmed"], 200, "{body}");
        assert_eq!(body["characters_uncertain"], 0, "{body}");
        assert_eq!(body["remaining_text"], "字".repeat(300), "{body}");
        assert_eq!(body["continuation_safe"], true, "{body}");
        assert_eq!(
            body["retry_safe"], false,
            "whole-request replay stays unsafe: {body}"
        );
        body["continue_token"]
            .as_str()
            .expect("safe continuation token")
            .to_string()
    }
    fn count(&self, path: &str) -> usize {
        self.calls
            .lock()
            .unwrap()
            .iter()
            .filter(|r| r.contains(path))
            .count()
    }
}

#[test]
fn continuation_reuses_one_native_target_after_reads_and_cannot_be_replayed() {
    block(async {
        for batch in [false, true] {
            let f = Fixture::new(true);
            let token = f.start(batch).await;
            assert_eq!(f.count("/wda/homescreen"), 0);
            let (status, body) = f.call("/agent/elements", Some("a"), None, false).await;
            assert_eq!(status, StatusCode::OK, "{body}");
            let (status, body) = f
                .call(
                    "/agent/input",
                    Some("a"),
                    Some(json!({"type":"text","continue_token":token})),
                    false,
                )
                .await;
            assert_eq!(status, StatusCode::OK, "{body}");
            assert_eq!(body["ok"], true, "{body}");
            assert_eq!(*f.text.lock().unwrap(), "字".repeat(500));
            assert_eq!(
                f.count("/wda/input-target"),
                1,
                "resume never rebinds focus"
            );
            assert_eq!(f.count("/wda/keys"), 3);
            let before = f.calls.lock().unwrap().len();
            let (status, body) = f
                .call(
                    "/agent/input",
                    Some("a"),
                    Some(json!({"type":"text","continue_token":token})),
                    false,
                )
                .await;
            assert_eq!(status, StatusCode::CONFLICT, "{body}");
            assert_eq!(body["error"], "input_continuation_expired");
            assert_eq!(
                f.calls.lock().unwrap().len(),
                before,
                "consumed token sends no native request"
            );
        }
    });
}

#[test]
fn wrong_owner_does_not_consume_but_release_takeover_and_session_changes_invalidate() {
    block(async {
        for reason in ["wrong-owner", "release", "takeover", "session", "mutation"] {
            let f = Fixture::new(true);
            let token = f.start(false).await;
            if reason == "wrong-owner" {
                let (status, _) = f
                    .call(
                        "/agent/input",
                        Some("b"),
                        Some(json!({"type":"text","continue_token":token})),
                        false,
                    )
                    .await;
                assert_eq!(status, StatusCode::CONFLICT);
            } else if reason == "release" {
                let (status, _) = f
                    .call(
                        "/agent/owner",
                        Some("a"),
                        Some(json!({"release":true})),
                        false,
                    )
                    .await;
                assert_eq!(status, StatusCode::OK);
            } else if reason == "takeover" {
                let (status, _) = f
                    .call(
                        "/agent/input",
                        Some("b"),
                        Some(json!({"type":"text","continue_token":token})),
                        true,
                    )
                    .await;
                assert_eq!(status, StatusCode::CONFLICT);
            } else if reason == "session" {
                f.state
                    .runner
                    .as_ref()
                    .unwrap()
                    .lock()
                    .await
                    .invalidate_session();
            } else {
                let (status, body) = f
                    .call(
                        "/agent/input",
                        Some("a"),
                        Some(json!({"type":"home"})),
                        false,
                    )
                    .await;
                assert_eq!(status, StatusCode::OK, "{body}");
            }
            let before = f.count("/wda/keys");
            let (status, body) = f
                .call(
                    "/agent/input",
                    Some("a"),
                    Some(json!({"type":"text","continue_token":token})),
                    reason == "takeover",
                )
                .await;
            if reason == "wrong-owner" {
                assert_eq!(status, StatusCode::OK, "{body}");
            } else {
                assert_eq!(status, StatusCode::CONFLICT, "{reason}: {body}");
                assert_eq!(body["error"], "input_continuation_expired");
                assert_eq!(f.count("/wda/keys"), before);
            }
            assert_eq!(f.count("/wda/input-target"), 1);
        }
    });
}

#[test]
fn resume_never_rebinds_after_focus_loss_or_unknown_delivery() {
    block(async {
        for failure in ["focus", "transport"] {
            let f = Fixture::new(true);
            let token = f.start(false).await;
            *f.failure.lock().unwrap() = Some(failure);
            let (status, body) = f
                .call(
                    "/agent/input",
                    Some("a"),
                    Some(json!({"type":"text","continue_token":token})),
                    false,
                )
                .await;
            assert!(!status.is_success(), "{body}");
            assert!(body.get("continue_token").is_none(), "{body}");
            if failure == "transport" {
                assert_eq!(body["characters_total"], 300, "resumed-call counts: {body}");
                assert_eq!(body["characters_uncertain"], 200, "{body}");
                assert_eq!(body["remaining_text"], "字".repeat(300));
            } else {
                assert_eq!(body["error"], "runner_rejected");
            }
            let (_, body) = f
                .call(
                    "/agent/input",
                    Some("a"),
                    Some(json!({"type":"text","continue_token":token})),
                    false,
                )
                .await;
            assert_eq!(body["error"], "input_continuation_expired");
            assert_eq!(f.count("/wda/keys"), 2, "failed chunk is never replayed");
            assert_eq!(f.count("/wda/input-target"), 1);
        }
    });
}

#[test]
fn invalid_continuations_and_anonymous_budgets_never_reach_runner() {
    block(async {
        let f = Fixture::new(true);
        for body in [
            json!({"type":"text","continue_token":"bad"}),
            json!({"type":"text","continue_token":"a".repeat(64),"text":"extra"}),
            json!({"type":"text","text":"x","budget_ms":5999}),
        ] {
            let (status, _) = f.call("/agent/input", Some("a"), Some(body), false).await;
            assert_eq!(status, StatusCode::BAD_REQUEST);
        }
        let (status, _) = f
            .call(
                "/agent/input",
                None,
                Some(json!({"type":"text","text":"x","budget_ms":6000})),
                false,
            )
            .await;
        assert_eq!(status, StatusCode::CONFLICT); // The named owner already holds this fixture.
        assert!(f.calls.lock().unwrap().is_empty());
        let anonymous = Fixture::new(true);
        let (status, body) = anonymous
            .call(
                "/agent/input",
                None,
                Some(json!({"type":"text","text":"x","budget_ms":6000})),
                false,
            )
            .await;
        assert_eq!(status, StatusCode::BAD_REQUEST, "{body}");
        assert_eq!(body["error"], "input_owner_required");
        assert!(anonymous.calls.lock().unwrap().is_empty());
        for guarded in [false, true] {
            let f = Fixture::with_capabilities(guarded, false);
            let (status, body) = f
                .call(
                    "/agent/input",
                    Some("a"),
                    Some(json!({"type":"text","text":"x".repeat(300),"budget_ms":6000})),
                    false,
                )
                .await;
            assert_eq!(status, StatusCode::CONFLICT, "{body}");
            assert_eq!(body["error"], "input_continuation_unsupported");
            assert_eq!(f.count("/wda/keys"), 0);
        }
    });
}

#[test]
fn repeated_safe_boundaries_rotate_tokens_without_reselecting_the_field() {
    block(async {
        let f = Fixture::new(true);
        let (mut status, mut body) = f
            .call(
                "/agent/input",
                Some("a"),
                Some(json!({"type":"text","text":"字".repeat(900),"budget_ms":6000})),
                false,
            )
            .await;
        let mut tokens = Vec::new();
        for _ in 0..6 {
            if status == StatusCode::OK {
                break;
            }
            assert_eq!(status, StatusCode::BAD_GATEWAY, "{body}");
            let token = body["continue_token"].as_str().unwrap().to_string();
            assert!(!tokens.contains(&token));
            tokens.push(token.clone());
            (status, body) = f
                .call(
                    "/agent/input",
                    Some("a"),
                    Some(json!({"type":"text","continue_token":token})),
                    false,
                )
                .await;
            if status != StatusCode::OK {
                let (old_status, old_body) = f
                    .call(
                        "/agent/input",
                        Some("a"),
                        Some(json!({"type":"text","continue_token":token})),
                        false,
                    )
                    .await;
                assert_eq!(old_status, StatusCode::CONFLICT, "{old_body}");
            }
        }
        assert_eq!(status, StatusCode::OK, "{body}");
        assert_eq!(*f.text.lock().unwrap(), "字".repeat(900));
        assert_eq!(f.count("/wda/input-target"), 1);
        assert_eq!(f.count("/wda/keys"), 5);
    });
}

#[test]
fn ownership_change_during_a_chunk_stops_before_the_next_chunk_without_a_token() {
    block(async {
        let f = Fixture::new(true);
        let calls = f.calls.clone();
        let state = f.state.clone();
        let handoff = tokio::spawn(async move {
            tokio::time::timeout(Duration::from_secs(5), async {
                while !calls
                    .lock()
                    .unwrap()
                    .iter()
                    .any(|r| r.contains("/wda/keys"))
                {
                    tokio::time::sleep(Duration::from_millis(2)).await;
                }
            })
            .await
            .unwrap();
            state
                .owner_epoch
                .fetch_add(1, std::sync::atomic::Ordering::AcqRel);
        });
        let (_, body) = f
            .call(
                "/agent/input",
                Some("a"),
                Some(json!({"type":"text","text":"字".repeat(500),"budget_ms":15000})),
                false,
            )
            .await;
        handoff.await.unwrap();
        assert_eq!(body["characters_confirmed"], 200, "{body}");
        assert_eq!(body["characters_uncertain"], 0, "{body}");
        assert!(body.get("continue_token").is_none(), "{body}");
        assert_eq!(
            body["detail"]["input_error"], "input_owner_changed",
            "{body}"
        );
        assert_eq!(f.count("/wda/keys"), 1);
    });
}

#[test]
fn cancellation_after_resuming_consumes_the_token_and_never_replays_the_request() {
    block(async {
        let f = Fixture::new(true);
        let token = f.start(false).await;
        {
            let request = f.call(
                "/agent/input",
                Some("a"),
                Some(json!({"type":"text","continue_token":token})),
                false,
            );
            tokio::pin!(request);
            tokio::select! {
                reply=&mut request => panic!("resume completed before cancellation: {reply:?}"),
                _=async {
                    tokio::time::timeout(Duration::from_secs(5),async {
                        while f.count("/wda/keys")<2 {tokio::time::sleep(Duration::from_millis(2)).await;}
                    }).await.unwrap();
                } => {}
            }
            // Dropping this request may leave the chunk on the phone. No acknowledgement,
            // and therefore no new token, exists; the consumed token must never be replayed.
        }
        let (status, body) = f
            .call(
                "/agent/input",
                Some("a"),
                Some(json!({"type":"text","continue_token":token})),
                false,
            )
            .await;
        assert_eq!(status, StatusCode::CONFLICT, "{body}");
        assert_eq!(body["error"], "input_continuation_expired");
        assert_eq!(f.count("/wda/keys"), 2);
        assert_eq!(f.count("/wda/input-target"), 1);
    });
}

#[test]
fn input_that_loses_ownership_while_waiting_for_the_runner_never_binds_or_types() {
    block(async {
        for characters in [3, 500] {
            let f = Fixture::new(true);
            let guard = f.state.runner.as_ref().unwrap().lock().await;
            let request = f.call(
                "/agent/input",
                Some("a"),
                Some(json!({"type":"text","text":"字".repeat(characters)})),
                false,
            );
            tokio::pin!(request);
            tokio::select! {
                reply=&mut request => panic!("request bypassed the runner lock: {reply:?}"),
                _=async {
                    tokio::time::timeout(Duration::from_secs(5),async {
                        loop {
                            let claimed = f.state.owner.lock().unwrap().as_ref().is_some_and(|o| o.name=="a");
                            if claimed { break; }
                            tokio::time::sleep(Duration::from_millis(2)).await;
                        }
                    }).await.unwrap();
                } => {}
            }
            // The takeover itself is authorized by the header; the invalid body then fails before
            // waiting for runner. This changes the owner while A is still queued at the real lock.
            let (status, _) = f
                .call(
                    "/agent/input",
                    Some("b"),
                    Some(json!({"type":"text","text":"x","budget_ms":1})),
                    true,
                )
                .await;
            assert_eq!(status, StatusCode::BAD_REQUEST);
            drop(guard);
            let (status, body) = tokio::time::timeout(Duration::from_secs(5), &mut request)
                .await
                .unwrap();
            assert_eq!(status, StatusCode::CONFLICT, "{body}");
            assert_eq!(body["error"], "input_owner_changed");
            assert!(
                f.calls.lock().unwrap().is_empty(),
                "no target read, focus change, unlock or text request"
            );
        }
    });
}

#[test]
fn completing_input_only_renews_its_existing_lease_and_never_reclaims_ownership() {
    block(async {
        for transition in ["takeover", "release", "expiry"] {
            let mut f = Fixture::new(true);
            Arc::get_mut(&mut f.state).unwrap().owner_lease_secs = 1;
            let request = f.call(
                "/agent/input",
                Some("a"),
                Some(json!({"type":"text","text":"字".repeat(500),"budget_ms":6000})),
                true,
            );
            tokio::pin!(request);
            tokio::select! {
                reply=&mut request => panic!("input finished before ownership transition: {reply:?}"),
                _=async {
                    tokio::time::timeout(Duration::from_secs(5),async {
                        while f.count("/wda/keys")==0 {tokio::time::sleep(Duration::from_millis(2)).await;}
                    }).await.unwrap();
                } => {}
            }
            let epoch = f
                .state
                .owner_epoch
                .load(std::sync::atomic::Ordering::Acquire);
            if transition == "takeover" {
                let (status, _) = f
                    .call(
                        "/agent/input",
                        Some("b"),
                        Some(json!({"type":"text","text":"x","budget_ms":1})),
                        true,
                    )
                    .await;
                assert_eq!(status, StatusCode::BAD_REQUEST);
            } else if transition == "release" {
                let (status, _) = f
                    .call(
                        "/agent/owner",
                        Some("a"),
                        Some(json!({"release":true})),
                        false,
                    )
                    .await;
                assert_eq!(status, StatusCode::OK);
            } else {
                f.state.owner.lock().unwrap().as_mut().unwrap().last_seen =
                    std::time::Instant::now() - Duration::from_secs(2);
            }
            let (_, body) = (&mut request).await;
            assert_eq!(body["characters_confirmed"], 200, "{body}");
            let owner = f
                .state
                .owner
                .lock()
                .unwrap()
                .as_ref()
                .map(|owner| owner.name.clone());
            match transition {
                "takeover" => {
                    assert_eq!(owner.as_deref(), Some("b"));
                    assert!(body.get("continue_token").is_none());
                }
                "release" => {
                    assert!(owner.is_none());
                    assert!(body.get("continue_token").is_none());
                }
                "expiry" => {
                    assert_eq!(owner.as_deref(), Some("a"));
                    assert_eq!(
                        f.state
                            .owner_epoch
                            .load(std::sync::atomic::Ordering::Acquire),
                        epoch,
                        "in-flight renewal must not start a new ownership incarnation"
                    );
                    let (status, result) = f
                        .call(
                            "/agent/input",
                            Some("a"),
                            Some(json!({"type":"text","continue_token":body["continue_token"]})),
                            false,
                        )
                        .await;
                    assert_eq!(status, StatusCode::OK, "{result}");
                    assert_eq!(*f.text.lock().unwrap(), "字".repeat(500));
                }
                _ => unreachable!(),
            }
        }
    });
}
