import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { usePlayerStore } from "../model/store";
import { TrackChannel } from "./TrackChannel";
import { Transport } from "./Transport";

export function Player() {
    const status = usePlayerStore((s) => s.status);
    const tracks = usePlayerStore((s) => s.tracks);
    const errorMessage = usePlayerStore((s) => s.errorMessage);

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Player</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {status === "empty" && (
                    <p className="text-sm text-muted-foreground">
                        분리가 끝나면 여기에 멀티트랙 플레이어가 자동으로
                        나타납니다.
                    </p>
                )}

                {status === "loading" && (
                    <p className="text-sm text-muted-foreground">
                        트랙 로딩 중…
                    </p>
                )}

                {status === "error" && errorMessage && (
                    <p className="text-sm text-destructive">{errorMessage}</p>
                )}

                {status !== "empty" && status !== "loading" && (
                    <>
                        {errorMessage && status !== "error" && (
                            <p className="text-xs text-amber-600 dark:text-amber-400">
                                {errorMessage}
                            </p>
                        )}
                        <Transport />
                        <div className="flex gap-3 overflow-x-auto pt-1">
                            {tracks.map((t) => (
                                <TrackChannel key={t.name} name={t.name} />
                            ))}
                        </div>
                    </>
                )}
            </CardContent>
        </Card>
    );
}
