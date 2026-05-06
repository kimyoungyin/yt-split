import type { ChannelState } from "./types";

/**
 * DAW-standard solo: when any channel is soloed, only soloed channels pass
 * (OR across solos). Mute is orthogonal — it always wins.
 *
 * Returns the gain factor (0..volume) the engine should apply to `name`.
 */
export function effectiveGain(
    channels: Record<string, ChannelState>,
    name: string,
): number {
    const ch = channels[name];
    if (!ch) return 0;
    if (ch.mute) return 0;
    const anySolo = Object.values(channels).some((c) => c.solo);
    if (anySolo && !ch.solo) return 0;
    return ch.volume;
}
