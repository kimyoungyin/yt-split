import { Loader2, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/shared/ui/button";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Progress } from "@/shared/ui/progress";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/shared/ui/select";

import { cancelPipeline, runPipeline } from "../api/sidecar";
import { usePipelineStore } from "../model/store";

const STEM_OPTIONS: { value: string; label: string }[] = [
    { value: "all", label: "all stems" },
    { value: "vocals", label: "--stem vocals" },
    { value: "drums", label: "--stem drums" },
    { value: "bass", label: "--stem bass" },
    { value: "other", label: "--stem other" },
];

export function PipelineRunner() {
    const [url, setUrl] = useState("");
    const [stem, setStem] = useState<string>("all");

    const status = usePipelineStore((s) => s.status);
    const hardware = usePipelineStore((s) => s.hardware);
    const currentStage = usePipelineStore((s) => s.currentStage);
    const progress = usePipelineStore((s) => s.progress);
    const tracks = usePipelineStore((s) => s.tracks);
    const errorMessage = usePipelineStore((s) => s.errorMessage);
    const logs = usePipelineStore((s) => s.logs);

    const onRun = async () => {
        if (!url.trim()) return;
        try {
            await runPipeline({
                url: url.trim(),
                stem: stem === "all" ? null : stem,
            });
        } catch (e) {
            // Errors from `invoke` already updated the store via the done event,
            // but log here for visibility.
            console.error(e);
        }
    };

    const onCancel = async () => {
        try {
            await cancelPipeline();
        } catch (e) {
            console.error(e);
        }
    };

    const isRunning = status === "running";
    const pct = Math.round(progress * 100);

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">yt-split</CardTitle>
                <div className="text-xs text-muted-foreground pt-1">
                    {hardware ? (
                        <span>
                            device:{" "}
                            <span className="font-medium text-foreground">
                                {hardware.demucs_device}
                            </span>
                            {" · "}RAM {hardware.ram_gb.toFixed(1)} GB
                            {" · "}free {hardware.free_space_gb.toFixed(1)} GB
                            {hardware.warning && (
                                <span className="ml-2 text-amber-600 dark:text-amber-400">
                                    {hardware.warning}
                                </span>
                            )}
                        </span>
                    ) : (
                        <span>
                            (hardware unknown — Run을 한 번 실행하면 채워집니다)
                        </span>
                    )}
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                <div className="flex gap-2">
                    <Input
                        type="text"
                        placeholder="https://www.youtube.com/watch?v=..."
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        disabled={isRunning}
                        className="flex-1"
                    />
                    <Select
                        value={stem}
                        onValueChange={setStem}
                        disabled={isRunning}
                    >
                        <SelectTrigger className="w-[160px]">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {STEM_OPTIONS.map((opt) => (
                                <SelectItem key={opt.value} value={opt.value}>
                                    {opt.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    {isRunning ? (
                        <Button
                            variant="destructive"
                            onClick={onCancel}
                            className="min-w-[88px]"
                        >
                            <X className="size-4" /> Cancel
                        </Button>
                    ) : (
                        <Button
                            onClick={onRun}
                            disabled={!url.trim()}
                            className="min-w-[88px]"
                        >
                            Run
                        </Button>
                    )}
                </div>

                <div className="space-y-2">
                    <div className="text-xs flex items-center gap-2">
                        <span>
                            status:{" "}
                            <span className="font-medium text-foreground">
                                {status}
                            </span>
                        </span>
                        {currentStage && (
                            <span className="text-muted-foreground">
                                · stage:{" "}
                                <span className="font-medium text-foreground">
                                    {currentStage}
                                </span>{" "}
                                ({pct}%)
                            </span>
                        )}
                        {isRunning && (
                            <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
                        )}
                    </div>
                    <Progress value={pct} />
                    {errorMessage && (
                        <p className="text-sm text-destructive">
                            {errorMessage}
                        </p>
                    )}
                </div>

                {Object.keys(tracks).length > 0 && (
                    <div>
                        <h3 className="text-sm font-medium mb-2">
                            출력 스템
                        </h3>
                        <ul className="space-y-1 font-mono text-xs text-muted-foreground">
                            {Object.entries(tracks).map(([name, path]) => (
                                <li key={name} className="break-all">
                                    <span className="font-semibold text-foreground">
                                        {name}
                                    </span>
                                    : {path}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {logs.length > 0 && (
                    <details className="text-xs">
                        <summary className="cursor-pointer text-muted-foreground select-none">
                            logs ({logs.length})
                        </summary>
                        <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-muted p-3 font-mono text-[11px] leading-snug">
                            {logs.join("\n")}
                        </pre>
                    </details>
                )}
            </CardContent>
        </Card>
    );
}
