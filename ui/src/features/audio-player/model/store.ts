import { create } from "zustand";

import * as engine from "../api/audio-engine";
import { effectiveGain } from "./solo";
import type { ChannelState, PlayerStatus, TrackMeta } from "./types";

const MEMORY_WARN_BYTES = 300 * 1024 * 1024;

interface PlayerState {
    status: PlayerStatus;
    duration: number;
    currentTime: number;
    masterVolume: number;
    channels: Record<string, ChannelState>;
    tracks: TrackMeta[];
    errorMessage: string | null;
    /** Identity of the last `tracks` dict the player loaded — used to
     *  short-circuit auto-load on re-subscribe. */
    sourceTracksId: object | null;

    load: (tracks: Record<string, string>) => Promise<void>;
    play: () => void;
    pause: () => void;
    seek: (t: number) => void;
    setChannelVolume: (name: string, v: number) => void;
    toggleMute: (name: string) => void;
    toggleSolo: (name: string) => void;
    setMasterVolume: (v: number) => void;
    unload: () => void;
}

let rafHandle: number | null = null;

function defaultChannel(): ChannelState {
    return { volume: 1, mute: false, solo: false };
}

function applyChannelGains(channels: Record<string, ChannelState>): void {
    for (const name of Object.keys(channels)) {
        engine.setChannelGain(name, effectiveGain(channels, name));
    }
}

export const usePlayerStore = create<PlayerState>((set, get) => {
    function startRaf(): void {
        if (rafHandle !== null) return;
        const tick = (): void => {
            const playing = get().status === "playing";
            if (!playing) {
                rafHandle = null;
                return;
            }
            const t = engine.getCurrentTime();
            // commit only if changed enough (avoid 60Hz spam re-renders)
            const prev = get().currentTime;
            if (Math.abs(t - prev) > 0.05) {
                set({ currentTime: t });
            }
            if (!engine.isPlaying()) {
                // natural end
                set({ status: "paused", currentTime: get().duration });
                rafHandle = null;
                return;
            }
            rafHandle = requestAnimationFrame(tick);
        };
        rafHandle = requestAnimationFrame(tick);
    }

    return {
        status: "empty",
        duration: 0,
        currentTime: 0,
        masterVolume: 1,
        channels: {},
        tracks: [],
        errorMessage: null,
        sourceTracksId: null,

        load: async (tracks) => {
            set({
                status: "loading",
                errorMessage: null,
                currentTime: 0,
                sourceTracksId: tracks,
            });
            try {
                const metas = await engine.loadTracks(tracks);
                const channels: Record<string, ChannelState> = {};
                for (const m of metas) channels[m.name] = defaultChannel();
                const totalBytes = metas.reduce(
                    (acc, m) => acc + m.bytesEstimate,
                    0,
                );
                const warning =
                    totalBytes > MEMORY_WARN_BYTES
                        ? `메모리 사용량 경고: 디코드된 PCM ~${Math.round(
                              totalBytes / (1024 * 1024),
                          )}MB`
                        : null;
                set({
                    status: "ready",
                    tracks: metas,
                    channels,
                    duration: metas.reduce(
                        (d, m) => Math.max(d, m.durationSec),
                        0,
                    ),
                    currentTime: 0,
                    errorMessage: warning,
                });
                applyChannelGains(channels);
                engine.setMasterGain(get().masterVolume);
            } catch (e) {
                const msg = e instanceof Error ? e.message : String(e);
                set({ status: "error", errorMessage: msg });
            }
        },

        play: () => {
            if (get().status === "empty" || get().status === "loading") return;
            if (get().currentTime >= get().duration && get().duration > 0) {
                engine.seek(0);
                set({ currentTime: 0 });
            }
            engine.play();
            set({ status: "playing" });
            startRaf();
        },

        pause: () => {
            engine.pause();
            set({ status: "paused", currentTime: engine.getCurrentTime() });
        },

        seek: (t) => {
            engine.seek(t);
            set({ currentTime: engine.getCurrentTime() });
        },

        setChannelVolume: (name, v) => {
            const channels = {
                ...get().channels,
                [name]: { ...get().channels[name], volume: v },
            };
            set({ channels });
            applyChannelGains(channels);
        },

        toggleMute: (name) => {
            const cur = get().channels[name];
            if (!cur) return;
            const channels = {
                ...get().channels,
                [name]: { ...cur, mute: !cur.mute },
            };
            set({ channels });
            applyChannelGains(channels);
        },

        toggleSolo: (name) => {
            // Single-solo mode (radio-button semantics): the most recently
            // soloed channel wins. Re-clicking the same channel clears it,
            // which restores normal mix.
            const cur = get().channels[name];
            if (!cur) return;
            const willSolo = !cur.solo;
            const channels: Record<string, ChannelState> = {};
            for (const [n, c] of Object.entries(get().channels)) {
                channels[n] = { ...c, solo: n === name ? willSolo : false };
            }
            set({ channels });
            applyChannelGains(channels);
        },

        setMasterVolume: (v) => {
            engine.setMasterGain(v);
            set({ masterVolume: v });
        },

        unload: () => {
            engine.unload();
            if (rafHandle !== null) {
                cancelAnimationFrame(rafHandle);
                rafHandle = null;
            }
            set({
                status: "empty",
                tracks: [],
                channels: {},
                duration: 0,
                currentTime: 0,
                errorMessage: null,
                sourceTracksId: null,
            });
        },
    };
});
