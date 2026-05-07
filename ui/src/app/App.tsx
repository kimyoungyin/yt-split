import { useEffect } from "react";

import { useAutoLoadPlayer } from "@/features/audio-player/api/auto-load";
import { Player } from "@/features/audio-player/ui/Player";
import { Library } from "@/features/library/ui/Library";
import { attachSidecarListeners } from "@/features/separate-audio/api/sidecar";
import { usePipelineStore } from "@/features/separate-audio/model/store";
import { PipelineRunner } from "@/features/separate-audio/ui/PipelineRunner";
import { useLibraryStore } from "@/features/library/model/store";

export function App() {
    // attachSidecarListeners is idempotent and lives for the lifetime of the
    // webview (cached on globalThis), so we don't return a cleanup. Returning
    // one would race with React StrictMode's double-invoked dev effect and
    // either tear down the listener prematurely or leave duplicates.
    useEffect(() => {
        void attachSidecarListeners();
    }, []);

    useAutoLoadPlayer();

    // Refresh the library whenever a pipeline run completes successfully.
    useEffect(() => {
        return usePipelineStore.subscribe((s, prev) => {
            if (s.status === "done" && prev.status !== "done") {
                void useLibraryStore.getState().refresh();
            }
        });
    }, []);

    return (
        <main className="min-h-screen bg-background text-foreground">
            <div className="mx-auto max-w-3xl space-y-4 p-6">
                <PipelineRunner />
                <Library />
                <Player />
            </div>
        </main>
    );
}
