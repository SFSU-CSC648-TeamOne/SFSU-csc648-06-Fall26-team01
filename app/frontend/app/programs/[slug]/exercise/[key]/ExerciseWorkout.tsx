"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Navbar from "../../../../../components/Navbar";
import { api, useAuth } from "../../../../../lib/auth";
import { readProgress, writeLast, writeProgress } from "../../../../../lib/programProgress";
import { buildSchedule, CATALOG_IDS, DUMMY_MODELS, getProgram } from "../../../programsData";
import s from "./exercise.module.css";
import { useProgramPrescription } from "../../../useProgramPrescription";

const ScanViewer = dynamic(() => import("../../../../../components/ScanViewer"), {
  ssr: false, loading: () => <div className={s.empty}>Loading 3D scan...</div>,
});

const DummyViewer = dynamic(() => import("../../../../../components/DummyViewer"), {
  ssr: false, loading: () => <div className={s.empty}>Loading 3D demo...</div>,
});

type Found = { id: number; name: string };
type Scan = { position: number; label: string; description?: string | null; model_url?: string | null };
type Model = { video_url?: string | null };

// adding a type and helper 
type Detail = {
  description?: string | null;
  primary_muscles?: string[];
  secondary_muscles?: string[];
  equipment?: string[];
  license_name?: string | null;
  license_author?: string | null;
};

// hides text
const usable = (t?: string | null) => {
  const x = (t ?? "").trim();
  return x.length >= 20 && !x.startsWith("Custom description created by");
};

const norm = (t: string) => t.toLowerCase().replace(/[^a-z0-9]/g, "");
const clock = (ms: number) => {
  const sec = Math.floor(ms / 1000);
  return `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
};

/** One exercise of a program day: video on top, two Niantic scans below, big timer + rep counter on the right. */
export default function ExerciseWorkout({ slug, exKey }: { slug: string; exKey: string }) {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const uid = user?.id ?? "guest";
  const program = getProgram(slug)!;
  const templateDays = useMemo(() => buildSchedule(program), [program]);
  const {days, baseline, loading: baselineLoading, error: baselineError, } 
      = useProgramPrescription(program, templateDays, user?.id ?? null, authLoading);

  const day = days.find((d) => d.exercises.some((e) => e.key === exKey));
  // Same order as the program page: core exercises first, then optional ones.
  const list = useMemo(() => (day ? [...day.exercises.filter((e) => e.role === "core"), ...day.exercises.filter((e) => e.role === "accessory")] : []), [day]);
  const index = list.findIndex((e) => e.key === exKey);
  const item = list[index];
  const dummy = item ? DUMMY_MODELS[item.exercise.id] : undefined;

  // ---- media from the backend (matched by exact exercise name) ----
  const [video, setVideo] = useState<string | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [mediaLoading, setMediaLoading] = useState(true);
  // Video and scans are looked up by this database name (the `demo` field in programsData.ts, else the exercise name).
  const name = item ? item.exercise.demo ?? item.exercise.name : undefined;
  // Video file in public/ (the `video` field in programsData.ts), used when the database has no video for `name`.
  const fallbackVideo = item?.exercise.video ?? null;

  useEffect(() => {
    if (!name) return;
    let live = true;
    // This component is reused when moving to the next exercise, so clear the previous one's media first.
    setVideo(fallbackVideo);
    setScans([]);
    setMediaLoading(true);
    (async () => {
      try {
        const page = await api<{ items: Found[] }>(`/exercises?q=${encodeURIComponent(name)}&limit=50`);
        const hit = page.items.find((x) => norm(x.name) === norm(name));
        if (!hit) return;
        const [m, sc] = await Promise.all([
          api<Model>(`/exercises/${hit.id}/model`).catch(() => ({} as Model)),
          api<Scan[]>(`/exercises/${hit.id}/scans`).catch(() => [] as Scan[]),
        ]);
        if (live) { setVideo(m.video_url ?? fallbackVideo); setScans([...sc].sort((a, b) => a.position - b.position)); }
      } catch {} finally { if (live) setMediaLoading(false); }
    })();
    return () => { live = false; };
  }, [name, fallbackVideo]);

  // WGER API info (description, muscles, equipment, license, etc etc)
  const catalogId = item ? CATALOG_IDS[item.exercise.id] : undefined;
  const [detail, setDetail] = useState<Detail | null>(null);
  useEffect(() => {
    setDetail(null);
    if (!catalogId) return;
    let live = true;
    api<Detail>(`/exercises/${catalogId}`)
      .then((d) => { if (live) setDetail(d); })
      .catch(() => {});
    return () => { live = false; };
  }, [catalogId]);

  // ---- big timer (stopwatch) ----
  const [elapsed, setElapsed] = useState(0);
  const [running, setRunning] = useState(false);
  const startedAt = useRef(0);
  useEffect(() => {
    if (!running) return;
    startedAt.current = Date.now() - elapsed;
    const id = setInterval(() => setElapsed(Date.now() - startedAt.current), 200);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  // ---- rep counter ----
  const targetSets = item?.sets ?? 3;
  const targetReps = item?.reps ?? 10;
  const isTimed = item?.exercise.id === "plank" || item?.exercise.id === "wall-sit";
  const needsRegression = targetReps === 0;
  const [set, setSet] = useState(1);
  const [reps, setReps] = useState(0);
  
    // ---- reset state when moving to a new exercise ----
  useEffect(() => {
    setSet(1);
    setReps(0);
    setRunning(false);
    setElapsed(0);
  }, [exKey]);


  const allDone = set > targetSets;
  const setComplete = !allDone && !needsRegression && 
    (isTimed ? elapsed >= targetReps * 1000 : reps >= targetReps);

  const addRep = () => {
    if (allDone || needsRegression || isTimed) return;
    setRunning(true);
    setReps((current) => current + 1);
  };
  const nextSet = () => { setSet((current) => current + 1); 
    setReps(0); 
    if (isTimed) { setRunning(false); setElapsed(0); 
    } 
  };

  // ---- finish ----
  const finish = useCallback(() => {
    if (!item || !day || needsRegression) return;
    if (!authLoading) {
      const st = readProgress(uid, slug);
      writeProgress(uid, slug, { ...st, checked: { ...st.checked, [item.key]: true } });
      writeLast(uid, { slug, day: day.number, view: "daily", week: day.week });
    }
    const next = list[index + 1];
    router.push(next ? `/programs/${slug}/exercise/${next.key}` : `/programs/${slug}`);
  }, [item, day, needsRegression, authLoading, uid, slug, list, index, router]);

  if (authLoading || baselineLoading) {
    return (
      <>
        <Navbar />
        <main className={s.page}>
          <p className={s.banner}>
            Loading your training prescription...
          </p>
        </main>
      </>
    );
  }

  if (baselineError) {
    return (
      <>
        <Navbar />
        <main className={s.page}>
          <p className={s.banner}>
            Error loading baseline.
          </p>
        </main>
      </>
    );
  }

  if (user && !baseline) {
    return (
      <>
        <Navbar />
        <main className={s.page}>
          <h1>Assessment required</h1>
          <p>Complete your program baseline before training.</p>
          <Link href={`/assessment/${slug}`} className={s.back}>
          Take assessment →
          </Link>
        </main>
      </>
    );
  }
  if (!item || !day) {
    return (
      <>
        <Navbar />
        <main className={s.page}><p className={s.empty}>Exercise not found.</p><Link href={`/programs/${slug}`} className={s.back}>← Back to program</Link></main>
      </>
    );
  }

  const prev = list[index - 1];
  const next = list[index + 1];

  return (
    <>
    <Navbar />
    <main className={s.page}>
      <Link href={`/programs/${slug}`} className={s.back}>← {program.name} · Day {day.number}</Link>
      <header className={s.head}>
        <p className={s.kicker}>Week {day.week} · Day {day.number} · Exercise {index + 1} of {list.length}{item.role === "accessory" ? " · optional" : ""}</p>
        <h1 className={s.h1}>{item.exercise.name}</h1>
        <p className={s.meta}> {needsRegression ? 
          "Exercise regression required": `${item.sets} sets × ${item.reps} ${
            isTimed ? "seconds" : "reps"
            }`} 
            {" · "} {item.exercise.muscle}
            {" · "} {item.exercise.equipment}
          </p>

      </header>

      <div className={s.layout}>
        {/* LEFT: video on top, details, Niantic scans below */}
        <div className={s.media}>
          <section className={s.card} aria-label="Exercise video">
            <div className={s.cardTop}>
              <span>3D VIDEO</span>
              <span>{video ? "PLAYING IN GYM SCAN" : dummy ? "3D DEMO · DRAG TO ROTATE" : mediaLoading ? "LOADING" : "NOT UPLOADED YET"}</span>
            </div>
            {video
              ? <video className={s.video} src={video} controls playsInline loop preload="metadata" />
              : dummy
                ? <DummyViewer url={dummy.url} clip={dummy.clip} />
                : <div className={s.videoEmpty}>{mediaLoading ? "Loading video..." : "The demonstration video for this exercise is not uploaded yet."}</div>}
            {dummy && !video && <div className={s.cap}><small>3D motion by KinemIQ</small></div>}
          </section>

          {detail && (
            <section className={s.card} aria-label="Exercise details">
              <div className={s.cardTop}><span>HOW TO</span><span>FROM WGER</span></div>
              <div className={s.cap}>
                {usable(detail.description) && <small>{detail.description}</small>}
                {!!detail.primary_muscles?.length && <small><b>Primary:</b> {detail.primary_muscles.join(", ")}</small>}
                {!!detail.secondary_muscles?.length && <small><b>Secondary:</b> {detail.secondary_muscles.join(", ")}</small>}
                {!!detail.equipment?.length && <small><b>Equipment:</b> {detail.equipment.join(", ")}</small>}
                <small>
                  Source: wger.de · {detail.license_name ?? "CC-BY-SA"} · {detail.license_author ?? "wger.de contributors"}
                </small>
              </div>
            </section>
          )}

          <section aria-label="Niantic 3D posture scans">
            <h2 className={s.h2}>Niantic 3D posture scans</h2>
            <div className={s.scanGrid}>
              {[0, 1].map((i) => {
                const sc = scans[i];
                return (
                  <div className={s.card} key={i}>
                    <div className={s.cardTop}><span>NIANTIC 3D SCAN</span><span>DRAG TO ROTATE</span></div>
                    {sc?.model_url
                      ? <ScanViewer url={sc.model_url} />
                      : <div className={s.scanEmpty}>{mediaLoading ? "Loading scan..." : `Posture scan ${i + 1} is not uploaded yet.`}</div>}
                    <div className={s.cap}>
                      <b>{i + 1} {sc?.label ?? (i === 0 ? "Top position" : "Bottom position")}</b>
                      {sc?.description && <small>{sc.description}</small>}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        {/* RIGHT: big timer + rep counter */}
        <aside className={s.side} aria-label="Timer and rep counter">
          <section className={s.panel}>
            <p className={s.label}>Timer</p>
            <p className={s.clock} role="timer" aria-live="off">{clock(elapsed)}</p>
            <div className={s.row}>
              <button type="button" className={running ? s.btnPause : s.btnStart} onClick={() => setRunning((r) => !r)}>{running ? "Pause" : elapsed > 0 ? "Resume" : "Start"}</button>
              <button type="button" className={s.btnGhost} onClick={() => { setRunning(false); setElapsed(0); }}>Reset</button>
            </div>
          </section>

          <section className={s.panel}>
            <div className={s.setsRow}>
              <p className={s.label}>{allDone ? "All sets done" : `Set ${set} of ${targetSets}`}</p>
              <span className={s.dots} aria-hidden="true">{Array.from({ length: targetSets }, (_, i) => <i key={i} className={i < set - 1 || allDone ? s.dotOn : i === set - 1 ? s.dotNow : ""} />)}</span>
            </div>
            <p className={s.reps} role="status" aria-live="polite"> {isTimed ? 
              Math.floor(elapsed / 1000) 
              : allDone ? targetReps : reps} 
              <small>
                {" / "} {targetReps} {isTimed ? "sec" : "reps"}
                </small>
                </p>

                <button 
                type="button"
                className={s.tap}
                onClick={addRep}
                disabled={ allDone || setComplete || needsRegression || isTimed }
                aria-label={ isTimed ? "Use timer for hold" : "Count one rep"}
                >
                {needsRegression 
                  ? "REGRESSION NEEDED" : allDone
                    ? "DONE" : setComplete
                      ? "SET COMPLETE" : isTimed
                        ? "USE TIMER"
                        : "+1 REP"}
              </button>
            <div className={s.row}>
              {setComplete && !allDone && <button type="button" className={s.btnStart} onClick={nextSet}>{set === targetSets ? "Finish sets" : "Next set"}</button>}
              <button type="button" className={s.btnGhost} onClick={() => setReps((r) => Math.max(0, r - 1))} 
                disabled={allDone || isTimed || reps === 0 ||needsRegression}>−1
                </button>
              <button type="button" className={s.btnGhost} onClick={() => { 
                  setSet(1); 
                  setReps(0);
                  setRunning(false);
                  setElapsed(0);
                }}
              >
                Reset reps
              </button>
            
            </div>
          </section>

          <button type="button" className={s.finish} onClick={finish} disabled={needsRegression}
          >
            {needsRegression ? "Select and easier exercise" 
            : next ? "Mark done · next exercise →" 
            : "Mark done · finish day ✓"}
          </button>
          
          <div className={s.nav}>
            {prev ? <Link href={`/programs/${slug}/exercise/${prev.key}`}>← {prev.exercise.name}</Link> : <span />}
            {next && <Link href={`/programs/${slug}/exercise/${next.key}`}>{next.exercise.name} →</Link>}
          </div>
        </aside>
      </div>
    </main>
    </>
  );
}
