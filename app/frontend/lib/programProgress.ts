// Program progress and "where you left off", kept per user in this browser (localStorage).
// Nothing here talks to the backend. To sync across devices later, store the same two objects in a table.
import { WEEKS, WORKOUT_DAYS_PER_WEEK } from "../app/programs/programsData";

export const TOTAL_DAYS = WEEKS * WORKOUT_DAYS_PER_WEEK; // 20 training days per program

export type ProgState = { done: Record<number, string>; checked: Record<string, boolean> }; // day -> completed date
export type LastState = { slug: string; day: number; view: "daily" | "list"; week: number | "all"; at: string };

const progKey = (uid: string | number, slug: string) => `ascenda-program-${uid}-${slug}`;
const lastKey = (uid: string | number) => `ascenda-last-program-${uid}`;

function read<T>(key: string): T | null {
  try { const raw = localStorage.getItem(key); return raw ? (JSON.parse(raw) as T) : null; } catch { return null; }
}
function write(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}

export const readProgress = (uid: string | number, slug: string): ProgState => {
  const s = read<Partial<ProgState>>(progKey(uid, slug));
  return { done: s?.done ?? {}, checked: s?.checked ?? {} };
};
export const writeProgress = (uid: string | number, slug: string, s: ProgState) => write(progKey(uid, slug), s);

export const readLast = (uid: string | number) => read<LastState>(lastKey(uid));
export const writeLast = (uid: string | number, s: Omit<LastState, "at">) => write(lastKey(uid), { ...s, at: new Date().toISOString() });

/** Whole-number percent of the 20 training days completed. */
export const percentDone = (s: ProgState) => Math.min(100, Math.round((Object.keys(s.done).length / TOTAL_DAYS) * 100));
