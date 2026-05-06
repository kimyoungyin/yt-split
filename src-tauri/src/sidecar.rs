//! Spawn the PyInstaller-built sidecar and stream its NDJSON stdout to the
//! frontend as Tauri events.
//!
//! The sidecar emits one JSON object per line on stdout when invoked with
//! `--sidecar`; we forward each line as a `yt-split:event` payload. Stderr is
//! forwarded as `yt-split:log` for debugging. Process exit code is reported as
//! `yt-split:done`.

use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Mutex;

use serde::Deserialize;
use tauri::{AppHandle, Emitter, State};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command;

const EVENT_DATA: &str = "yt-split:event";
const EVENT_LOG: &str = "yt-split:log";
const EVENT_DONE: &str = "yt-split:done";

#[derive(Debug, Deserialize)]
pub struct PipelineArgs {
    pub url: String,
    pub stem: Option<String>,
}

/// Tracks the OS pid of the running sidecar so `cancel_pipeline` can signal it
/// without taking the Child's exclusive borrow away from the wait loop.
#[derive(Default)]
pub struct PipelineState {
    pid: Mutex<Option<u32>>,
}

impl PipelineState {
    pub fn new() -> Self {
        Self::default()
    }
}

/// Compile-time target triple suffix for the staged sidecar folder name.
/// Phase 1 only verifies the dev path; production bundling is a follow-up.
fn target_triple() -> &'static str {
    #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
    {
        "aarch64-apple-darwin"
    }
    #[cfg(all(target_os = "macos", target_arch = "x86_64"))]
    {
        "x86_64-apple-darwin"
    }
    #[cfg(all(target_os = "linux", target_arch = "x86_64"))]
    {
        "x86_64-unknown-linux-gnu"
    }
    #[cfg(all(target_os = "linux", target_arch = "aarch64"))]
    {
        "aarch64-unknown-linux-gnu"
    }
    #[cfg(target_os = "windows")]
    {
        "x86_64-pc-windows-msvc"
    }
}

fn sidecar_executable_name() -> &'static str {
    if cfg!(target_os = "windows") {
        "yt-split-py.exe"
    } else {
        "yt-split-py"
    }
}

/// dev-mode resolver: the sidecar lives under src-tauri/binaries/<triple>/.
fn sidecar_path() -> PathBuf {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    PathBuf::from(manifest_dir)
        .join("binaries")
        .join(format!("yt-split-py-{}", target_triple()))
        .join(sidecar_executable_name())
}

#[tauri::command]
pub async fn run_pipeline(
    app: AppHandle,
    state: State<'_, PipelineState>,
    args: PipelineArgs,
) -> Result<(), String> {
    let bin = sidecar_path();
    if !bin.exists() {
        return Err(format!(
            "사이드카 바이너리를 찾을 수 없습니다: {}\n먼저 `pyinstaller/build.sh`를 실행하세요.",
            bin.display()
        ));
    }

    let mut cmd_args: Vec<String> = vec!["--url".into(), args.url, "--sidecar".into()];
    if let Some(stem) = args.stem {
        cmd_args.push("--stem".into());
        cmd_args.push(stem);
    }

    // Pin the sidecar's working directory to the project root so the Python
    // side writes downloads/ and output/ next to the repo, not under src-tauri/
    // where Tauri dev happens to spawn us. Phase 1: dev path; production will
    // switch to AppLocalData via tauri::path::PathResolver.
    let workspace_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from("."));

    let mut child = Command::new(&bin)
        .args(&cmd_args)
        .current_dir(&workspace_root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("사이드카 spawn 실패: {e}"))?;

    if let Some(pid) = child.id() {
        if let Ok(mut guard) = state.pid.lock() {
            *guard = Some(pid);
        }
    }

    let stdout = child.stdout.take().expect("stdout piped");
    let stderr = child.stderr.take().expect("stderr piped");

    let app_for_stdout = app.clone();
    let stdout_task = tokio::spawn(async move {
        let mut reader = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            match serde_json::from_str::<serde_json::Value>(&line) {
                Ok(value) => {
                    let _ = app_for_stdout.emit(EVENT_DATA, value);
                }
                Err(_) => {
                    // Non-JSON line on stdout (shouldn't happen in --sidecar
                    // mode); forward as a log so we can still see it.
                    let _ = app_for_stdout.emit(EVENT_LOG, line);
                }
            }
        }
    });

    let app_for_stderr = app.clone();
    let stderr_task = tokio::spawn(async move {
        let mut reader = BufReader::new(stderr).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            let _ = app_for_stderr.emit(EVENT_LOG, line);
        }
    });

    let wait_result = child.wait().await;
    if let Ok(mut guard) = state.pid.lock() {
        *guard = None;
    }
    let status = wait_result.map_err(|e| format!("사이드카 wait 실패: {e}"))?;
    let _ = stdout_task.await;
    let _ = stderr_task.await;

    let _ = app.emit(EVENT_DONE, status.code().unwrap_or(-1));

    if status.success() {
        Ok(())
    } else {
        Err(format!("사이드카 종료 코드: {:?}", status.code()))
    }
}

#[tauri::command]
pub async fn cancel_pipeline(state: State<'_, PipelineState>) -> Result<(), String> {
    let pid = state
        .pid
        .lock()
        .map_err(|e| format!("state lock poisoned: {e}"))?
        .clone();
    let Some(pid) = pid else {
        // No active sidecar; treat as a no-op so the UI can call this freely.
        return Ok(());
    };

    #[cfg(unix)]
    {
        // SIGTERM lets the Python handler emit a final "cancelled" event before
        // exiting. SIGKILL would leave the UI without context for the abort.
        let rc = unsafe { libc::kill(pid as i32, libc::SIGTERM) };
        if rc != 0 {
            let err = std::io::Error::last_os_error();
            return Err(format!("kill({pid}, SIGTERM) failed: {err}"));
        }
        Ok(())
    }

    #[cfg(windows)]
    {
        let _ = pid;
        Err("Windows에서의 사이드카 취소는 Phase 4 패키징 단계에서 추가 예정".into())
    }
}
