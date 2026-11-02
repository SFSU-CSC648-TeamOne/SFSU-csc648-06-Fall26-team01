"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import styles from "./programs.module.css";
import { api } from "../lib/api";
import { addSavedProgram, readSavedPrograms } from "../lib/savedPrograms";

// Program library and program view (design from public/Demo/demo.html), backed by the API:
//   GET  /programs                  -> program picker
//   GET  /workout-sessions          -> sessions per program (ordered by position)
//   GET  /workout-sessions/{id}     -> exercises for each training day
//   GET  /exercises/{id}            -> description shown by the "i" button
//   GET  /workout-records           -> restores which days are already done
//   POST /workout-records           -> "Mark Day N As Complete"
//
// The backend stores an ordered list of sessions per program but no week/day schedule,
// so buildSchedule() lays the sessions out over the program's weeks on the frontend.

type Program = {
    id: number;
    name: string;
    goal: string;
    experience_level: string;
    length_weeks: number;
    description: string | null;
};
type SessionSummary = {
    id: number;
    name: string;
    program_id: number;
    total_minutes: number;
    exercise_count: number;
    muscle_groups: string[];
};
type SessionExercise = {
    id: number;
    exercise_id: number;
    name: string;
    role: string;
    sets: number | null;
    reps: number | null;
    minutes: number;
    equipment: string[];
    primary_muscles: string[];
    video_url: string | null;
};
type SessionDetail = SessionSummary & { guidance: string | null; exercises: SessionExercise[] };
type ExerciseDetail = { id: number; description: string | null };
type RecordSummary = { id: number; workout_session_id: number | null; performed_at: string };
type Page<T> = { items: T[]; total: number };

type Day = { week: number; day: number; number: number; rest: boolean; sessionId: number | null };

const ini = (name: string) => name.split(/\s+/).filter(Boolean).map((s) => s[0].toUpperCase()).join("").slice(0, 3);
const cx = (...names: (string | false | undefined)[]) => names.filter(Boolean).join(" ");
const today = () => new Date().toISOString().slice(0, 10);
const errorText = (reason: unknown, fallback: string) => (reason instanceof Error ? reason.message : fallback);
const isLoggedIn = () => typeof window !== "undefined" && Boolean(localStorage.getItem("token"));

// Endpoints cap limit at 100, so page through until everything is loaded.
async function fetchAll<T>(path: string): Promise<T[]> {
    const sep = path.includes("?") ? "&" : "?";
    const items: T[] = [];
    for (let offset = 0; ; offset += 100) {
        const page = (await api(`${path}${sep}limit=100&offset=${offset}`)) as Page<T>;
        items.push(...page.items);
        if (page.items.length === 0 || items.length >= page.total) return items;
    }
}

// 5 training days + 2 rest days a week (more training days if there are more sessions
// than slots, up to 7). Sessions repeat in order when the program has fewer than the slots.
function buildSchedule(sessions: SessionSummary[], weeks: number): Day[] {
    const count = Math.max(1, weeks);
    const perWeek = Math.min(7, Math.max(5, Math.ceil(sessions.length / count)));
    const days: Day[] = [];
    let k = 0;
    for (let week = 1; week <= count; week++) {
        for (let day = 1; day <= 7; day++) {
            const training = day <= perWeek && sessions.length > 0;
            days.push({
                week, day, number: (week - 1) * 7 + day, rest: !training,
                sessionId: training ? sessions[k++ % sessions.length].id : null,
            });
        }
    }
    return days;
}

function minuteRange(minutes: number[]) {
    if (minutes.length === 0) return "—";
    const lo = Math.min(...minutes), hi = Math.max(...minutes);
    return lo === hi ? `${lo}` : `${lo}-${hi}`;
}

function prescription(e: SessionExercise) {
    const sets = e.sets ?? "—";
    return e.reps == null ? `${sets} sets` : `${sets} sets × ${e.reps} reps`;
}

function Picker({ onOpen }: { onOpen: (program: Program, sessions: SessionSummary[]) => void }) {
    const [programs, setPrograms] = useState<Program[]>([]);
    const [sessions, setSessions] = useState<SessionSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        Promise.all([fetchAll<Program>("/programs"), fetchAll<SessionSummary>("/workout-sessions")])
            .then(([p, s]) => { setPrograms(p); setSessions(s); })
            .catch((reason) => setError(errorText(reason, "Could not load programs")))
            .finally(() => setLoading(false));
    }, []);

    return (
        <main className={styles.page}>
            <header className={styles.pageHead}>
                <p className={styles.kicker}>Programs</p>
                <h1 className={styles.h1}>Pick your <span className={styles.accent}>program.</span></h1>
                <p className={styles.lead}>Each program combines its workout sessions into training days across its weeks.</p>
            </header>
            {loading && <p className={styles.banner}>Loading programs…</p>}
            {error && <p className={cx(styles.banner, styles.error)} role="alert">{error}</p>}
            {!loading && !error && programs.length === 0 && <p className={styles.banner}>No programs are in the database yet.</p>}
            <ul className={styles.cardGrid}>
                {programs.map((p) => {
                    const own = sessions.filter((s) => s.program_id === p.id);
                    const trainingDays = buildSchedule(own, p.length_weeks).filter((d) => !d.rest).length;
                    return (
                        <li key={p.id}>
                            <a className={styles.programCard} href="#" onClick={(e) => { e.preventDefault(); onOpen(p, own); }}>
                                <span className={styles.programCode}>{ini(p.name)}</span>
                                <span className={styles.programName}>{p.name}</span>
                                <span className={styles.programTag}>{p.goal} · {p.experience_level}</span>
                                <span className={styles.chips}>
                                    <span className={styles.chip}>{p.length_weeks} weeks</span>
                                    <span className={styles.chip}>{trainingDays} workouts</span>
                                    <span className={styles.chip}>{minuteRange(own.map((s) => s.total_minutes))} min/day</span>
                                    <span className={styles.chip}>{own.length} sessions</span>
                                </span>
                                <span className={styles.cta}>View program →</span>
                            </a>
                        </li>
                    );
                })}
            </ul>
        </main>
    );
}

function TimelineItem({ e, optional, checked, onToggle }: { e: SessionExercise; optional?: boolean; checked: boolean; onToggle: () => void }) {
    const [open, setOpen] = useState(false);
    const [description, setDescription] = useState<string | null>(null);
    const [error, setError] = useState("");

    async function toggleInfo() {
        setOpen(!open);
        if (open || description !== null) return;
        try {
            const detail = (await api(`/exercises/${e.exercise_id}`)) as ExerciseDetail;
            // wger descriptions contain HTML
            setDescription(detail.description?.replace(/<[^>]*>/g, " ").trim() || "No description available yet.");
        } catch (reason) {
            setError(errorText(reason, "Could not load exercise details"));
        }
    }

    return (
        <>
            <li className={styles.tItem}>
                <button type="button" className={checked ? styles.markerOn : styles.marker} onClick={onToggle} aria-pressed={checked} aria-label={`Done: ${e.name}`}>
                    {checked ? "✓" : ""}
                </button>
                <div className={styles.workoutCard}>
                    <div className={styles.cardThumb}>
                        {ini(e.name)}
                        <span className={styles.badge}>{e.minutes} min</span>
                    </div>
                    <div className={styles.cardBody}>
                        <h3>{e.name}{optional && <> <span className={styles.optTag}>optional</span></>}</h3>
                        <p>{prescription(e)}{e.primary_muscles.length > 0 && ` · ${e.primary_muscles.join(", ")}`}</p>
                        <p className={styles.equip}>{e.equipment.length ? e.equipment.join(", ") : "No equipment"}</p>
                    </div>
                    <button type="button" className={styles.info2} onClick={toggleInfo} aria-expanded={open} aria-label={`About ${e.name}`}>i</button>
                </div>
            </li>
            {open && (
                <li className={styles.infoPanel}>
                    {error ? <span className={styles.error}>{error}</span> : <span>{description ?? "Loading…"}</span>}
                    {e.video_url && (
                        <video controls preload="metadata" src={e.video_url}>Your browser does not support video playback.</video>
                    )}
                </li>
            )}
        </>
    );
}

function ProgramView({ program: p, sessions, onHome }: { program: Program; sessions: SessionSummary[]; onHome: () => void }) {
    const days = useMemo(() => buildSchedule(sessions, p.length_weeks), [sessions, p.length_weeks]);
    const trainingDays = days.filter((x) => !x.rest);
    const weekNumbers = Array.from(new Set(days.map((x) => x.week)));

    const [details, setDetails] = useState<Record<number, SessionDetail>>({});
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState("");
    const [view, setView] = useState<"daily" | "list">("daily");
    const [sel, setSel] = useState(1);
    const [wk, setWk] = useState<number | "all">(1);
    const [done, setDone] = useState<Record<number, string>>({});
    const [checked, setChecked] = useState<Record<string, boolean>>({});
    const [showMore, setShowMore] = useState(false);
    const [date, setDate] = useState(today);
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState("");
    const [loggedIn, setLoggedIn] = useState(false);
    const [saved, setSaved] = useState(false);
    const stripRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        setSaved(readSavedPrograms().some((item) => item.id === p.id));
    }, [p.id]);

    // Load every session's exercises (needed for the list-view thumbnails too).
    useEffect(() => {
        Promise.all(sessions.map((s) => api(`/workout-sessions/${s.id}`) as Promise<SessionDetail>))
            .then((list) => setDetails(Object.fromEntries(list.map((d) => [d.id, d]))))
            .catch((reason) => setLoadError(errorText(reason, "Could not load workout sessions")))
            .finally(() => setLoading(false));
    }, [sessions]);

    // Restore progress from the user's workout history. Records only know their session, so
    // the k-th record for a session fills that session's k-th scheduled day.
    useEffect(() => {
        setLoggedIn(isLoggedIn());
        if (!isLoggedIn()) return;
        fetchAll<RecordSummary>("/workout-records")
            .then((records) => {
                const restored: Record<number, string> = {};
                [...records]
                    .sort((a, b) => a.performed_at.localeCompare(b.performed_at))
                    .forEach((r) => {
                        const slot = trainingDays.find((d) => d.sessionId === r.workout_session_id && !restored[d.number]);
                        if (slot) restored[slot.number] = r.performed_at.slice(0, 10);
                    });
                setDone(restored);
            })
            .catch(() => setLoggedIn(false)); // expired token: treat as logged out
    }, [days]);

    // Keep the selected day tab visible when switching days or coming back from list view.
    useEffect(() => {
        stripRef.current?.querySelector(`[data-day="${sel}"]`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
    }, [sel, view]);

    const d = days[sel - 1];
    const detail = d.sessionId != null ? details[d.sessionId] : undefined;
    const exercises = detail?.exercises ?? [];
    const core = exercises.filter((e) => e.role === "core");
    const opt = exercises.filter((e) => e.role !== "core");
    const sum = (list: SessionExercise[]) => list.reduce((t, e) => t + e.minutes, 0);
    const n = Object.keys(done).length;
    const isDone = Boolean(done[d.number]);
    const checkKey = (e: SessionExercise) => `${d.number}-${e.id}`;
    const equipment = Array.from(new Set(Object.values(details).flatMap((s) => s.exercises.flatMap((e) => e.equipment)))).sort();
    const description = p.description || "No program description available yet.";

    // Saved programs are listed on /profile (stored in this browser, not the backend).
    function saveProgram() {
        addSavedProgram({ id: p.id, name: p.name });
        setSaved(true);
    }

    function toggleCheck(key: string) {
        setChecked((c) => ({ ...c, [key]: !c[key] }));
    }

    async function markComplete() {
        if (!detail) return;
        setSaving(true);
        setSaveError("");
        // Checked exercises are completed, the rest skipped. If nothing was ticked,
        // treat the whole session as completed.
        const anyChecked = exercises.some((e) => checked[checkKey(e)]);
        const completed = exercises.filter((e) => !anyChecked || checked[checkKey(e)]);
        try {
            await api("/workout-records", {
                method: "POST",
                body: JSON.stringify({
                    workout_session_id: detail.id,
                    performed_at: new Date(`${date}T12:00:00`).toISOString(),
                    duration_minutes: Math.max(1, sum(completed)),
                    entries: exercises.map((e) => ({
                        exercise_id: e.exercise_id,
                        reps: e.reps,
                        status: completed.includes(e) ? "completed" : "skipped",
                    })),
                }),
            });
            setDone((cur) => ({ ...cur, [d.number]: date }));
        } catch (reason) {
            setSaveError(errorText(reason, "Could not save workout"));
        } finally {
            setSaving(false);
        }
    }

    function goToDay(number: number) {
        setSel(number);
        setView("daily");
    }

    const daily = (
        <>
            <div className={styles.stripWrap}>
                <button type="button" className={styles.arrow} aria-label="Scroll days left" onClick={() => stripRef.current?.scrollBy({ left: -280, behavior: "smooth" })}>‹</button>
                <div className={styles.strip} ref={stripRef}>
                    {days.map((x) => (
                        <button
                            type="button"
                            key={x.number}
                            data-day={x.number}
                            className={cx(styles.dayTab, x.number === sel && styles.dayTabOn, x.rest && styles.dayTabRest, done[x.number] && styles.dayTabDone)}
                            onClick={() => setSel(x.number)}
                        >
                            {x.rest ? "Rest Day" : `Day ${x.number}`}{done[x.number] ? " ✓" : ""}
                        </button>
                    ))}
                </div>
                <button type="button" className={styles.arrow} aria-label="Scroll days right" onClick={() => stripRef.current?.scrollBy({ left: 280, behavior: "smooth" })}>›</button>
            </div>

            <div className={styles.dayCard}>
                <div className={styles.dayHead}>
                    <p className={styles.kicker}>Week {d.week} · Day {d.number}</p>
                    <h2 className={styles.h2}>{d.rest ? "Rest Day" : `Day ${d.number}'s Workout`}</h2>
                    {detail && (
                        <p className={styles.meta}>
                            {detail.name} · {exercises.length} Workouts | {detail.total_minutes} Mins Total ({sum(core)} Mins + {sum(opt)} Mins Optional)
                        </p>
                    )}
                    {detail?.guidance && <p className={styles.meta}>{detail.guidance}</p>}
                </div>

                {d.rest ? (
                    <div className={styles.restBox}><p>Recovery is part of the plan. Walk, stretch or sleep well.</p></div>
                ) : loading ? (
                    <div className={styles.restBox}><p>Loading workout…</p></div>
                ) : !detail ? (
                    <div className={styles.restBox}><p className={styles.error}>{loadError || "This workout could not be loaded."}</p></div>
                ) : (
                    <>
                        <ol className={styles.timeline}>
                            {core.map((e) => <TimelineItem key={e.id} e={e} checked={!!checked[checkKey(e)]} onToggle={() => toggleCheck(checkKey(e))} />)}
                            <li className={styles.pillRow}><span className={styles.pillDone}>Workout Complete</span></li>
                            {opt.length > 0 && <li className={styles.pillRow}><span className={styles.pillOpt}>Optional</span></li>}
                            {opt.map((e) => <TimelineItem key={e.id} e={e} optional checked={!!checked[checkKey(e)]} onToggle={() => toggleCheck(checkKey(e))} />)}
                        </ol>
                        <div className={styles.completeRow}>
                            <label className={styles.dateLabel}>
                                <span className={styles.label}>Completed on</span>
                                <input type="date" value={done[d.number] || date} disabled={isDone || saving} onChange={(e) => setDate(e.target.value)} />
                            </label>
                            {isDone ? (
                                <button type="button" className={styles.btnGhost} disabled>Day {d.number} Logged ✓</button>
                            ) : (
                                <button type="button" className={styles.btnPrimary} onClick={markComplete} disabled={saving || !loggedIn}>
                                    {saving ? "Saving…" : `Mark Day ${d.number} As Complete`}
                                </button>
                            )}
                        </div>
                        {!loggedIn && !isDone && (
                            <p className={styles.saveNote}><Link href="/login">Log in</Link> to save completed workouts to your history.</p>
                        )}
                        {isDone && <p className={styles.saveNote}>Saved to your workout history.</p>}
                        {saveError && <p className={cx(styles.saveNote, styles.error)} role="alert">{saveError}</p>}
                    </>
                )}
            </div>
        </>
    );

    const weeks = wk === "all" ? weekNumbers : [wk];
    const list = (
        <>
            <div className={styles.pills}>
                {weekNumbers.map((i) => (
                    <button type="button" key={i} className={wk === i ? styles.pillOn : styles.pill} onClick={() => setWk(i)}>WEEK {i}</button>
                ))}
                <button type="button" className={wk === "all" ? styles.pillOn : styles.pill} onClick={() => setWk("all")}>VIEW ALL</button>
            </div>
            <p className={styles.banner}>
                This list view is an overview for planning purposes. Go back to{" "}
                <button type="button" className={styles.linkBtn} onClick={() => setView("daily")}>Daily View</button> to train.
            </p>
            {weeks.map((i) => (
                <div key={i}>
                    {wk === "all" && <h3 className={styles.weekHead}>Week {i}</h3>}
                    <div className={styles.listGrid}>
                        {days.filter((x) => x.week === i).map((x) => {
                            const s = x.sessionId != null ? details[x.sessionId] : undefined;
                            return x.rest ? (
                                <div key={x.number} className={cx(styles.listCard, styles.listRest)}>
                                    <h4>Day {x.number}</h4>
                                    <p className={styles.restTitle}>Rest Day</p>
                                    <p className={styles.metaSmall}>Recover and stretch lightly</p>
                                </div>
                            ) : (
                                <button type="button" key={x.number} className={styles.listCard} onClick={() => goToDay(x.number)}>
                                    <h4>Day {x.number}{done[x.number] && <> <span className={styles.tick}>✓</span></>}</h4>
                                    <p className={styles.metaSmall}>{s ? `${s.exercises.length} Workouts | ${s.total_minutes} Mins · ${s.name}` : "Loading…"}</p>
                                    <div className={styles.thumbs}>
                                        {s?.exercises.map((e) => <span key={e.id} className={styles.thumb}>{ini(e.name)}</span>)}
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>
            ))}
        </>
    );

    return (
        <main className={styles.page}>
            <a className={styles.back} href="#" onClick={(e) => { e.preventDefault(); onHome(); }}>← All programs</a>
            <div className={styles.layout}>
                <aside className={styles.info}>
                    <div className={styles.hero}><span className={styles.heroCode}>{ini(p.name)}</span></div>
                    <dl className={styles.stats}>
                        <div><dt>Duration</dt><dd>{trainingDays.length} days</dd></div>
                        <div><dt>Per day</dt><dd>{minuteRange(sessions.map((s) => s.total_minutes))} min</dd></div>
                        <div><dt>Level</dt><dd>{p.experience_level}</dd></div>
                        <div><dt>Goal</dt><dd>{p.goal}</dd></div>
                    </dl>
                    <p className={styles.equipLine}>
                        <span className={styles.label}>Equipment</span>
                        {loading ? "Loading…" : equipment.length ? equipment.join(" · ") : "No equipment"}
                    </p>
                    <h2 className={styles.label}>Details</h2>
                    <p className={styles.details}>
                        {showMore || description.length <= 90 ? description : description.slice(0, 90) + "..."}{" "}
                        {description.length > 90 && (
                            <button type="button" className={styles.linkBtn} onClick={() => setShowMore(!showMore)}>{showMore ? "Show less" : "Read more"}</button>
                        )}
                    </p>
                    <div className={styles.progressWrap}>
                        <div className={styles.progressTop}><span className={styles.label}>Progress</span><span>{n}/{trainingDays.length} days</span></div>
                        <div className={styles.bar}><div className={styles.barFill} style={{ width: `${trainingDays.length ? (n / trainingDays.length) * 100 : 0}%` }} /></div>
                    </div>
                    <button type="button" className={saved ? styles.btnGhost : styles.btnPrimary} onClick={saveProgram} disabled={saved}>
                        {saved ? "Added to profile ✓" : "Add program to profile"}
                    </button>
                </aside>

                <section className={styles.content}>
                    <div className={styles.titleRow}>
                        <h1 className={styles.h1}>{ini(p.name)} <span className={styles.accent}>{p.name}</span></h1>
                        <div className={styles.toggle}>
                            <button type="button" className={view === "daily" ? styles.toggleOn : undefined} onClick={() => setView("daily")}>Daily</button>
                            <button type="button" className={view === "list" ? styles.toggleOn : undefined} onClick={() => setView("list")}>List</button>
                        </div>
                    </div>
                    {sessions.length === 0
                        ? <p className={styles.banner}>No workout sessions are assigned to this program yet.</p>
                        : view === "daily" ? daily : list}
                </section>
            </div>
        </main>
    );
}

export default function ProgramsPage() {
    const [selected, setSelected] = useState<{ program: Program; sessions: SessionSummary[] } | null>(null);

    return (
        <div className={styles.root}>
            <header className={styles.top}>
                <span style={{ fontSize: 22 }}>☰</span>
                <b>ASCENDA</b>
                <nav>
                    <Link href="/">Home</Link>
                    <Link href="/search">Exercises</Link>
                    <Link href="/programs" className={styles.on}>Programs</Link>
                    <Link href="/history">Progress</Link>
                    <Link href="/profile">Profile</Link>
                </nav>
            </header>
            {/* key resets per-program state (selected day, completions) when switching programs */}
            {selected
                ? <ProgramView key={selected.program.id} program={selected.program} sessions={selected.sessions} onHome={() => setSelected(null)} />
                : <Picker onOpen={(program, sessions) => setSelected({ program, sessions })} />}
        </div>
    );
}
