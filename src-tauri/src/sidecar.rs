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
use tauri::{AppHandle, Emitter, Manager, State};
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

/// Returns the sidecar binary directory given a resource_dir root (prod path).
/// Extracted as a pure function so it can be unit-tested without an AppHandle.
pub(crate) fn sidecar_binary_dir_from_resource(res: &std::path::Path) -> PathBuf {
    res.join("binaries")
        .join(format!("yt-split-py-{}", target_triple()))
}

/// dev-mode resolver: the sidecar lives under src-tauri/binaries/<triple>/.
fn sidecar_path() -> PathBuf {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    sidecar_binary_dir_from_resource(&PathBuf::from(manifest_dir))
        .join(sidecar_executable_name())
}

#[tauri::command]
pub async fn run_pipeline(
    app: AppHandle,
    state: State<'_, PipelineState>,
    args: PipelineArgs,
) -> Result<(), String> {
    let bin = if cfg!(debug_assertions) {
        sidecar_path()
    } else {
        let res = app
            .path()
            .resource_dir()
            .map_err(|e| format!("resource_dir 조회 실패: {e}"))?;
        sidecar_binary_dir_from_resource(&res).join(sidecar_executable_name())
    };
    if !bin.exists() {
        return Err(format!(
            "사이드카 바이너리를 찾을 수 없습니다: {}\n먼저 `pyinstaller/build.sh`를 실행하세요.",
            bin.display()
        ));
    }

    // Busy check: reject if a pipeline is already running.
    {
        let guard = state.pid.lock().map_err(|e| format!("state lock poisoned: {e}"))?;
        if guard.is_some() {
            return Err("이미 파이프라인이 실행 중입니다.".into());
        }
    }

    // Resolve AppLocalData base directory and pass it to the sidecar via --workdir.
    let base_dir = app
        .path()
        .app_local_data_dir()
        .map_err(|e| format!("AppLocalData 경로 조회 실패: {e}"))?
        .join("yt-split");
    std::fs::create_dir_all(&base_dir)
        .map_err(|e| format!("workdir 생성 실패: {e}"))?;

    let mut cmd_args: Vec<String> = vec![
        "--url".into(), args.url,
        "--sidecar".into(),
        "--workdir".into(), base_dir.to_string_lossy().into_owned(),
    ];
    if let Some(stem) = args.stem {
        cmd_args.push("--stem".into());
        cmd_args.push(stem);
    }

    let mut cmd = Command::new(&bin);
    cmd.args(&cmd_args).stdout(Stdio::piped()).stderr(Stdio::piped());

    // Windows: launch in a new process group so GenerateConsoleCtrlEvent can
    // target the sidecar without affecting the Tauri host process.
    #[cfg(windows)]
    {
        const CREATE_NEW_PROCESS_GROUP: u32 = 0x00000200;
        cmd.creation_flags(CREATE_NEW_PROCESS_GROUP);
    }

    let mut child = cmd
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
    cancel_windows(pid).await
}

#[cfg(windows)]
async fn cancel_windows(pid: u32) -> Result<(), String> {
    // WaitForSingleObject(5000) blocks for up to 5 s — run on a dedicated
    // blocking thread so the tokio async runtime is not stalled.
    tokio::task::spawn_blocking(move || {
        use windows_sys::Win32::Foundation::CloseHandle;
        use windows_sys::Win32::System::Console::GenerateConsoleCtrlEvent;
        use windows_sys::Win32::System::Threading::{
            OpenProcess, TerminateProcess, WaitForSingleObject, PROCESS_SYNCHRONIZE,
            PROCESS_TERMINATE,
        };

        unsafe {
            // 1. Ctrl+C to the process group (pgid == pid for CREATE_NEW_PROCESS_GROUP).
            GenerateConsoleCtrlEvent(0 /* CTRL_C_EVENT */, pid);

            // 2. Wait up to 5 s for graceful exit.
            // PROCESS_SYNCHRONIZE is required by WaitForSingleObject;
            // PROCESS_TERMINATE is required by TerminateProcess.
            let handle = OpenProcess(PROCESS_TERMINATE | PROCESS_SYNCHRONIZE, 0, pid);
            if handle == 0 {
                // Process already gone — treat as success.
                return Ok(());
            }
            let wait = WaitForSingleObject(handle, 5000);
            if wait != 0 {
                // 3. Still alive — force terminate.
                TerminateProcess(handle, 1);
            }
            CloseHandle(handle);
        }
        Ok(())
    })
    .await
    .map_err(|e| format!("spawn_blocking join error: {e}"))?
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf; 

    #[test]
    fn sidecar_binary_dir_prod_uses_resource_subpath() {
        let resource_dir = PathBuf::from("/fake/resources");
        let dir = sidecar_binary_dir_from_resource(&resource_dir);
        assert_eq!(
            dir,
            PathBuf::from("/fake/resources")
                .join("binaries")
                .join(format!("yt-split-py-{}", target_triple()))
        );
    }
}
