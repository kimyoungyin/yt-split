import { describe, expect, it } from "vitest";

import { effectiveGain } from "./solo";
import type { ChannelState } from "./types";

function ch(volume: number, mute = false, solo = false): ChannelState {
    return { volume, mute, solo };
}

describe("effectiveGain", () => {
    it("passes volume through when nothing is muted or soloed", () => {
        const channels = { vocals: ch(0.7), drums: ch(0.5) };
        expect(effectiveGain(channels, "vocals")).toBe(0.7);
        expect(effectiveGain(channels, "drums")).toBe(0.5);
    });

    it("returns 0 for a muted channel", () => {
        const channels = { vocals: ch(0.9, true), drums: ch(0.5) };
        expect(effectiveGain(channels, "vocals")).toBe(0);
        expect(effectiveGain(channels, "drums")).toBe(0.5);
    });

    it("a single solo silences every other channel", () => {
        const channels = {
            vocals: ch(0.8, false, true),
            drums: ch(0.5),
            bass: ch(0.6),
        };
        expect(effectiveGain(channels, "vocals")).toBe(0.8);
        expect(effectiveGain(channels, "drums")).toBe(0);
        expect(effectiveGain(channels, "bass")).toBe(0);
    });

    it("multi-solo is OR — every soloed channel passes", () => {
        const channels = {
            vocals: ch(0.7, false, true),
            drums: ch(0.5, false, true),
            bass: ch(0.6),
            other: ch(0.4),
        };
        expect(effectiveGain(channels, "vocals")).toBe(0.7);
        expect(effectiveGain(channels, "drums")).toBe(0.5);
        expect(effectiveGain(channels, "bass")).toBe(0);
        expect(effectiveGain(channels, "other")).toBe(0);
    });

    it("mute always wins over solo", () => {
        const channels = { vocals: ch(0.9, true, true), drums: ch(0.5) };
        expect(effectiveGain(channels, "vocals")).toBe(0);
        // soloing a muted track still silences other tracks (anySolo is true)
        expect(effectiveGain(channels, "drums")).toBe(0);
    });

    it("clearing all solos restores normal mix", () => {
        const channels = {
            vocals: ch(0.7),
            drums: ch(0.5),
            bass: ch(0.6),
        };
        expect(effectiveGain(channels, "vocals")).toBe(0.7);
        expect(effectiveGain(channels, "drums")).toBe(0.5);
        expect(effectiveGain(channels, "bass")).toBe(0.6);
    });

    it("returns 0 for an unknown channel name", () => {
        const channels = { vocals: ch(0.7) };
        expect(effectiveGain(channels, "ghost")).toBe(0);
    });

    it("solo + mute on the same channel still mutes that channel and silences others", () => {
        const channels = {
            vocals: ch(0.7, true, true),
            drums: ch(0.5, false, false),
        };
        expect(effectiveGain(channels, "vocals")).toBe(0);
        expect(effectiveGain(channels, "drums")).toBe(0);
    });
});
