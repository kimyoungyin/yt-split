import { useEffect } from "react";

import { attachSidecarListeners } from "../features/separate-audio/api/sidecar";
import { PipelineRunner } from "../features/separate-audio/ui/PipelineRunner";

export function App() {
    // attachSidecarListeners is idempotent and lives for the lifetime of the
    // webview (cached on globalThis), so we don't return a cleanup. Returning
    // one would race with React StrictMode's double-invoked dev effect and
    // either tear down the listener prematurely or leave duplicates.
    useEffect(() => {
        void attachSidecarListeners();
    }, []);

    return <PipelineRunner />;
}
