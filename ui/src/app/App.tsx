import { useEffect } from "react";

import { useAutoLoadPlayer } from "@/features/audio-player/api/auto-load";
import { Player } from "@/features/audio-player/ui/Player";
import { attachSidecarListeners } from "@/features/separate-audio/api/sidecar";
import { PipelineRunner } from "@/features/separate-audio/ui/PipelineRunner";

export function App() {
    // attachSidecarListeners is idempotent and lives for the lifetime of the
    // webview (cached on globalThis), so we don't return a cleanup. Returning
    // one would race with React StrictMode's double-invoked dev effect and
    // either tear down the listener prematurely or leave duplicates.
    useEffect(() => {
        void attachSidecarListeners();
    }, []);

    useAutoLoadPlayer();

    return (
        <main className="min-h-screen bg-background text-foreground">
            <div className="mx-auto max-w-3xl space-y-4 p-6">
                <PipelineRunner />
                <Player />
            </div>
        </main>
    );
}
