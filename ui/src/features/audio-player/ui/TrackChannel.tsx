import { Headphones, Volume2, VolumeX } from "lucide-react";

import { Slider } from "@/shared/ui/slider";
import { Toggle } from "@/shared/ui/toggle";
import { usePlayerStore } from "../model/store";

interface Props {
    name: string;
}

export function TrackChannel({ name }: Props) {
    const channel = usePlayerStore((s) => s.channels[name]);
    const anySolo = usePlayerStore((s) =>
        Object.values(s.channels).some((c) => c.solo),
    );
    const setChannelVolume = usePlayerStore((s) => s.setChannelVolume);
    const toggleMute = usePlayerStore((s) => s.toggleMute);
    const toggleSolo = usePlayerStore((s) => s.toggleSolo);

    if (!channel) return null;

    const silenced = channel.mute || (anySolo && !channel.solo);
    const StatusIcon = channel.solo
        ? Headphones
        : silenced
          ? VolumeX
          : Volume2;
    const statusColor = channel.solo
        ? "text-foreground"
        : silenced
          ? "text-muted-foreground/60"
          : "text-foreground";

    return (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-card px-3 py-4 min-w-[96px]">
            <div className="flex items-center gap-1.5">
                <StatusIcon className={`size-3.5 ${statusColor}`} />
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {name}
                </div>
            </div>

            <div className="h-32 flex items-center">
                <Slider
                    value={[channel.volume]}
                    min={0}
                    max={1}
                    step={0.01}
                    onValueChange={(v) =>
                        setChannelVolume(name, v[0] ?? 0)
                    }
                    orientation="vertical"
                    className="h-full"
                />
            </div>

            <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                {Math.round(channel.volume * 100)}
            </span>

            <div className="flex gap-1">
                <Toggle
                    size="sm"
                    variant="outline"
                    pressed={channel.mute}
                    onPressedChange={() => toggleMute(name)}
                    aria-label={`Mute ${name}`}
                    title="Mute"
                >
                    <VolumeX className="size-3.5" />
                </Toggle>
                <Toggle
                    size="sm"
                    variant="outline"
                    pressed={channel.solo}
                    onPressedChange={() => toggleSolo(name)}
                    aria-label={`Solo ${name}`}
                    title="Solo (모니터링)"
                >
                    <Headphones className="size-3.5" />
                </Toggle>
            </div>
        </div>
    );
}
