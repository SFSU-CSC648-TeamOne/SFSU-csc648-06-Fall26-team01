"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import styles from "./programs.module.css";
import home from "./programsHome.module.css";
import Navbar from "../../components/Navbar";
import { useAuth } from "../../lib/auth";
import { TOTAL_DAYS, type LastState, type ProgState, percentDone, readLast, readProgress } from "../../lib/programProgress";
import { PROGRAMS, buildSchedule, minutesRange, WEEKS, WORKOUT_DAYS_PER_WEEK } from "./programsData";

const EMPTY: ProgState = { done: {}, checked: {} };

/** Programs page = the home screen after login: continue where you left off + % complete per program. */
export default function ProgramsHome() {
  const { user, loading } = useAuth();
  const [progress, setProgress] = useState<Record<string, ProgState>>({});
  const [last, setLast] = useState<LastState | null>(null);

  useEffect(() => {
    if (loading) return;
    const uid = user?.id ?? "guest";
    setProgress(Object.fromEntries(PROGRAMS.map((p) => [p.slug, readProgress(uid, p.slug)])));
    setLast(readLast(uid));
  }, [loading, user?.id]);

  const lastProgram = last ? PROGRAMS.find((p) => p.slug === last.slug) : undefined;
  const lastState = lastProgram ? progress[lastProgram.slug] ?? EMPTY : EMPTY;

  return (
    <>
    <Navbar />
    <main className={styles.page}>
      <header className={styles.pageHead}>
        <p className={styles.kicker}>{user ? `Welcome back${user.display_name ? ", " + user.display_name.split(" ")[0] : ""}` : "Programs"}</p>
        <h1 className={styles.h1}>
          Pick your <span className={styles.accent}>program.</span>
        </h1>
        <p className={styles.lead}>
          Each program has 10 exercises combined into {WORKOUT_DAYS_PER_WEEK} training days a week for {WEEKS} weeks.
        </p>
      </header>

      {lastProgram && last && (
        <section className={home.resume} aria-label="Continue where you left off">
          <div>
            <p className={styles.kicker}>Continue where you left off</p>
            <h2 className={home.resumeTitle}>{lastProgram.name} <span>{lastProgram.fullName}</span></h2>
            <p className={home.resumeMeta}>Day {last.day} · {last.view === "list" ? "List" : "Daily"} view · {percentDone(lastState)}% complete</p>
            <div className={home.bar} aria-hidden="true"><div className={home.barFill} style={{ width: `${percentDone(lastState)}%` }} /></div>
          </div>
          <Link href={`/programs/${lastProgram.slug}`} className={home.resumeBtn}>Continue →</Link>
        </section>
      )}

      <ul className={styles.cardGrid}>
        {PROGRAMS.map((p) => {
          const days = buildSchedule(p);
          const [min, max] = minutesRange(days);
          const st = progress[p.slug] ?? EMPTY;
          const pct = percentDone(st);
          const count = Object.keys(st.done).length;
          return (
            <li key={p.slug}>
              <Link href={`/programs/${p.slug}`} className={styles.programCard}>
                <span className={styles.programCode}>{p.name}</span>
                <span className={styles.programName}>{p.fullName}</span>
                <span className={styles.programTag}>{p.tagline}</span>
                <span className={styles.chips}>
                  <span className={styles.chip}>{WEEKS * WORKOUT_DAYS_PER_WEEK} workouts</span>
                  <span className={styles.chip}>{min}-{max} min/day</span>
                  <span className={styles.chip}>{p.exercises.length} exercises</span>
                </span>
                <span className={home.pctRow}>
                  <span>{pct}% complete</span><span>{count}/{TOTAL_DAYS} days</span>
                </span>
                <span className={home.bar} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${p.fullName} progress`}>
                  <span className={home.barFill} style={{ width: `${pct}%` }} />
                </span>
                <span className={styles.cta}>{count > 0 ? "Open program →" : "View program →"}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </main>
    </>
  );
}
