export const SAVED_PROGRAMS_KEY = "ascenda.savedPrograms.v1";
export const SAVED_PROGRAMS_EVENT = "ascenda:saved-programs-changed";

export type SavedProgram = { id: number; name: string };

export function readSavedPrograms(): SavedProgram[] {
    if (typeof window === "undefined") return [];
    try {
        const value: unknown = JSON.parse(localStorage.getItem(SAVED_PROGRAMS_KEY) ?? "[]");
        if (!Array.isArray(value)) return [];
        return value.filter((item): item is SavedProgram =>
            typeof item === "object" && item !== null &&
            Number.isInteger(item.id) && item.id > 0 &&
            typeof item.name === "string"
        );
    } catch {
        return [];
    }
}

export function addSavedProgram(program: SavedProgram): void {
    const current = readSavedPrograms();
    const updated = [...current.filter((saved) => saved.id !== program.id), program];
    localStorage.setItem(SAVED_PROGRAMS_KEY, JSON.stringify(updated));
    window.dispatchEvent(new Event(SAVED_PROGRAMS_EVENT));
}