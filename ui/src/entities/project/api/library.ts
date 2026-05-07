import { invoke } from "@tauri-apps/api/core";

import type { ProjectMeta } from "../model/types";

export async function listProjects(): Promise<ProjectMeta[]> {
    return invoke<ProjectMeta[]>("list_projects");
}

export async function deleteProject(id: string): Promise<void> {
    return invoke<void>("delete_project", { id });
}
