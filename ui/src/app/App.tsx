import { useEffect } from "react";

import { attachSidecarListeners } from "../features/separate-audio/api/sidecar";
import { PipelineRunner } from "../features/separate-audio/ui/PipelineRunner";

export function App() {
    useEffect(() => {
        let detach: (() => void) | undefined;
        attachSidecarListeners().then((off) => {
            detach = off;
        });
        return () => detach?.();
    }, []);

    return <PipelineRunner />;
}
