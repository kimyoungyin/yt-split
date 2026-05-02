import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

import type { SidecarEvent } from "../model/events";
import { usePipelineStore } from "../model/store";

const EVENT_DATA = "yt-split:event";
const EVENT_LOG = "yt-split:log";
const EVENT_DONE = "yt-split:done";

let unlisteners: UnlistenFn[] = [];

/** Subscribe to sidecar events once on app mount. */
export async function attachSidecarListeners(): Promise<UnlistenFn> {
    const store = usePipelineStore.getState();

    const offData = await listen<SidecarEvent>(EVENT_DATA, (e) => {
        store.handleEvent(e.payload);
    });
    const offLog = await listen<string>(EVENT_LOG, (e) => {
        store.appendLog(e.payload);
    });
    const offDone = await listen<number>(EVENT_DONE, (e) => {
        store.finishWithCode(e.payload);
    });

    unlisteners = [offData, offLog, offDone];

    return () => {
        for (const u of unlisteners) u();
        unlisteners = [];
    };
}

/** Kick off a separation pipeline run. Resolves when the sidecar exits. */
export async function runPipeline(args: {
    url: string;
    stem?: string | null;
}): Promise<void> {
    usePipelineStore.getState().start();
    await invoke("run_pipeline", {
        args: { url: args.url, stem: args.stem ?? null },
    });
}
