export type PlayerStatus =
    | "empty"
    | "loading"
    | "ready"
    | "playing"
    | "paused"
    | "error";

export interface ChannelState {
    volume: number; // 0..1
    mute: boolean;
    solo: boolean;
}

export interface TrackMeta {
    name: string;
    path: string;
    durationSec: number;
    sampleRate: number;
    bytesEstimate: number; // raw float32 in memory
}
