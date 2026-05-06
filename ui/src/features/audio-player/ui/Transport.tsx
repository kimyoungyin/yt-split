import { Pause, Play } from "lucide-react";

import { Button } from "@/shared/ui/button";
import { Slider } from "@/shared/ui/slider";
import { usePlayerStore } from "../model/store";

function formatTime(seconds: number): string {
    if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
}

export function Transport() {
    const status = usePlayerStore((s) => s.status);
    const currentTime = usePlayerStore((s) => s.currentTime);
    const duration = usePlayerStore((s) => s.duration);
    const play = usePlayerStore((s) => s.play);
    const pause = usePlayerStore((s) => s.pause);
    const seek = usePlayerStore((s) => s.seek);

    const isPlaying = status === "playing";
    const disabled =
        status === "empty" || status === "loading" || status === "error";

    return (
        <div className="flex items-center gap-3 w-full">
            <Button
                size="icon"
                variant={isPlaying ? "secondary" : "default"}
                onClick={() => (isPlaying ? pause() : play())}
                disabled={disabled}
                aria-label={isPlaying ? "Pause" : "Play"}
            >
                {isPlaying ? (
                    <Pause className="size-4" />
                ) : (
                    <Play className="size-4" />
                )}
            </Button>

            <span className="font-mono text-xs tabular-nums text-muted-foreground w-10 text-right">
                {formatTime(currentTime)}
            </span>

            <Slider
                value={[duration === 0 ? 0 : currentTime]}
                min={0}
                max={duration === 0 ? 1 : duration}
                step={0.01}
                disabled={disabled || duration === 0}
                onValueChange={(v) => seek(v[0] ?? 0)}
                className="flex-1"
            />

            <span className="font-mono text-xs tabular-nums text-muted-foreground w-10">
                {formatTime(duration)}
            </span>
        </div>
    );
}
