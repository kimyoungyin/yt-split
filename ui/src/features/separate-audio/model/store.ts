import { create } from "zustand";
import type { HardwareEvent, SidecarEvent, Stage } from "./events";

export type PipelineStatus = "idle" | "running" | "done" | "error";

interface PipelineState {
    status: PipelineStatus;
    hardware: HardwareEvent | null;
    currentStage: Stage | null;
    progress: number; // 0..1 for the current stage
    tracks: Record<string, string>;
    errorMessage: string | null;
    logs: string[];
    reset: () => void;
    start: () => void;
    handleEvent: (e: SidecarEvent) => void;
    appendLog: (line: string) => void;
    finishWithCode: (code: number) => void;
}

const MAX_LOGS = 200;

export const usePipelineStore = create<PipelineState>((set) => ({
    status: "idle",
    hardware: null,
    currentStage: null,
    progress: 0,
    tracks: {},
    errorMessage: null,
    logs: [],

    reset: () =>
        set({
            status: "idle",
            currentStage: null,
            progress: 0,
            tracks: {},
            errorMessage: null,
            logs: [],
        }),

    start: () =>
        set({
            status: "running",
            currentStage: null,
            progress: 0,
            tracks: {},
            errorMessage: null,
            logs: [],
        }),

    handleEvent: (e) =>
        set((s) => {
            switch (e.type) {
                case "hardware":
                    return { hardware: e };
                case "stage":
                    if (e.status === "start") {
                        return { currentStage: e.stage, progress: 0 };
                    }
                    // status === "done"
                    return {
                        currentStage: e.stage,
                        progress: 1,
                        tracks: e.tracks
                            ? { ...s.tracks, ...e.tracks }
                            : s.tracks,
                    };
                case "progress":
                    return { currentStage: e.stage, progress: e.value };
                case "error":
                    return { status: "error", errorMessage: e.message };
                case "done":
                    return { status: e.ok ? "done" : "error" };
                default:
                    return {};
            }
        }),

    appendLog: (line) =>
        set((s) => ({
            logs:
                s.logs.length >= MAX_LOGS
                    ? [...s.logs.slice(s.logs.length - MAX_LOGS + 1), line]
                    : [...s.logs, line],
        })),

    finishWithCode: (code) =>
        set((s) => {
            if (s.status === "running") {
                return code === 0
                    ? { status: "done" }
                    : {
                          status: "error",
                          errorMessage: `사이드카 종료 코드: ${code}`,
                      };
            }
            return {};
        }),
}));
