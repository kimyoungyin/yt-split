import { beforeEach, describe, expect, it, vi } from "vitest";

import { useLibraryStore } from "./store";

vi.mock("../../../entities/project/api/library", () => ({
    listProjects: vi.fn(),
}));

describe("library store", () => {
    beforeEach(() => useLibraryStore.setState({ items: [], status: "idle" }));

    it("loads and sorts items by created_at desc", async () => {
        const { listProjects } = await import(
            "../../../entities/project/api/library"
        );
        (listProjects as ReturnType<typeof vi.fn>).mockResolvedValue([
            {
                id: "a",
                title: "Old",
                created_at: "2026-01-01T00:00:00Z",
                url: "",
                device: "cpu",
                stem_mode: "all",
                tracks: {},
                schema_version: 1,
            },
            {
                id: "b",
                title: "New",
                created_at: "2026-05-01T00:00:00Z",
                url: "",
                device: "cpu",
                stem_mode: "all",
                tracks: {},
                schema_version: 1,
            },
        ]);

        await useLibraryStore.getState().refresh();
        const items = useLibraryStore.getState().items;
        expect(items.map((i) => i.id)).toEqual(["b", "a"]);
    });

    it("sets status to loading during refresh then idle", async () => {
        const { listProjects } = await import(
            "../../../entities/project/api/library"
        );
        let resolveList!: (v: unknown[]) => void;
        (listProjects as ReturnType<typeof vi.fn>).mockReturnValue(
            new Promise((res) => { resolveList = res; }),
        );

        const promise = useLibraryStore.getState().refresh();
        expect(useLibraryStore.getState().status).toBe("loading");

        resolveList([]);
        await promise;
        expect(useLibraryStore.getState().status).toBe("idle");
    });

    it("sets status to error when listProjects rejects", async () => {
        const { listProjects } = await import(
            "../../../entities/project/api/library"
        );
        (listProjects as ReturnType<typeof vi.fn>).mockRejectedValue(
            new Error("tauri error"),
        );

        await useLibraryStore.getState().refresh();
        expect(useLibraryStore.getState().status).toBe("error");
    });
});
