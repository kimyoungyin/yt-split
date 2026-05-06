import { useEffect } from "react";

import { usePipelineStore } from "@/features/separate-audio/model/store";
import { usePlayerStore } from "../model/store";

/**
 * Watches the pipeline store; when a `done` event delivers a non-empty
 * `tracks` dict, hand it off to the player. Identity check on the dict
 * prevents re-loading the same payload after subscriber re-renders.
 */
export function useAutoLoadPlayer(): void {
    useEffect(() => {
        const tryLoad = (
            tracks: Record<string, string>,
            status: string,
        ): void => {
            if (status !== "done") return;
            if (Object.keys(tracks).length === 0) return;
            const player = usePlayerStore.getState();
            if (player.sourceTracksId === tracks) return;
            void player.load(tracks);
        };

        // initial check (in case pipeline finished before App mounted)
        const init = usePipelineStore.getState();
        tryLoad(init.tracks, init.status);

        return usePipelineStore.subscribe((s, prev) => {
            if (s.tracks === prev.tracks && s.status === prev.status) return;
            tryLoad(s.tracks, s.status);
        });
    }, []);
}
