import { create } from "zustand";

import {
    deleteProject,
    listProjects,
} from "../../../entities/project/api/library";
import type { ProjectMeta } from "../../../entities/project/model/types";

type LibraryStatus = "idle" | "loading" | "error";

interface LibraryState {
    items: ProjectMeta[];
    status: LibraryStatus;
    refresh: () => Promise<void>;
    deleteAndRefresh: (id: string) => Promise<void>;
}

export const useLibraryStore = create<LibraryState>((set) => ({
    items: [],
    status: "idle",

    refresh: async () => {
        set({ status: "loading" });
        try {
            const raw = await listProjects();
            const sorted = [...raw].sort((a, b) =>
                b.created_at.localeCompare(a.created_at),
            );
            set({ items: sorted, status: "idle" });
        } catch {
            set({ status: "error" });
        }
    },

    deleteAndRefresh: async (id) => {
        await deleteProject(id);
        set((s) => ({ items: s.items.filter((p) => p.id !== id) }));
    },
}));
