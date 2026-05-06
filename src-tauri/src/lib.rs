mod sidecar;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(sidecar::PipelineState::new())
        .invoke_handler(tauri::generate_handler![
            sidecar::run_pipeline,
            sidecar::cancel_pipeline
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
