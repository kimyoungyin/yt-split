//! Tauri commands for reading and deleting project library entries.

use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

#[derive(Debug, Serialize, Deserialize)]
pub struct ProjectMeta {
    pub schema_version: u32,
    pub id: String,
    pub title: String,
    pub url: String,
    pub created_at: String,
    pub device: String,
    pub stem_mode: String,
    /// Relative paths on disk; resolved to absolute before returning to frontend.
    pub tracks: std::collections::HashMap<String, String>,
}

fn yt_split_base(app: &AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_local_data_dir()
        .map(|p| p.join("yt-split"))
        .map_err(|e| format!("AppLocalData 경로 조회 실패: {e}"))
}

#[tauri::command]
pub fn list_projects(app: AppHandle) -> Result<Vec<ProjectMeta>, String> {
    let base = yt_split_base(&app)?;
    let projects_dir = base.join("projects");

    if !projects_dir.is_dir() {
        return Ok(vec![]);
    }

    let mut results: Vec<ProjectMeta> = Vec::new();

    let entries = std::fs::read_dir(&projects_dir)
        .map_err(|e| format!("projects 디렉터리 읽기 실패: {e}"))?;

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let Ok(text) = std::fs::read_to_string(&path) else {
            continue;
        };
        let Ok(mut meta) = serde_json::from_str::<ProjectMeta>(&text) else {
            continue;
        };
        if meta.schema_version != 1 {
            continue;
        }

        // Resolve relative track paths to absolute paths.
        let project_dir = projects_dir.join(&meta.id);
        let mut resolved: std::collections::HashMap<String, String> =
            std::collections::HashMap::new();
        for (stem, rel) in &meta.tracks {
            let abs = project_dir.join(rel);
            if abs.exists() {
                resolved.insert(stem.clone(), abs.to_string_lossy().into_owned());
            }
        }
        meta.tracks = resolved;
        results.push(meta);
    }

    results.sort_by(|a, b| b.created_at.cmp(&a.created_at));
    Ok(results)
}

#[tauri::command]
pub fn delete_project(app: AppHandle, id: String) -> Result<(), String> {
    let base = yt_split_base(&app)?;

    // Reject path traversal.
    if id.contains('/') || id.contains('\\') || id.contains("..") {
        return Err(format!("잘못된 프로젝트 ID: {id}"));
    }

    let meta_path = base.join("projects").join(format!("{id}.json"));
    let project_dir = base.join("projects").join(&id);

    if meta_path.exists() {
        std::fs::remove_file(&meta_path)
            .map_err(|e| format!("메타 파일 삭제 실패: {e}"))?;
    }
    if project_dir.is_dir() {
        std::fs::remove_dir_all(&project_dir)
            .map_err(|e| format!("프로젝트 디렉터리 삭제 실패: {e}"))?;
    }

    Ok(())
}
