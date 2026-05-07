export interface ProjectMeta {
    schema_version: number;
    id: string;
    title: string;
    url: string;
    created_at: string;
    device: string;
    stem_mode: string;
    /** Absolute file paths keyed by stem name (resolved by Rust before delivery). */
    tracks: Record<string, string>;
}
