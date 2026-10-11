use std::{
    ffi::{CStr, CString},
    path::Path,
    time::{Duration, Instant},
};
fn main() {
    let args: Vec<_> = std::env::args().collect();
    if args.len() < 3 || args[1] != "--config" {
        eprintln!("usage: ipu-phone-host --config PRIVATE_JSON [--pair-out PRIVATE_PLIST]");
        std::process::exit(2);
    }
    let path = Path::new(&args[2]);
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if std::fs::metadata(path).unwrap().permissions().mode() & 0o077 != 0 {
            eprintln!("Config must be private (chmod 600)");
            std::process::exit(2);
        }
    }
    let mut config: serde_json::Value =
        serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
    if let Some(path) = config.get("pair_record_path").and_then(|x| x.as_str()) {
        use base64::{Engine, engine::general_purpose::STANDARD};
        let bytes = std::fs::read(path).unwrap();
        config["pair_record_base64"] = STANDARD.encode(bytes).into();
    }
    let config = CString::new(config.to_string()).unwrap();
    if unsafe { ipu_phone_host::ipu_host_start(config.as_ptr()) } != 0 {
        eprintln!("Invalid config or host already active");
        std::process::exit(2);
    }
    let started = Instant::now();
    let mut previous = String::new();
    loop {
        let ptr = ipu_phone_host::ipu_host_status();
        let status = unsafe { CStr::from_ptr(ptr) }.to_str().unwrap().to_owned();
        unsafe {
            ipu_phone_host::ipu_host_string_free(ptr);
        }
        if status != previous {
            println!("{status}");
            previous = status.clone();
        }
        let value: serde_json::Value = serde_json::from_str(&status).unwrap();
        let phase = value["phase"].as_str().unwrap_or("");
        if value["pair_record_available"] == true && args.len() == 5 && args[3] == "--pair-out" {
            let length =
                unsafe { ipu_phone_host::ipu_host_copy_pair_record(std::ptr::null_mut(), 0) };
            if length > 0 && !Path::new(&args[4]).exists() {
                let mut record = vec![0u8; length as usize];
                unsafe {
                    ipu_phone_host::ipu_host_copy_pair_record(record.as_mut_ptr(), record.len());
                }
                let mut opts = std::fs::OpenOptions::new();
                opts.write(true).create_new(true);
                #[cfg(unix)]
                {
                    use std::os::unix::fs::OpenOptionsExt;
                    opts.mode(0o600);
                }
                use std::io::Write;
                opts.open(&args[4]).unwrap().write_all(&record).unwrap();
                use zeroize::Zeroize;
                record.zeroize();
            }
        }
        if phase == "rsd_verified" || phase == "runner_exited" {
            return;
        }
        if phase == "failed" || started.elapsed() > Duration::from_secs(180) && phase != "running" {
            ipu_phone_host::ipu_host_stop();
            std::process::exit(1);
        }
        std::thread::sleep(Duration::from_millis(250));
    }
}
