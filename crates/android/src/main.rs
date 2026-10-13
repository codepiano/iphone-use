use android_use::{
    backend::{self, AndroidBackend},
    http::{self, ApiState, Session},
    mcp::{AndroidHandler, DaemonClient},
};
use clap::{Parser, Subcommand};
use rmcp::{transport::stdio, ServiceExt};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{fs::OpenOptions, path::PathBuf, sync::Arc};
use tokio::sync::Mutex;

#[derive(Parser)]
#[command(
    name = "android-use",
    version,
    about = "Android control for agents, sharing the iphone-use control core"
)]
struct Cli {
    #[arg(long, global = true)]
    url: Option<String>,
    #[arg(long, global = true, default_value = "cli")]
    owner: String,
    #[command(subcommand)]
    command: Commands,
}
#[derive(Subcommand)]
enum Commands {
    /// Download and verify the pinned UIAutomator runner (no Python required).
    Setup,
    /// Serve one explicitly selected, authorized Android over loopback HTTP.
    Serve {
        #[arg(long)]
        serial: String,
        #[arg(long, default_value_t = 44322)]
        port: u16,
        #[arg(long)]
        runner_jar: Option<PathBuf>,
    },
    Status,
    Capabilities,
    Elements {
        #[arg(long)]
        since: Option<String>,
    },
    /// Execute one action JSON or a batch JSON containing steps.
    Act {
        json: String,
    },
    Screenshot {
        output: PathBuf,
    },
    Release,
    /// MCP stdio server; stdout is reserved for protocol messages.
    Mcp,
}
#[derive(Serialize, Deserialize)]
struct Connection {
    url: String,
    token: String,
}
fn config_path() -> anyhow::Result<PathBuf> {
    Ok(backend::data_dir()?.join("connection.json"))
}
fn save_connection(connection: &Connection) -> anyhow::Result<()> {
    let path = config_path()?;
    let temp = path.with_extension(format!("{}.tmp", std::process::id()));
    let mut options = OpenOptions::new();
    options.create_new(true).write(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    use std::io::Write;
    let mut file = options.open(&temp)?;
    file.write_all(&serde_json::to_vec(connection)?)?;
    file.sync_all()?;
    std::fs::rename(&temp, path)?;
    Ok(())
}
fn connection(url: Option<String>) -> anyhow::Result<Connection> {
    let saved = std::fs::read(config_path()?)
        .ok()
        .and_then(|b| serde_json::from_slice::<Connection>(&b).ok());
    let token = std::env::var("ANDROID_USE_TOKEN").ok();
    match (url, token, saved) {
        (Some(url), Some(token), _) => Ok(Connection { url, token }),
        (Some(url), None, Some(saved)) if url == saved.url => Ok(saved),
        (None, token, Some(mut saved)) => {
            if let Some(token) = token {
                saved.token = token;
            }
            Ok(saved)
        }
        _ => anyhow::bail!("Start android-use serve, or specify --url and ANDROID_USE_TOKEN"),
    }
}
fn print_result(value: Value) -> anyhow::Result<()> {
    println!("{}", serde_json::to_string(&value)?);
    if value.get("ok") == Some(&json!(false)) {
        std::process::exit(1);
    }
    Ok(())
}
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Setup => {
            let path = backend::setup_runner().await?;
            println!(
                "{}",
                json!({"ok":true,"runner":path,"sha256":backend::RUNNER_SHA256,"requires":"adb and an Android with authorized USB debugging"})
            );
        }
        Commands::Serve {
            serial,
            port,
            runner_jar,
        } => {
            if serial.is_empty() || serial.len() > 255 || serial.chars().any(char::is_control) {
                anyhow::bail!("Invalid Android serial");
            }
            let dir = backend::data_dir()?;
            std::fs::create_dir_all(dir.join("locks"))?;
            let lock_path = dir
                .join("locks")
                .join(format!("{:x}.lock", Sha256::digest(serial.as_bytes())));
            let lock = OpenOptions::new()
                .read(true)
                .write(true)
                .create(true)
                .truncate(false)
                .open(lock_path)?;
            fs2::FileExt::try_lock_exclusive(&lock)
                .map_err(|_| anyhow::anyhow!("Another android-use daemon owns this device"))?;
            let listener =
                tokio::net::TcpListener::bind((std::net::Ipv4Addr::LOCALHOST, port)).await?;
            let url = format!("http://{}", listener.local_addr()?);
            let jar = match runner_jar {
                Some(path) => path,
                None => backend::setup_runner().await?,
            };
            let device = AndroidBackend::connect(serial, &jar)
                .await
                .map_err(|e| anyhow::anyhow!("{}: {}", e.error, e.message))?;
            let mut random = [0u8; 32];
            getrandom::fill(&mut random)
                .map_err(|_| anyhow::anyhow!("Random source unavailable"))?;
            use base64::Engine as _;
            let token = base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(random);
            save_connection(&Connection {
                url: url.clone(),
                token: token.clone(),
            })?;
            let session = Arc::new(Mutex::new(Session::new(device)));
            let stopping = session.lock().await.control.stopping.clone();
            eprintln!("android-use listening at {url}; connection credentials saved privately");
            let api = http::router(ApiState::new(session.clone(), token));
            let served = axum::serve(listener, api)
                .with_graceful_shutdown(async move {
                    let _ = tokio::signal::ctrl_c().await;
                    stopping.store(true, std::sync::atomic::Ordering::Release);
                })
                .await;
            session.lock().await.control.backend.close().await;
            served?;
        }
        command => {
            let connection = connection(cli.url)?;
            let owner = if matches!(command, Commands::Mcp) {
                format!("mcp-{}", std::process::id())
            } else {
                cli.owner
            };
            let client = DaemonClient::new(connection.url, connection.token, owner)?;
            match command {
                Commands::Status => print_result(client.request("/agent/status", None).await)?,
                Commands::Capabilities => {
                    print_result(client.request("/agent/capabilities", None).await)?
                }
                Commands::Elements { since } => {
                    let path = if let Some(id) = since {
                        if !id
                            .bytes()
                            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
                        {
                            anyhow::bail!("Invalid snapshot token");
                        }
                        format!("/agent/elements?since={id}")
                    } else {
                        "/agent/elements".into()
                    };
                    print_result(client.request(&path, None).await)?;
                }
                Commands::Act { json: text } => {
                    let value: Value = serde_json::from_str(&text)?;
                    let path = if value.get("steps").is_some() {
                        "/agent/actions"
                    } else {
                        "/agent/input"
                    };
                    print_result(client.request(path, Some(value)).await)?;
                }
                Commands::Screenshot { output } => {
                    let bytes = client.screenshot().await.map_err(|e| anyhow::anyhow!(e))?;
                    tokio::fs::write(&output, bytes).await?;
                    println!("{}", json!({"ok":true,"path":output}));
                }
                Commands::Release => {
                    print_result(client.request("/agent/release", Some(json!({}))).await)?
                }
                Commands::Mcp => {
                    let service = AndroidHandler::new(client.clone()).serve(stdio()).await?;
                    let waited = service.waiting().await;
                    let _ = client.request("/agent/release", Some(json!({}))).await;
                    waited?;
                }
                Commands::Setup | Commands::Serve { .. } => unreachable!(),
            }
        }
    }
    Ok(())
}
