import { Trash2 } from "lucide-react";
import { useEffect } from "react";

import { usePlayerStore } from "@/features/audio-player/model/store";
import { Button } from "@/shared/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/shared/ui/card";
import { useLibraryStore } from "../model/store";

export function Library() {
    const { items, status, refresh, deleteAndRefresh } = useLibraryStore();
    const loadPlayer = usePlayerStore((s) => s.load);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    if (status === "loading" && items.length === 0) {
        return null;
    }

    if (items.length === 0) {
        return (
            <p className="text-sm text-muted-foreground text-center py-4">
                아직 처리한 곡이 없습니다.
            </p>
        );
    }

    function handleLoad(tracks: Record<string, string>) {
        void loadPlayer(tracks);
    }

    return (
        <div className="space-y-2">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                라이브러리
            </h2>
            <div className="grid gap-2">
                {items.map((project) => (
                    <Card
                        key={project.id}
                        className="cursor-pointer hover:bg-accent transition-colors"
                        onClick={() => handleLoad(project.tracks)}
                    >
                        <CardHeader className="p-4 pb-2">
                            <CardTitle className="text-base">
                                {project.title || project.id}
                            </CardTitle>
                            <CardDescription className="text-xs">
                                {new Date(project.created_at).toLocaleString(
                                    "ko-KR",
                                )}{" "}
                                · {project.device} · {project.stem_mode}
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="p-4 pt-0 flex justify-end">
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-muted-foreground hover:text-destructive"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    void deleteAndRefresh(project.id);
                                }}
                            >
                                <Trash2 className="h-4 w-4" />
                            </Button>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
