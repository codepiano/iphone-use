//! On-device RemotePairing -> TLS-PSK -> RSD -> XCTest bootstrap.
//! No usbmuxd, lockdown provider, subprocess, or Mac fallback.
use idevice::{
    remote_pairing::{
        connect_tls_psk_tunnel_native, RemotePairingClient, RpPairingFile, RpPairingSocket,
    },
    services::{
        dvt::xctest::{listener::XCUITestListener, TestConfig, XCUITestService},
        installation_proxy::InstallationProxyClient,
        rsd::RsdHandshake,
    },
};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    net::{IpAddr, SocketAddr},
    sync::{Mutex, OnceLock},
    time::Duration,
};
use tokio::{net::TcpStream, sync::oneshot};

#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Configuration {
    pub schema: u8,
    pub endpoint: IpAddr,
    #[serde(default)]
    pub expected_udid: String,
    pub runner_bundle_id: String,
    #[serde(default)]
    pub runner_app_path: String,
    #[serde(default)]
    pub runner_app_container: String,
    #[serde(default)]
    pub runner_bundle_executable: String,
    pub runner_environment: BTreeMap<String, String>,
}
impl Configuration {
    fn validate(&self) -> Result<(), &'static str> {
        if self.schema != 1 {
            return Err("unsupported_schema");
        }
        // Only this phone's loopback / LocalDevVPN gateway, never a LAN Mac.
        if self.endpoint != "127.0.0.1".parse::<IpAddr>().unwrap()
            && self.endpoint != "10.7.0.1".parse::<IpAddr>().unwrap()
        {
            return Err("nonlocal_endpoint");
        }
        if !self.expected_udid.is_empty()
            && (self.expected_udid.len() < 16 || self.expected_udid.len() > 64)
        {
            return Err("invalid_identity");
        }
        if !self.runner_bundle_id.starts_with("com.leeguoo.iphone-use.")
            || !self.runner_bundle_id.ends_with(".xctrunner")
            || (!self.runner_bundle_executable.is_empty()
                && !self.runner_bundle_executable.ends_with("-Runner"))
        {
            return Err("invalid_runner");
        }
        for path in [&self.runner_app_path, &self.runner_app_container] {
            if path.is_empty() {
                continue;
            }
            if !path.starts_with("/private/var/") && !path.starts_with("/var/") {
                return Err("invalid_runner_path");
            }
            if path.contains("..") || path.contains('\0') {
                return Err("invalid_runner_path");
            }
        }
        for (key, value) in &self.runner_environment {
            if !matches!(
                key.as_str(),
                "IPU_RUNNER_TOKEN"
                    | "IPU_DAEMON_TOKEN"
                    | "IPU_DAEMON_PASSWORD"
                    | "IPU_DAEMON_HOST"
                    | "IPU_DAEMON_PORT"
                    | "IPU_DAEMON_ENABLED"
                    | "USE_PORT"
                    | "MJPEG_SERVER_PORT"
            ) || value.len() > 1024
                || value.contains('\0')
            {
                return Err("invalid_environment");
            }
        }
        if self
            .runner_environment
            .get("IPU_DAEMON_HOST")
            .is_some_and(|v| v != "127.0.0.1")
        {
            return Err("nonlocal_daemon_bind");
        }
        for key in ["IPU_RUNNER_TOKEN", "IPU_DAEMON_TOKEN"] {
            if self
                .runner_environment
                .get(key)
                .is_none_or(|v| v.len() < 32)
            {
                return Err("missing_token");
            }
        }
        Ok(())
    }
    fn test_config(&self) -> TestConfig {
        TestConfig {
            runner_bundle_id: self.runner_bundle_id.clone(),
            runner_app_path: self.runner_app_path.clone(),
            runner_app_container: self.runner_app_container.clone(),
            runner_bundle_executable: self.runner_bundle_executable.clone(),
            target_bundle_id: None,
            target_app_path: None,
            target_app_env: None,
            target_app_args: None,
            tests_to_run: Some(vec!["RunnerTests/testServe".into()]),
            tests_to_skip: None,
            runner_env: Some(
                self.runner_environment
                    .iter()
                    .map(|(k, v)| (k.clone(), plist::Value::String(v.clone())))
                    .collect(),
            ),
            runner_args: None,
        }
    }
}

#[derive(Clone, Serialize)]
struct Status {
    phase: &'static str,
    error_code: Option<&'static str>,
}
struct Session {
    status: Status,
    active: bool,
    stop: Option<oneshot::Sender<()>>,
    pin: Option<oneshot::Sender<String>>,
    private_record: Option<Vec<u8>>,
    setup_saved: Option<oneshot::Sender<bool>>,
}
static SESSION: OnceLock<Mutex<Session>> = OnceLock::new();
fn session() -> &'static Mutex<Session> {
    SESSION.get_or_init(|| {
        Mutex::new(Session {
            status: Status {
                phase: "idle",
                error_code: None,
            },
            active: false,
            stop: None,
            pin: None,
            private_record: None,
            setup_saved: None,
        })
    })
}
fn set_phase(phase: &'static str) {
    session().lock().unwrap().status.phase = phase;
}
struct Listener;
impl XCUITestListener for Listener {
    async fn did_begin_executing_test_plan(&mut self) -> Result<(), idevice::IdeviceError> {
        // This means XCTest started, not that daemon HTTP health passed.
        set_phase("test_plan_started");
        Ok(())
    }
}

fn validate_device(handshake: &RsdHandshake, expected_udid: &str) -> Result<u8, &'static str> {
    if handshake
        .properties
        .get("UniqueDeviceID")
        .and_then(|v| v.as_string())
        != Some(expected_udid)
    {
        return Err("device_identity_mismatch");
    }
    let major = handshake
        .properties
        .get("OSVersion")
        .and_then(|v| v.as_string())
        .and_then(|v| v.split('.').next())
        .and_then(|v| v.parse::<u8>().ok())
        .ok_or("missing_ios_version")?;
    if major < 17 {
        return Err("unsupported_ios_version");
    }
    Ok(major)
}

async fn resolve_runner(
    handle: &mut idevice::tcp::handle::AdapterHandle,
    handshake: &RsdHandshake,
    config: &Configuration,
) -> Result<TestConfig, &'static str> {
    if let Some(service) = handshake
        .services
        .get("com.apple.mobile.installation_proxy.shim.remote")
    {
        let stream = handle
            .connect(service.port)
            .await
            .map_err(|_| "runner_metadata_connect_failed")?;
        let mut device = idevice::Idevice::new(Box::new(stream), "iphone-use-on-device");
        device
            .rsd_checkin()
            .await
            .map_err(|_| "runner_metadata_checkin_failed")?;
        let mut proxy = InstallationProxyClient::new(device);
        let mut result =
            TestConfig::from_installation_proxy(&mut proxy, &config.runner_bundle_id, None)
                .await
                .map_err(|_| "runner_not_installed")?;
        result.runner_env = config.test_config().runner_env;
        result.tests_to_run = Some(vec!["RunnerTests/testServe".into()]);
        return Ok(result);
    }
    // Explicit legacy setup remains usable; never guess an app's filesystem path.
    if config.runner_app_path.is_empty()
        || config.runner_app_container.is_empty()
        || config.runner_bundle_executable.is_empty()
    {
        return Err("runner_metadata_service_unavailable");
    }
    Ok(config.test_config())
}

async fn bootstrap(
    mut config: Configuration,
    pair_bytes: Option<Vec<u8>>,
) -> Result<(), &'static str> {
    let first_pair = pair_bytes.is_none();
    let mut pair = match pair_bytes {
        Some(bytes) => {
            RpPairingFile::from_bytes(&bytes).map_err(|_| "invalid_remote_pair_record")?
        }
        None => RpPairingFile::generate("iphone-use-on-device"),
    };
    let address = SocketAddr::new(config.endpoint, 49152);
    set_phase("connecting");
    let stream = TcpStream::connect(address)
        .await
        .map_err(|_| "local_developer_port_unavailable")?;
    let mut client = RemotePairingClient::new(RpPairingSocket::new(stream), "iphone-use-on-device");
    client
        .attempt_pair_verify()
        .await
        .map_err(|_| "remote_pairing_handshake_failed")?;
    set_phase("authenticating");
    if first_pair {
        // Only the explicit first-pair action may request human consent / PIN.
        client
            .pair(&mut pair, || async {
                let (tx, rx) = oneshot::channel();
                {
                    let mut state = session().lock().unwrap();
                    state.pin = Some(tx);
                    state.status.phase = "awaiting_pairing_pin";
                }
                rx.await.unwrap_or_default()
            })
            .await
            .map_err(|_| "new_pairing_failed")?;
    } else {
        // Never silently replace a rejected existing pairing record.
        client
            .validate_pairing(&mut pair)
            .await
            .map_err(|_| "remote_pair_record_rejected")?;
    }
    let port = client
        .create_tcp_listener()
        .await
        .map_err(|_| "tunnel_listener_failed")?;
    let stream = TcpStream::connect(SocketAddr::new(config.endpoint, port))
        .await
        .map_err(|_| "tunnel_connect_failed")?;
    let tunnel = connect_tls_psk_tunnel_native(stream, client.encryption_key())
        .await
        .map_err(|_| "tunnel_auth_failed")?;
    let our_ip = tunnel
        .info
        .client_address
        .parse()
        .map_err(|_| "invalid_tunnel_address")?;
    let peer_ip = tunnel
        .info
        .server_address
        .parse()
        .map_err(|_| "invalid_tunnel_address")?;
    let mtu = tunnel.info.mtu as usize;
    let rsd_port = tunnel.info.server_rsd_port;
    if rsd_port == 0 || mtu < 1280 {
        return Err("invalid_tunnel_parameters");
    }
    let mut adapter =
        idevice::tcp::adapter::Adapter::new(Box::new(tunnel.into_inner()), our_ip, peer_ip);
    adapter.set_mss(mtu.saturating_sub(60));
    let mut handle = adapter.to_async_handle();
    set_phase("discovering");
    let stream = handle
        .connect(rsd_port)
        .await
        .map_err(|_| "rsd_connect_failed")?;
    let handshake = RsdHandshake::new(stream)
        .await
        .map_err(|_| "rsd_handshake_failed")?;
    if first_pair && config.expected_udid.is_empty() {
        // Only initial human-approved pairing may bind identity from this local tunnel.
        config.expected_udid = handshake
            .properties
            .get("UniqueDeviceID")
            .and_then(|v| v.as_string())
            .filter(|v| (16..=64).contains(&v.len()))
            .ok_or("missing_device_identity")?
            .to_owned();
    }
    let major = validate_device(&handshake, &config.expected_udid)?;
    if first_pair {
        let bytes = serde_json::to_vec(
            &serde_json::json!({"configuration":&config,"pairing_record":pair.to_bytes()}),
        )
        .map_err(|_| "setup_encoding_failed")?;
        let (saved, confirmation) = oneshot::channel();
        {
            let mut state = session().lock().unwrap();
            state.private_record = Some(bytes);
            state.setup_saved = Some(saved);
            state.status.phase = "awaiting_setup_storage";
        }
        if !confirmation.await.unwrap_or(false) {
            return Err("setup_not_saved");
        }
    }
    // Preserve the authenticated record even if app discovery or XCTest startup fails.
    set_phase("reading_runner_metadata");
    let test_config = resolve_runner(&mut handle, &handshake, &config).await?;
    set_phase("starting_test_session");
    let result =
        XCUITestService::run_from_rsd(test_config, &mut Listener, None, major, handle, handshake)
            .await
            .map_err(|_| "test_session_failed");
    // Explicitly retain the authenticated control channel for the entire runner lifetime.
    drop(client);
    result
}

/// Copies configuration and RemotePairing bytes before returning. Caller remains owner.
/// Returns 0 when scheduled, 1 if already running, -1 for malformed data.
/// # Safety
/// Both buffers must be valid for their declared lengths for this call.
#[no_mangle]
pub unsafe extern "C" fn ipu_self_launch_start(
    config: *const u8,
    config_len: usize,
    pair: *const u8,
    pair_len: usize,
) -> i32 {
    if config.is_null()
        || pair.is_null()
        || config_len == 0
        || config_len > 65536
        || pair_len == 0
        || pair_len > 65536
    {
        return -1;
    }
    let config: Configuration =
        match serde_json::from_slice(std::slice::from_raw_parts(config, config_len)) {
            Ok(v) => v,
            Err(_) => return -1,
        };
    if config.validate().is_err() || config.expected_udid.is_empty() {
        return -1;
    }
    let pair_bytes = std::slice::from_raw_parts(pair, pair_len).to_vec();
    match RpPairingFile::from_bytes(&pair_bytes) {
        Ok(pair) if pair.e_private_key.verifying_key() == pair.e_public_key => {}
        _ => return -1,
    }
    schedule(config, Some(pair_bytes))
}

/// Explicit human-assisted initial pairing, entirely in the phone process.
/// # Safety
/// Configuration must be valid for the declared length during this call.
#[no_mangle]
pub unsafe extern "C" fn ipu_self_launch_pair_start(config: *const u8, length: usize) -> i32 {
    if config.is_null() || length == 0 || length > 65536 {
        return -1;
    }
    let config: Configuration =
        match serde_json::from_slice(std::slice::from_raw_parts(config, length)) {
            Ok(v) => v,
            Err(_) => return -1,
        };
    if config.validate().is_err() {
        return -1;
    }
    schedule(config, None)
}

fn schedule(config: Configuration, pair_bytes: Option<Vec<u8>>) -> i32 {
    let mut state = session().lock().unwrap();
    if state.active {
        return 1;
    }
    let (stop, stopped) = oneshot::channel();
    state.active = true;
    state.pin = None;
    state.setup_saved = None;
    if let Some(mut old) = state.private_record.take() {
        old.fill(0);
    }
    state.stop = Some(stop);
    state.status = Status {
        phase: "scheduled",
        error_code: None,
    };
    drop(state);
    let spawn = std::thread::Builder::new()
        .name("ipu-self-launch".into())
        .stack_size(8 * 1024 * 1024)
        .spawn(move || {
            let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                let runtime = tokio::runtime::Builder::new_multi_thread()
                    .worker_threads(2)
                    .enable_all()
                    .build()
                    .map_err(|_| "runtime_failed")?;
                runtime.block_on(async {
                    tokio::select! {
                        _ = stopped => Ok(()),
                        result = bootstrap(config, pair_bytes) => result,
                        _ = async {
                            tokio::time::sleep(Duration::from_secs(120)).await;
                            let started = session().lock().unwrap().status.phase == "test_plan_started";
                        if started {
                                std::future::pending::<()>().await;
                            }
                        } => Err("bootstrap_timeout"),
                    }
                })
            }))
            .unwrap_or(Err("launcher_panicked"));
            let mut state = session().lock().unwrap();
            state.active = false;
            state.pin = None;
            state.setup_saved = None;
            state.stop = None;
            state.status = match result {
                Ok(()) => Status {
                    phase: "stopped",
                    error_code: None,
                },
                Err(code) => Status {
                    phase: "failed",
                    error_code: Some(code),
                },
            };
        });
    if spawn.is_err() {
        let mut state = session().lock().unwrap();
        state.active = false;
        state.stop = None;
        state.status = Status {
            phase: "failed",
            error_code: Some("thread_failed"),
        };
        return -1;
    }
    0
}

#[no_mangle]
pub extern "C" fn ipu_self_launch_stop() {
    let mut state = session().lock().unwrap();
    if state.active {
        state.status.phase = "stopping";
    }
    if let Some(stop) = state.stop.take() {
        let _ = stop.send(());
    }
}

/// Accept a human-entered code only while the explicit pairing flow is waiting.
/// # Safety
/// PIN buffer must be valid for length bytes during this call.
#[no_mangle]
pub unsafe extern "C" fn ipu_self_launch_submit_pin(pin: *const u8, length: usize) -> i32 {
    if pin.is_null() || !(4..=8).contains(&length) {
        return -1;
    }
    let bytes = std::slice::from_raw_parts(pin, length);
    if !bytes.iter().all(u8::is_ascii_digit) {
        return -1;
    }
    let mut state = session().lock().unwrap();
    if !state.active || state.status.phase != "awaiting_pairing_pin" {
        return -1;
    }
    if let Some(tx) = state.pin.take() {
        state.status.phase = "authenticating";
        return if tx.send(String::from_utf8_lossy(bytes).into_owned()).is_ok() {
            0
        } else {
            -1
        };
    }
    -1
}

/// Copy the new secret record once to the phone's Keychain, then zero this buffer.
/// Never call this for a diagnostic report.
/// # Safety
/// Non-null output must be writable for capacity bytes.
#[no_mangle]
pub unsafe extern "C" fn ipu_self_launch_take_record(output: *mut u8, capacity: usize) -> usize {
    let mut state = session().lock().unwrap();
    let Some(record) = state.private_record.as_ref() else {
        return 0;
    };
    let required = record.len();
    if !output.is_null() && capacity >= required {
        let mut record = state.private_record.take().unwrap();
        std::ptr::copy_nonoverlapping(record.as_ptr(), output, required);
        record.fill(0);
    }
    required
}

/// Acknowledge atomic on-phone Keychain storage before any runner is started.
#[no_mangle]
pub extern "C" fn ipu_self_launch_setup_saved(success: bool) -> i32 {
    let mut state = session().lock().unwrap();
    if !state.active || state.status.phase != "awaiting_setup_storage" {
        return -1;
    }
    match state.setup_saved.take() {
        Some(tx) => {
            if tx.send(success).is_ok() {
                0
            } else {
                -1
            }
        }
        None => -1,
    }
}

/// NUL-terminated, redacted status. Returns required buffer length including NUL.
/// # Safety
/// A non-null output must be writable for `capacity` bytes.
#[no_mangle]
pub unsafe extern "C" fn ipu_self_launch_status(output: *mut u8, capacity: usize) -> usize {
    let data = serde_json::to_vec(&session().lock().unwrap().status).unwrap();
    let required = data.len() + 1;
    if !output.is_null() && capacity >= required {
        std::ptr::copy_nonoverlapping(data.as_ptr(), output, data.len());
        *output.add(data.len()) = 0;
    }
    required
}

#[cfg(test)]
mod tests {
    use super::*;
    static TEST_LIFECYCLE: Mutex<()> = Mutex::new(());
    fn config() -> Configuration {
        Configuration {
            schema: 1,
            endpoint: "10.7.0.1".parse().unwrap(),
            expected_udid: "SYNTHETIC-DEVICE-14".into(),
            runner_bundle_id: "com.leeguoo.iphone-use.runner.xctrunner".into(),
            runner_app_path: "/private/var/containers/Bundle/Application/fixture/Runner.app".into(),
            runner_app_container: "/private/var/mobile/Containers/Data/Application/fixture".into(),
            runner_bundle_executable: "IPhoneUseRunner-Runner".into(),
            runner_environment: [
                ("IPU_RUNNER_TOKEN".into(), "a".repeat(64)),
                ("IPU_DAEMON_TOKEN".into(), "b".repeat(64)),
            ]
            .into(),
        }
    }
    #[test]
    fn refuses_external_host_and_unrestricted_launch_environment() {
        let mut c = config();
        assert!(c.validate().is_ok());
        c.endpoint = "192.168.1.2".parse().unwrap();
        assert_eq!(c.validate(), Err("nonlocal_endpoint"));
        c.endpoint = "10.7.0.1".parse().unwrap();
        c.runner_environment
            .insert("DYLD_INSERT_LIBRARIES".into(), "fixture".into());
        assert_eq!(c.validate(), Err("invalid_environment"));
    }
    #[test]
    fn runner_configuration_is_authenticated_and_filtered() {
        let mut c = config();
        c.runner_environment.remove("IPU_RUNNER_TOKEN");
        assert_eq!(c.validate(), Err("missing_token"));
        let cfg = config().test_config();
        assert_eq!(cfg.tests_to_run.unwrap(), ["RunnerTests/testServe"]);
        assert!(cfg.target_bundle_id.is_none());
    }
    #[test]
    fn malformed_ffi_inputs_never_connect_and_status_never_contains_secrets() {
        unsafe {
            assert_eq!(
                ipu_self_launch_start(std::ptr::null(), 1, std::ptr::null(), 1),
                -1
            );
        }
        let mut output = [0u8; 256];
        let count = unsafe { ipu_self_launch_status(output.as_mut_ptr(), output.len()) };
        let value: serde_json::Value = serde_json::from_slice(&output[..count - 1]).unwrap();
        assert_eq!(value.as_object().unwrap().len(), 2);
        assert!(value.get("phase").is_some());
        assert!(value.get("error_code").is_some());
    }
    #[test]
    fn rsd_identity_and_version_are_verified_before_launch() {
        let mut h = RsdHandshake {
            services: Default::default(),
            protocol_version: 1,
            properties: [
                (
                    "UniqueDeviceID".into(),
                    plist::Value::String("SYNTHETIC-DEVICE-14".into()),
                ),
                ("OSVersion".into(), plist::Value::String("27.2".into())),
            ]
            .into(),
            uuid: "fixture".into(),
        };
        assert_eq!(validate_device(&h, "SYNTHETIC-DEVICE-14"), Ok(27));
        assert_eq!(
            validate_device(&h, "different-device"),
            Err("device_identity_mismatch")
        );
        h.properties
            .insert("OSVersion".into(), plist::Value::String("16.5".into()));
        assert_eq!(
            validate_device(&h, "SYNTHETIC-DEVICE-14"),
            Err("unsupported_ios_version")
        );
    }
    #[test]
    fn stopping_does_not_allow_a_replacement_until_teardown_finishes() {
        let _serial = TEST_LIFECYCLE.lock().unwrap();
        let (tx, mut rx) = oneshot::channel();
        {
            let mut s = session().lock().unwrap();
            s.active = true;
            s.stop = Some(tx);
        }
        ipu_self_launch_stop();
        assert_eq!(rx.try_recv(), Ok(()));
        {
            let s = session().lock().unwrap();
            assert!(s.active);
            assert_eq!(s.status.phase, "stopping");
        }
        {
            let mut s = session().lock().unwrap();
            s.active = false;
            s.status.phase = "stopped";
        }
    }
    #[test]
    fn pin_requires_an_active_human_pairing_request_and_is_used_once() {
        let _serial = TEST_LIFECYCLE.lock().unwrap();
        let pin = b"123456";
        unsafe {
            assert_eq!(ipu_self_launch_submit_pin(pin.as_ptr(), pin.len()), -1);
        }
        let (tx, mut rx) = oneshot::channel();
        {
            let mut s = session().lock().unwrap();
            s.active = true;
            s.status.phase = "awaiting_pairing_pin";
            s.pin = Some(tx);
        }
        unsafe {
            assert_eq!(ipu_self_launch_submit_pin(b"abcdef".as_ptr(), 6), -1);
            assert_eq!(ipu_self_launch_submit_pin(pin.as_ptr(), pin.len()), 0);
            assert_eq!(ipu_self_launch_submit_pin(pin.as_ptr(), pin.len()), -1);
        }
        assert_eq!(rx.try_recv().unwrap(), "123456");
        {
            let mut s = session().lock().unwrap();
            s.active = false;
            s.status.phase = "stopped";
        }
    }
    #[test]
    fn secret_record_transfer_checks_capacity_and_consumes_once() {
        let _serial = TEST_LIFECYCLE.lock().unwrap();
        session().lock().unwrap().private_record = Some(b"synthetic-secret".to_vec());
        let mut small = [0u8; 2];
        let mut output = [0u8; 64];
        unsafe {
            assert_eq!(
                ipu_self_launch_take_record(small.as_mut_ptr(), small.len()),
                16
            );
            assert_eq!(small, [0, 0]);
            assert_eq!(
                ipu_self_launch_take_record(output.as_mut_ptr(), output.len()),
                16
            );
            assert_eq!(&output[..16], b"synthetic-secret");
            assert_eq!(
                ipu_self_launch_take_record(output.as_mut_ptr(), output.len()),
                0
            );
        }
    }
    #[test]
    fn phone_generated_configuration_needs_no_mac_paths_but_cannot_skip_first_pairing() {
        let _serial = TEST_LIFECYCLE.lock().unwrap();
        let bytes = serde_json::to_vec(&serde_json::json!({
            "schema":1,"endpoint":"10.7.0.1", "runner_bundle_id":"com.leeguoo.iphone-use.runner.xctrunner",
            "runner_environment":{"IPU_RUNNER_TOKEN":"a".repeat(64),"IPU_DAEMON_TOKEN":"b".repeat(64)}
        })).unwrap();
        let config: Configuration = serde_json::from_slice(&bytes).unwrap();
        assert!(config.validate().is_ok());
        assert!(config.expected_udid.is_empty());
        let pair = RpPairingFile::generate("synthetic-pair").to_bytes();
        unsafe {
            assert_eq!(
                ipu_self_launch_start(bytes.as_ptr(), bytes.len(), pair.as_ptr(), pair.len()),
                -1
            );
        }
    }
    #[test]
    fn keychain_storage_must_be_acknowledged_once_and_failures_are_observable() {
        let _serial = TEST_LIFECYCLE.lock().unwrap();
        assert_eq!(ipu_self_launch_setup_saved(true), -1);
        let (tx, mut rx) = oneshot::channel();
        {
            let mut s = session().lock().unwrap();
            s.active = true;
            s.status.phase = "awaiting_setup_storage";
            s.setup_saved = Some(tx);
        }
        assert_eq!(ipu_self_launch_setup_saved(false), 0);
        assert_eq!(rx.try_recv(), Ok(false));
        assert_eq!(ipu_self_launch_setup_saved(true), -1);
        {
            let mut s = session().lock().unwrap();
            s.active = false;
            s.status.phase = "stopped";
        }
    }
    #[test]
    fn daemon_cannot_be_exposed_on_the_lan_by_imported_configuration() {
        let mut c = config();
        c.runner_environment
            .insert("IPU_DAEMON_HOST".into(), "0.0.0.0".into());
        assert_eq!(c.validate(), Err("nonlocal_daemon_bind"));
    }
}
