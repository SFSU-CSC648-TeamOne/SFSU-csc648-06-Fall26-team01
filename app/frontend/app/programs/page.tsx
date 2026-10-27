"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";
import { addSavedProgram, readSavedPrograms } from "../lib/savedPrograms";

type Program = {
    id: number;
    name: string;
    goal: string;
    experience_level: string;
    length_weeks: number;
    description: string | null;
};
type Session = {
    id: number;
    program_id: number;
    name: string;
    total_minutes: number;
    exercise_count: number;
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
    video_url: string | null;
};
type SessionDetail = Session & {
    guidance: string | null;
    exercises: SessionExercise[];
};
type ExerciseDetail = {
    id: number;
    description: string | null;
}
type Page<T> = { items: T[]; total: number}

// Uhm so backend has ordered workout sessions, but no week number or schedule.
// Group sessions in round-robin order by position in the returned list for preview only.

function groupIntoDisplayWeeks(sessions: Session[], weekCount: number) {
    const count = Math.max(1, weekCount);
    const weeks: Session[][] = Array.from({length: count}, () => []);
    sessions.forEach((session, index) => weeks[index & count].push(session));
    return weeks;
}

function exercisePrescription(ex: SessionExercise) {
    const sets = ex.sets == null ? "Sets not specified" : `${ex.sets} sets`;
    const reps = ex.reps == null ? null : `${ex.reps} reps`;
    const duration = ex.minutes > 0 ? `${ex.minutes} min` : null;
    return [sets, reps, duration].filter(Boolean).join(" - ");
}

function ExerciseRow({exercise}: {exercise: SessionExercise}) {
    const [open, setOpen] = useState(false);
    const [description, setDescription] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");


    async function toggleDemo() {
        if (open) {
            setOpen(false);
            return;
        }
        setOpen(true);
        if (description !== null) return;
        setLoading(true);
        setError("");
        try{
            const detail = (await api(`/exercises/${exercise.exercise_id}`)) as ExerciseDetail;
            setDescription(detail.description || "No exercise description is available... yet.");
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Could not load exercise details");
        } finally {
            setLoading(false);
        }
    }
    return (
        <li>
            <strong>{exercise.name}</strong> -- {exercisePrescription(exercise)}
            -- {exercise.role}
            {exercise.equipment.length > 0 && <> 
            -- {exercise.equipment.join(", ")}</>}{" "}
            <button type="button" onClick={toggleDemo} aria-expanded={open}>
                {open ? "Hide description / demo" : "Description / Demo"}
            </button>
            {open && (
                <div>
                    {loading && <p>Loading description...</p>}
                    {error && <p role="alert">{error}</p>}
                    {description && <p>{description.replace(/<[^>]*>/g, " " )}</p>}
                    {exercise.video_url ? (
                        <video controls preload="metadata" width="360" src={exercise.video_url}>
                            Your browser does not support video playback.
                        </video>
                    ) : (
                        <p>No video demonstration available for this exercise.</p>
                    )}
                </div>
            )}
        </li>
    );
}

function SessionRow({session}: {session: Session}) {
    const [open, setOpen] = useState(false);
    const [detail, setDetail] = useState<SessionDetail | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    async function toggleSession() {
        setOpen(true);
        if (detail) return;
        setLoading(true);
        setError("");
        try{
            setDetail((await api(`/workout-sessions/${sessionStorage.id}`)) as SessionDetail); // Gotta double check sessionStorage - Ian
        } catch (reason) {
            setError(reason instanceof Error ? reason.message : "Could not load session");
        } finally {
            setLoading(false);
        }
    }
    return (
        <li>
            <button type="button" onClick={toggleSession} aria-expanded={open}>
                {open ? "▾" : "▸"} {sessionStorage.name} — {sessionStorage.total_minutes} min, {sessionStorage.exercise_count} exercises
            </button>
            {open && (
                <div>
                {loading && <p>Loading exercises…</p>}
                {error && <p role="alert">{error}</p>}
                {detail?.guidance && <p>{detail.guidance}</p>}
                {detail && (
                    <ul>
                    {detail.exercises.map((exercise) => (
                        <ExerciseRow key={exercise.id} exercise={exercise} />
                    ))}
                    </ul>
                )}
                </div>
            )}
        </li>
    );
}
export default function ProgramsPage() {
    const [programs, setPrograms] = useState<Program[]>([]);
    const [sessions, setSessions] = useState<Session[]>([]);
    const [selectedProgram, setSelectedProgram] = useState<Program | null>(null);
    const [openWeeks, setOpenWeeks] = useState<number[]>([]);
    const [savedIds, setSavedIds] = useState<number[]>([]);
    const [menuOpen, setMenuOpen] = useState(false);
    const [filterOpen, setFilterOpen] = useState(false);
    const [duration, setDuration] = useState("");
    const [equipment, setEquipment] = useState("");
    const [loading, setLoading] = useState(true);
    const [sessionsLoading, setSessionsLoading] = useState(false);
    const [error, setError] = useState("");
    const [sessionError, setSessionError] = useState("");

  useEffect(() => {
    setSavedIds(readSavedPrograms().map((item) => item.id));
    let cancelled = false;
    // Request enough programs to show multiple choices when present.
    api("/programs?limit=100")
      .then((page: Page<Program>) => {
        if (!cancelled) setPrograms(page.items);
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "Could not load programs");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!programs.length || typeof window === "undefined") return;
    const match = /^#program-(\d+)$/.exec(window.location.hash);
    if (!match) return;
    const program = programs.find((item) => item.id === Number(match[1]));
    if (program && selectedProgram?.id !== program.id) void chooseProgram(program);
    // Select a program after loading the list from a profile shortcut.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [programs]);

  async function chooseProgram(program: Program) {
    if (selectedProgram?.id === program.id) {
      setSelectedProgram(null);
      return;
    }
    setSelectedProgram(program);
    setOpenWeeks([]);
    setSessions([]);
    setSessionError("");
    setSessionsLoading(true);
    try {
      // Backend exposes all sessions globally; join by the returned program_id.
      const page = (await api("/workout-sessions?limit=100")) as Page<Session>;
      setSessions(page.items.filter((session) => session.program_id === program.id));
      if (page.total > page.items.length) {
        setSessionError("Only the first 100 sessions were loaded; additional sessions may be missing.");
      }
    } catch (reason) {
      setSessionError(reason instanceof Error ? reason.message : "Could not load program sessions");
    } finally {
      setSessionsLoading(false);
    }
  }

  function saveProgram(program: Program) {
    try {
      addSavedProgram({ id: program.id, name: program.name });
      setSavedIds(readSavedPrograms().map((item) => item.id));
    } catch {
      setError("This browser could not save your program shortcut.");
    }
  }

  const weeks = selectedProgram ? groupIntoDisplayWeeks(sessions, selectedProgram.length_weeks) : [];

  return (
    <main>
      <header>
        <button type="button" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation" aria-expanded={menuOpen}>☰ Menu</button>{" "}
        <Link href="/">ASCENDA</Link>
        {menuOpen && (
          <nav aria-label="Site pages">
            <ul>
              <li><Link href="/">Home</Link></li>
              <li><Link href="/profile">Profile</Link></li>
              <li><Link href="/programs">Programs</Link></li>
              <li><Link href="/search">Exercises</Link></li>
            </ul>
          </nav>
        )}
      </header>

      <h1>Program Library</h1>
      <button type="button" onClick={() => setFilterOpen(!filterOpen)} aria-expanded={filterOpen}>Filters (placeholder)</button>
      {filterOpen && (
        <div>
          <label htmlFor="program-duration">Duration (weeks)</label>{" "}
          <select id="program-duration" value={duration} onChange={(event) => setDuration(event.target.value)}>
            <option value="">Any duration</option>
            <option value="4">Up to 4 weeks</option>
            <option value="8">Up to 8 weeks</option>
            <option value="12">Up to 12 weeks</option>
          </select>{" "}
          <label htmlFor="program-equipment">Equipment tags</label>{" "}
          <input id="program-equipment" value={equipment} onChange={(event) => setEquipment(event.target.value)} placeholder="Equipment search (coming soon)" disabled />
          <p>Equipment filtering is awaiting a program-level backend filter. Duration is preview-only.</p>
        </div>
      )}
      {loading && <p>Loading programs…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && programs.length < 2 && <p>Only {programs.length} program(s) are available in the database. At least two seeded programs are needed for the milestone demonstration.</p>}

      <section aria-label="Available programs">
        {programs.filter((program) => !duration || program.length_weeks <= Number(duration)).map((program) => (
          <article key={program.id}>
            <h2>{program.name}</h2>
            <p>{program.goal} — {program.experience_level} — {program.length_weeks} weeks</p>
            {program.description && <p>{program.description}</p>}
            <button type="button" onClick={() => chooseProgram(program)} aria-expanded={selectedProgram?.id === program.id}>
              {selectedProgram?.id === program.id ? "Close overview" : "View program overview"}
            </button>{" "}
            <button type="button" onClick={() => saveProgram(program)} disabled={savedIds.includes(program.id)}>
              {savedIds.includes(program.id) ? "Added to profile" : "Add program to profile"}
            </button>
          </article>
        ))}
      </section>

      {selectedProgram && (
        <section id={`program-${selectedProgram.id}`} aria-label={`${selectedProgram.name} overview`}>
          <h2>{selectedProgram.name} — Overview</h2>
          <p>{selectedProgram.description || "No overview description available."}</p>
          <p>Goal: {selectedProgram.goal} | Level: {selectedProgram.experience_level} | Duration: {selectedProgram.length_weeks} weeks</p>
          <p>Week grouping is a preview: the backend currently stores session order, not session-to-week assignments.</p>
          {sessionsLoading && <p>Loading sessions…</p>}
          {sessionError && <p role="alert">{sessionError}</p>}
          {!sessionsLoading && sessions.length === 0 && <p>No sessions are currently assigned to this program.</p>}
          {!sessionsLoading && sessions.length > 0 && weeks.map((weekSessions, index) => (
            <section key={index}>
              <h3>
                <button type="button" onClick={() => setOpenWeeks((current) => current.includes(index) ? current.filter((week) => week !== index) : [...current, index])} aria-expanded={openWeeks.includes(index)}>
                  {openWeeks.includes(index) ? "▾" : "▸"} Week {index + 1} ({weekSessions.length} sessions)
                </button>
              </h3>
              {openWeeks.includes(index) && (weekSessions.length ? (
                <ul>{weekSessions.map((session) => <SessionRow key={session.id} session={session} />)}</ul>
              ) : <p>No sessions assigned in this preview week.</p>)}
            </section>
          ))}
        </section>
      )}
    </main>
  );
}
