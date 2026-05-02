/**
 * NDJSON event payloads emitted by the Python sidecar on stdout.
 *
 * Keep this file in sync with src/features/progress.py and the call sites
 * inside src/app/main.py / src/features/{download,separation}.py.
 */
export type Stage = "download" | "separate" | "system" | "pipeline";

export interface HardwareEvent {
    type: "hardware";
    cuda_available: boolean;
    mps_available: boolean;
    demucs_device: "cuda" | "mps" | "cpu";
    ram_gb: number;
    vram_gb: number;
    free_space_gb: number;
    can_run: boolean;
    warning: string;
}

export interface StageStartEvent {
    type: "stage";
    status: "start";
    stage: Stage;
    url?: string;
    model?: string;
    device?: string;
}

export interface StageDoneEvent {
    type: "stage";
    status: "done";
    stage: Stage;
    path?: string;
    tracks?: Record<string, string>;
}

export interface ProgressEvent {
    type: "progress";
    stage: Stage;
    value: number;
}

export interface ErrorEvent {
    type: "error";
    stage?: Stage;
    message: string;
}

export interface DoneEvent {
    type: "done";
    ok: boolean;
}

export type SidecarEvent =
    | HardwareEvent
    | StageStartEvent
    | StageDoneEvent
    | ProgressEvent
    | ErrorEvent
    | DoneEvent;
