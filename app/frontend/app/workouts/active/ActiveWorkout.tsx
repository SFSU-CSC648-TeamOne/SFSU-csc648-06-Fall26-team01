"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import Navbar from "../../../components/Navbar";
import { api, useRequireAuth } from "../../../lib/auth";
import s from "../../screens.module.css";

type Exercise = { id: number; name: string; role: string; sets: number | null; reps: number | null };
type Detail = { id: number; name: string; exercises: Exercise[] };
type Result = { status: "done" | "skipped"; weight: string };

const clock = (sec: number) => `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;

export default function ActiveWorkout() {
  useRequireAuth();
  const router = useRouter();
  const sessionId = useSearchParams().get("session");
  const [w, setW] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [i, setI] = useState(0);
  const [results, setResults] = useState<Record<number, Result>>({});
  const [weight, setWeight] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [saving, setSaving] = useState(false);
  const started = useRef(new Date());

  useEffect(() => {
    if (!sessionId) { setError("No workout selected. Pick one from Programs."); return; }
    api<Detail>(`/workout-sessions/${sessionId}`).then(setW).catch((e) => setError(e.message));
  }, [sessionId]);

  useEffect(() => { const t = setInterval(() => setSeconds((x) => x + 1), 1000); return () => clearInterval(t); }, []);

  const cur = w?.exercises[i];
  const next = w?.exercises[i + 1];
  const doneCount = useMemo(() => Object.values(results).filter((r) => r.status === "done").length, [results]);

  function mark(status: Result["status"]) {
    if (!cur) return;
    setResults((r) => ({ ...r, [cur.id]: { status, weight } }));
    setWeight("");
    if (w && i < w.exercises.length - 1) setI(i + 1);
  }

  /** Finishing logs the workout and saves it to Training history. There is no separate log screen. */
  async function finish() {
    if (!w) return;
    setSaving(true); setError("");
    const entries = w.exercises.map((e) => {
      const r = results[e.id];
      return {
        exercise_id: e.id,
        reps: r?.status === "done" ? Math.min(1000, (e.sets ?? 1) * (e.reps ?? 1)) : 0,
        weight_kg: r?.weight ? Math.min(2000, Math.max(0, Number(r.weight))) : null,
        status: r?.status === "done" ? "completed" : "skipped",   // backend EntryStatus values
      };
    });
    try {
      await api("/workout-records", {
        method: "POST",
        body: JSON.stringify({
          workout_session_id: w.id,
          performed_at: started.current.toISOString(),
          duration_minutes: Math.min(600, Math.max(1, Math.round(seconds / 60))),
          entries,
        }),
      });
      router.push("/history");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the workout");
      setSaving(false);
    }
  }

  return (
    <main className={s.page}>
      <Navbar />
      <div className={s.wrap}>
        <p className={s.kicker}>{w ? `${w.name} · exercise ${Math.min(i + 1, w.exercises.length)} of ${w.exercises.length}` : "Active workout"}</p>
        {error && <p className={s.error} role="alert">{error}</p>}
        {cur && (
          <>
            <h1 className={s.h1}>{cur.name}</h1>
            <p className={s.muted}>{cur.sets && cur.reps ? `${cur.sets} sets × ${cur.reps} reps` : "Follow the exercise"} · {cur.role.toUpperCase()}</p>
            <p className={s.timer} aria-label="Elapsed time">{clock(seconds)}</p>
            <div className={s.field} style={{ maxWidth: 220 }}>
              <label htmlFor="kg">Weight used (kg, optional)</label>
              <input id="kg" className={s.input} inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} />
            </div>
            <div className={s.actions}>
              <Link href={`/exercises/${cur.id}`} target="_blank" className={`${s.btn} ${s.btnGhost}`}>Watch demo ↗</Link>
              <button className={s.btn} onClick={() => mark("done")}>Done</button>
              <button className={`${s.btn} ${s.btnGhost}`} onClick={() => mark("skipped")}>Skip</button>
            </div>
            <p className={s.muted} style={{ marginTop: 22 }}>{next ? `Next: ${next.name}` : "Last exercise"} · {doneCount} done</p>
          </>
        )}
        {w && (
          <div className={s.actions} style={{ marginTop: 40 }}>
            <button className={`${s.btn} ${s.btnGreen}`} onClick={finish} disabled={saving}>{saving ? "Saving..." : "Finish and save"}</button>
          </div>
        )}
      </div>
    </main>
  );
}
