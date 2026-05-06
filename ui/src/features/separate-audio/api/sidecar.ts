import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import type { SidecarEvent } from "../model/events";
import { usePipelineStore } from "../model/store";

const EVENT_DATA = "yt-split:event";
const EVENT_LOG = "yt-split:log";
const EVENT_DONE = "yt-split:done";

// Listener registration must survive both React StrictMode's double-invoked
// useEffect (dev) and Vite HMR module re-evaluations. A module-level guard is
// reset on HMR; storing the promise on globalThis keeps it alive for the
// lifetime of the webview, which is exactly what we want — the sidecar
// channel is global state, not component state.
//
// Refs:
// - Tauri Discussion #5194 (avoid duplicate listeners)
// - React Issue #24502 (StrictMode double-invokes useEffect in dev)
declare global {
    // eslint-disable-next-line no-var
    var __ytSplitSidecarAttach: Promise<void> | undefined;
}

function doAttach(): Promise<void> {
    const store = usePipelineStore.getState();
    return Promise.all([
        listen<SidecarEvent>(EVENT_DATA, (e) => store.handleEvent(e.payload)),
        listen<string>(EVENT_LOG, (e) => store.appendLog(e.payload)),
        listen<number>(EVENT_DONE, (e) => store.finishWithCode(e.payload)),
    ]).then(() => undefined);
}

export function attachSidecarListeners(): Promise<void> {
    if (globalThis.__ytSplitSidecarAttach) {
        return globalThis.__ytSplitSidecarAttach;
    }
    globalThis.__ytSplitSidecarAttach = doAttach();
    return globalThis.__ytSplitSidecarAttach;
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

/** Send SIGTERM to the running sidecar (no-op when nothing is running). */
export async function cancelPipeline(): Promise<void> {
    await invoke("cancel_pipeline");
}
