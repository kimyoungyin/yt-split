import { useState } from "react";

import { runPipeline } from "../api/sidecar";
import { usePipelineStore } from "../model/store";

const STEMS = ["", "vocals", "drums", "bass", "other"] as const;

export function PipelineRunner() {
    const [url, setUrl] = useState("");
    const [stem, setStem] = useState<string>("");

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
            await runPipeline({ url: url.trim(), stem: stem || null });
        } catch (e) {
            // Errors from `invoke` already updated the store via the done event,
            // but log here for visibility.
            console.error(e);
        }
    };

    const isRunning = status === "running";
    const pct = Math.round(progress * 100);

    return (
        <div style={{ padding: 24, fontFamily: "system-ui, sans-serif" }}>
            <h1 style={{ fontSize: 22, marginBottom: 12 }}>yt-split</h1>

            <section style={{ marginBottom: 16, fontSize: 14, color: "#444" }}>
                {hardware ? (
                    <div>
                        <span>
                            device: <b>{hardware.demucs_device}</b>
                        </span>
                        {" · "}
                        <span>RAM {hardware.ram_gb.toFixed(1)} GB</span>
                        {" · "}
                        <span>free {hardware.free_space_gb.toFixed(1)} GB</span>
                        {hardware.warning && (
                            <div style={{ color: "#a55", marginTop: 4 }}>
                                {hardware.warning}
                            </div>
                        )}
                    </div>
                ) : (
                    <span>
                        (hardware unknown — Run을 한 번 실행하면 채워집니다)
                    </span>
                )}
            </section>

            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                <input
                    type="text"
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    disabled={isRunning}
                    style={{ flex: 1, padding: "8px 10px", fontSize: 14 }}
                />
                <select
                    value={stem}
                    onChange={(e) => setStem(e.target.value)}
                    disabled={isRunning}
                    style={{ padding: "8px 10px", fontSize: 14 }}
                >
                    {STEMS.map((s) => (
                        <option key={s || "all"} value={s}>
                            {s ? `--stem ${s}` : "all stems"}
                        </option>
                    ))}
                </select>
                <button
                    onClick={onRun}
                    disabled={isRunning || !url.trim()}
                    style={{ padding: "8px 14px", fontSize: 14 }}
                >
                    {isRunning ? "Running…" : "Run"}
                </button>
            </div>

            <section style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, marginBottom: 4 }}>
                    status: <b>{status}</b>
                    {currentStage && (
                        <>
                            {" "}
                            · stage: <b>{currentStage}</b> ({pct}%)
                        </>
                    )}
                </div>
                <div
                    style={{
                        height: 8,
                        background: "#eee",
                        borderRadius: 4,
                        overflow: "hidden",
                    }}
                >
                    <div
                        style={{
                            width: `${pct}%`,
                            height: "100%",
                            background: status === "error" ? "#c44" : "#46a",
                            transition: "width 120ms linear",
                        }}
                    />
                </div>
                {errorMessage && (
                    <div style={{ color: "#c44", fontSize: 13, marginTop: 8 }}>
                        {errorMessage}
                    </div>
                )}
            </section>

            {Object.keys(tracks).length > 0 && (
                <section style={{ marginBottom: 16 }}>
                    <h3 style={{ fontSize: 14 }}>출력 스템</h3>
                    <ul
                        style={{
                            fontSize: 12,
                            fontFamily: "ui-monospace, monospace",
                        }}
                    >
                        {Object.entries(tracks).map(([name, path]) => (
                            <li key={name}>
                                <b>{name}</b>: {path}
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {logs.length > 0 && (
                <details style={{ fontSize: 12 }}>
                    <summary>logs ({logs.length})</summary>
                    <pre
                        style={{
                            maxHeight: 200,
                            overflow: "auto",
                            background: "#f6f6f6",
                            padding: 8,
                        }}
                    >
                        {logs.join("\n")}
                    </pre>
                </details>
            )}
        </div>
    );
}
