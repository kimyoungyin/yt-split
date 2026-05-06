import { convertFileSrc } from "@tauri-apps/api/core";

import type { TrackMeta } from "../model/types";

interface LoadedTrack {
    name: string;
    path: string;
    buffer: AudioBuffer;
    gain: GainNode;
}

interface EngineState {
    ctx: AudioContext;
    masterGain: GainNode;
    loaded: Map<string, LoadedTrack>;
    activeSources: Map<string, AudioBufferSourceNode>;
    startedAtCtxTime: number;
    offsetAtStart: number;
    duration: number;
    playing: boolean;
    onEnded: (() => void) | null;
}

let state: EngineState | null = null;

function ensureCtx(): AudioContext {
    if (state) return state.ctx;
    const ctx = new AudioContext({ latencyHint: "interactive" });
    const masterGain = ctx.createGain();
    masterGain.gain.value = 1;
    masterGain.connect(ctx.destination);
    state = {
        ctx,
        masterGain,
        loaded: new Map(),
        activeSources: new Map(),
        startedAtCtxTime: 0,
        offsetAtStart: 0,
        duration: 0,
        playing: false,
        onEnded: null,
    };
    return ctx;
}

function stopAllSources(): void {
    if (!state) return;
    state.activeSources.forEach((src) => {
        try {
            src.onended = null;
            src.stop();
        } catch {
            // already stopped
        }
        src.disconnect();
    });
    state.activeSources.clear();
}

export async function loadTracks(
    tracks: Record<string, string>,
): Promise<TrackMeta[]> {
    unload();
    const ctx = ensureCtx();
    const entries = Object.entries(tracks);
    const decoded = await Promise.all(
        entries.map(async ([name, path]) => {
            const url = convertFileSrc(path);
            const res = await fetch(url);
            if (!res.ok) {
                throw new Error(
                    `failed to fetch ${name} (${res.status} ${res.statusText})`,
                );
            }
            const buf = await res.arrayBuffer();
            const audioBuffer = await ctx.decodeAudioData(buf);
            return { name, path, audioBuffer };
        }),
    );

    if (!state) throw new Error("engine state lost during decode");

    const sampleRate = decoded[0]?.audioBuffer.sampleRate ?? ctx.sampleRate;
    const metas: TrackMeta[] = [];
    for (const { name, path, audioBuffer } of decoded) {
        if (audioBuffer.sampleRate !== sampleRate) {
            console.warn(
                `[audio-engine] sampleRate mismatch on ${name}: ${audioBuffer.sampleRate} vs ${sampleRate}`,
            );
        }
        const gain = ctx.createGain();
        gain.gain.value = 1;
        gain.connect(state.masterGain);
        state.loaded.set(name, { name, path, buffer: audioBuffer, gain });
        metas.push({
            name,
            path,
            durationSec: audioBuffer.duration,
            sampleRate: audioBuffer.sampleRate,
            bytesEstimate:
                audioBuffer.length *
                audioBuffer.numberOfChannels *
                4 /* float32 */,
        });
    }
    state.duration = Math.max(...metas.map((m) => m.durationSec), 0);
    state.offsetAtStart = 0;
    state.playing = false;
    return metas;
}

export function play(onEnded?: () => void): void {
    if (!state) return;
    if (state.loaded.size === 0) return;
    if (state.playing) return;

    if (state.ctx.state === "suspended") {
        // user gesture lifts WKWebView's autoplay block; resume is fire-and-forget.
        void state.ctx.resume();
    }

    const s = state;
    const when = s.ctx.currentTime + 0.05;
    let endedFired = false;

    s.loaded.forEach((track) => {
        const src = s.ctx.createBufferSource();
        src.buffer = track.buffer;
        src.connect(track.gain);
        src.onended = () => {
            // natural end: only the first source to end triggers store sync.
            // pause()/seek() clear src.onended before stop(), so this only fires
            // when the buffer plays through to its end.
            if (endedFired || !state || !state.playing) return;
            endedFired = true;
            state.playing = false;
            state.offsetAtStart = state.duration;
            onEnded?.();
        };
        src.start(when, s.offsetAtStart);
        s.activeSources.set(track.name, src);
    });

    s.startedAtCtxTime = when;
    s.playing = true;
    s.onEnded = onEnded ?? null;
}

export function pause(): void {
    if (!state || !state.playing) return;
    const at = getCurrentTime();
    state.playing = false;
    stopAllSources();
    state.offsetAtStart = Math.min(at, state.duration);
}

export function seek(seconds: number): void {
    if (!state) return;
    const clamped = Math.max(0, Math.min(seconds, state.duration));
    const wasPlaying = state.playing;
    if (wasPlaying) {
        state.playing = false;
        stopAllSources();
    }
    state.offsetAtStart = clamped;
    if (wasPlaying) play(state.onEnded ?? undefined);
}

export function setChannelGain(name: string, gain: number): void {
    if (!state) return;
    const t = state.loaded.get(name);
    if (!t) return;
    t.gain.gain.value = Math.max(0, gain);
}

export function setMasterGain(gain: number): void {
    if (!state) return;
    state.masterGain.gain.value = Math.max(0, gain);
}

export function getCurrentTime(): number {
    if (!state) return 0;
    if (!state.playing) return state.offsetAtStart;
    const elapsed = state.ctx.currentTime - state.startedAtCtxTime;
    const t = state.offsetAtStart + Math.max(0, elapsed);
    return Math.min(t, state.duration);
}

export function getDuration(): number {
    return state?.duration ?? 0;
}

export function isPlaying(): boolean {
    return state?.playing ?? false;
}

export function unload(): void {
    if (!state) return;
    stopAllSources();
    state.loaded.forEach((t) => t.gain.disconnect());
    state.loaded.clear();
    state.duration = 0;
    state.offsetAtStart = 0;
    state.playing = false;
    state.onEnded = null;
}
