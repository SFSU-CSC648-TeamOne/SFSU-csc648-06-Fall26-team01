"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import styles from "../programs.module.css";
import Navbar from "../../../components/Navbar";
import cardStyles from "../exerciseCards.module.css";
import { useAuth } from "../../../lib/auth";
import { readLast, readProgress, writeLast, writeProgress } from "../../../lib/programProgress";
import { type Program, type ScheduledDay, WEEKS, minutesRange } from "../programsData";
import { useProgramPrescription } from "../useProgramPrescription";

type Props = { program: Program; days: ScheduledDay[] };
type View = "daily" | "list";

const todayISO = () => new Date().toISOString().slice(0, 10);

export default function ProgramView({ program, days: templateDays, }: Props) {
  const { user, loading: authLoading } = useAuth();
  const { days, baseline, loading: baselineLoading, error: baselineError } = 
    useProgramPrescription(program, templateDays, user?.id ?? null, authLoading);
  
    const uid = user?.id ?? "guest"; // progress is stored per user, so two people on one browser do not mix
  const [view, setView] = useState<View>("daily");
  const [selected, setSelected] = useState(1);
  const [weekFilter, setWeekFilter] = useState<number | "all">(1);
  const [done, setDone] = useState<Record<number, string>>({}); // day number -> completed date
  const [checked, setChecked] = useState<Record<string, boolean>>({}); // exercise key -> done
  const [date, setDate] = useState(todayISO());
  const [showMore, setShowMore] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const stripRef = useRef<HTMLDivElement>(null);

  // Load this user's progress and restore the day/view they were on last time in this program.
  useEffect(() => {
    if (authLoading) return;
    const s = readProgress(uid, program.slug);
    setDone(s.done); setChecked(s.checked);
    const last = readLast(uid);
    if (last && last.slug === program.slug) {
      setSelected(Math.min(Math.max(1, last.day), days.length));
      setView(last.view);
      setWeekFilter(last.week);
    }
    setLoaded(true);
  }, [authLoading, uid, program.slug, days.length]);

  useEffect(() => {
    if (!loaded) return;
    writeProgress(uid, program.slug, { done, checked });
  }, [done, checked, loaded, uid, program.slug]);

  // Remember the program tab the user is on, for "Continue where you left off".
  useEffect(() => {
    if (!loaded) return;
    writeLast(uid, { slug: program.slug, day: selected, view, week: weekFilter });
  }, [selected, view, weekFilter, loaded, uid, program.slug]);

  const day = days[selected - 1];
  const [minMin, maxMin] = useMemo(() => minutesRange(days), [days]);
  const completedCount = Object.keys(done).length;
  const core = day.exercises.filter((e) => e.role === "core");
  const optional = day.exercises.filter((e) => e.role === "accessory");

  function scrollStrip(dir: 1 | -1) {
    stripRef.current?.scrollBy({ left: dir * 280, behavior: "smooth" });
  }

  function toggleExercise(key: string) {
    setChecked((c) => ({ ...c, [key]: !c[key] }));
  }

  function markComplete() {
    setDone((d) => {
      const n = { ...d };
      if (n[day.number]) delete n[day.number];
      else n[day.number] = date;
      return n;
    });
  }

  function openDay(n: number) {
    setSelected(n);
    setView("daily");
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const listDays = days.filter((d) => weekFilter === "all" || d.week === weekFilter);
  const weeks = weekFilter === "all" ? [1, 2, 3, 4] : [weekFilter];
  
  if (authLoading || baselineLoading) { 
    return (
    <>
    <Navbar />
    <main className={styles.page}>
    <p className={styles.banner}>
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
    <main className={styles.page}>
    <p className={styles.banner} role="alert">
      {baselineError}
      </p>
      </main>
    </>
    );
  }

  if (user && !baseline) {
    return (
    <>
    <Navbar />
    <main className={styles.page}>
    <p className={styles.kicker}>
      Initial assessment required
      </p>
    
    <h1 className={styles.h1}>Establish your starting point.</h1>
      <p className={styles.lead}>
        Complete your {program.fullName} assessment
        before beginning training.
        </p>
        <Link
        href={`/assessment/${program.slug}`}
        className={styles.btnPrimary}
        >
          Take initial assessment →
          </Link>
    </main>
    </>
    );
  }


  return (
    <>
    <Navbar />
    <main className={styles.page}>
      <Link href="/programs" className={styles.back}>← All programs</Link>

      <div className={styles.layout}>
        {/* Left info card */}
        <aside className={styles.info}>
          <div className={styles.hero} aria-hidden="true">
            <span className={styles.heroCode}>{program.name}</span>
          </div>
          <dl className={styles.stats}>
            <div><dt>Duration</dt><dd>{WEEKS * 5} days</dd></div>
            <div><dt>Per day</dt><dd>{minMin}-{maxMin} min</dd></div>
          </dl>
          <p className={styles.equipLine}>
            <span className={styles.label}>Equipment</span>
            {program.equipment.join(" · ")}
          </p>
          <h2 className={styles.label}>Details</h2>
          <p className={styles.details}>
            {showMore ? program.description : program.description.slice(0, 90) + "..."}
            {" "}
            <button className={styles.linkBtn} onClick={() => setShowMore((s) => !s)}>
              {showMore ? "Show less" : "Read more"}
            </button>
          </p>
          <div style={{ margin: "20px 0" }}>
            <Link href={`/assessment/${program.slug}`} className={styles.back}>
            Take initial assessment →
            </Link>
            </div>
          <div className={styles.progressWrap}>
            <div className={styles.progressTop}>
              <span className={styles.label}>Progress</span>
              <span>{completedCount}/20 days</span>
            </div>
            <div className={styles.bar}><div className={styles.barFill} style={{ width: `${(completedCount / 20) * 100}%` }} /></div>
          </div>
        </aside>

        {/* Right content */}
        <section className={styles.content}>
          <div className={styles.titleRow}>
            <h1 className={styles.h1}>
              {program.name} <span className={styles.accent}>{program.fullName}</span>
            </h1>
            <div className={styles.toggle} role="tablist" aria-label="View">
              <button role="tab" aria-selected={view === "daily"} className={view === "daily" ? styles.toggleOn : ""} onClick={() => setView("daily")}>Daily</button>
              <button role="tab" aria-selected={view === "list"} className={view === "list" ? styles.toggleOn : ""} onClick={() => setView("list")}>List</button>
            </div>
          </div>

          {view === "daily" ? (
            <>
              <div className={styles.stripWrap}>
                <button className={styles.arrow} onClick={() => scrollStrip(-1)} aria-label="Scroll days left">‹</button>
                <div className={styles.strip} ref={stripRef}>
                  {days.map((d) => (
                    <button
                      key={d.number}
                      className={[
                        styles.dayTab,
                        d.number === selected ? styles.dayTabOn : "",
                        d.rest ? styles.dayTabRest : "",
                        done[d.number] ? styles.dayTabDone : "",
                      ].join(" ")}
                      onClick={() => setSelected(d.number)}
                      aria-current={d.number === selected}
                    >
                      {d.rest ? "Rest Day" : `Day ${d.number}`}
                      {done[d.number] && <span aria-label="completed"> ✓</span>}
                    </button>
                  ))}
                </div>
                <button className={styles.arrow} onClick={() => scrollStrip(1)} aria-label="Scroll days right">›</button>
              </div>

              <div className={styles.dayCard}>
                <div className={styles.dayHead}>
                  <p className={styles.kicker}>Week {day.week} · Day {day.number}</p>
                  <h2 className={styles.h2}>{day.rest ? "Rest Day" : `Day ${day.number}'s Workout`}</h2>
                  {!day.rest && (
                    <p className={styles.meta}>
                      {day.title} · {day.exercises.length} Workouts | {day.totalMinutes} Mins Total ({day.coreMinutes} Mins + {day.optionalMinutes} Mins Optional)
                    </p>
                  )}
                </div>

                {day.rest ? (
                  <div className={styles.restBox}>
                    <p>Recovery is part of the plan. Walk, stretch or sleep well. Your next workout is Day {day.number + 1 <= 28 ? day.number + 1 : day.number}.</p>
                  </div>
                ) : (
                  <ol className={styles.timeline}>
                    {core.map((e) => <TimelineItem key={e.key} e={e} checked={!!checked[e.key]} onToggle={() => toggleExercise(e.key)} slug={program.slug} />)}
                    <li className={styles.pillRow}><span className={styles.pillDone}>Workout Complete</span></li>
                    {optional.length > 0 && <li className={styles.pillRow}><span className={styles.pillOpt}>Optional</span></li>}
                    {optional.map((e) => <TimelineItem key={e.key} e={e} checked={!!checked[e.key]} onToggle={() => toggleExercise(e.key)} slug={program.slug} optional />)}
                  </ol>
                )}

                {!day.rest && (
                  <div className={styles.completeRow}>
                    <label className={styles.dateLabel}>
                      <span className={styles.label}>Completed on</span>
                      <input type="date" value={done[day.number] ?? date} disabled={!!done[day.number]} onChange={(e) => setDate(e.target.value)} />
                    </label>
                    <button className={done[day.number] ? styles.btnGhost : styles.btnPrimary} onClick={markComplete}>
                      {done[day.number] ? `Unmark Day ${day.number}` : `Mark Day ${day.number} As Complete`}
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            <>
              <div className={styles.pills}>
                {[1, 2, 3, 4].map((w) => (
                  <button key={w} className={weekFilter === w ? styles.pillOn : styles.pill} onClick={() => setWeekFilter(w)}>WEEK {w}</button>
                ))}
                <button className={weekFilter === "all" ? styles.pillOn : styles.pill} onClick={() => setWeekFilter("all")}>VIEW ALL</button>
              </div>
              <p className={styles.banner}>
                This list view is an overview for planning purposes. Go back to{" "}
                <button className={styles.linkBtn} onClick={() => setView("daily")}>Daily View</button> to train.
              </p>

              {weeks.map((w) => (
                <div key={w}>
                  {weekFilter === "all" && <h3 className={styles.weekHead}>Week {w}</h3>}
                  <div className={styles.listGrid}>
                    {listDays.filter((d) => d.week === w).map((d) =>
                      d.rest ? (
                        <div key={d.number} className={`${styles.listCard} ${styles.listRest}`}>
                          <h4>Day {d.number}</h4>
                          <p className={styles.restTitle}>Rest Day</p>
                          <p className={styles.metaSmall}>Recover and stretch lightly</p>
                        </div>
                      ) : (
                        <div key={d.number} className={`${styles.listCard} ${cardStyles.listCardLive}`}>
                          <button className={cardStyles.listOpen} onClick={() => openDay(d.number)}>
                            <h4>Day {d.number}{done[d.number] && <span className={styles.tick}> ✓</span>}</h4>
                            <p className={styles.metaSmall}>{d.exercises.length} Workouts | {d.totalMinutes} Mins · {d.title}</p>
                          </button>
                          <div className={styles.thumbs}>
                            {d.exercises.map((e) => (
                              <Link key={e.key} href={`/programs/${program.slug}/exercise/${e.key}`} className={`${styles.thumb} ${cardStyles.thumbBtn}`} title={`Open ${e.exercise.name}`}
                                aria-label={`Open ${e.exercise.name} workout page`}>
                                {e.exercise.name.split(" ").map((s) => s[0]).join("").slice(0, 2)}
                              </Link>
                            ))}
                          </div>
                        </div>
                      )
                    )}
                  </div>
                </div>
              ))}
            </>
          )}
        </section>
      </div>
    </main>
    </>
  );
}

type Ex = ScheduledDay["exercises"][number];

function TimelineItem({ e, checked, onToggle, slug, optional }: {
  e: Ex; checked: boolean; onToggle: () => void; slug: string; optional?: boolean;
}) {
  const router = useRouter();
  const open = () => router.push(`/programs/${slug}/exercise/${e.key}`);
  return (
    <li className={styles.tItem}>
      <button className={checked ? styles.markerOn : styles.marker} onClick={onToggle} aria-pressed={checked} aria-label={`Mark ${e.exercise.name} done`}>
        {checked ? "✓" : ""}
      </button>
      {/* The whole card opens this exercise's own workout page. */}
      <div className={`${styles.workoutCard} ${cardStyles.cardClickable}`} role="link" tabIndex={0}
        aria-label={`Open ${e.exercise.name} workout page`}
        onClick={open}
        onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); open(); } }}>
        <div className={styles.cardThumb} aria-hidden="true">
          {e.exercise.name.split(" ").map((s) => s[0]).join("").slice(0, 2)}
          <span className={styles.badge}>{e.minutes} min</span>
          <span className={cardStyles.play}>▶</span>
        </div>
        <div className={styles.cardBody}>
          <h3>{e.exercise.name}{optional && <span className={styles.optTag}> optional</span>}</h3>
          <p>{e.reps === 0 ? "Regression required" : 
            `${e.sets} sets x ${e.reps} ${e.exercise.id === "plank" ? "sec" : "reps"}`
            } {" . "}
            {e.exercise.muscle}
          </p>
          <p className={styles.equip}>{e.exercise.equipment}</p>
        </div>
        <span className={styles.info2} aria-hidden="true">→</span>
      </div>
    </li>
  );
}
