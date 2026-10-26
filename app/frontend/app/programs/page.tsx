"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";

type Program = {
    id: number;
    name: string;
    goal: string;
    experience_level: string;
    length_weeks: number;
    description: string | null;
};

export default function ProgramsPage() {
    const [programs, setPrograms] = useState<Program[]>([]);
    const [total, setTotal] = useState(0);
    const [goal, setGoal] = useState("");
    const [maxWeeks, setMaxWeeks] = useState("");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    // any filter change will load new programs
    useEffect(() => {
        const params = new URLSearchParams();
        if (goal.trim()) params.set("goal", goal.trim());
        if (maxWeeks) params.set("max_weeks", maxWeeks);

        setLoading(true);
        setError("");
        api(`/programs?${params.toString()}`)
        .then((data) => {
            setPrograms(data.items);
            setTotal(data.total);
        })
        .catch((e) => setError(e instanceof Error ? e.message : "Could not load programs"))
        .finally(() => setLoading(false));
    }, [goal, maxWeeks]);

    return (
        <main className="site">
            <header className="navbar">
                <Link href="/" className="logo">
                    <span className="logo-symbol">A</span>
                    ASCENDA
                </Link>
                <Link href="/" className="nav-button">
                    BACK TO HOME
                </Link>
            </header>

            <section className="intro">
                <span className="section-number">PROGRAMS</span>
                <h2>
                    TRAINING
                    <br />
                    <span>PROGRAMS</span>
                </h2>
                <p>Programs curated from exercise data. Filter by goal or length</p>

                {/* lets user type in a goal to filter */}
                <div className="program-filters">
                    <label htmlFor="goal">GOAL</label>
                    <input
                        id="goal"
                        type="text"
                        placeholder="ex: fitness"
                        value={goal}
                        onChange={(e) => setGoal(e.target.value)}
                    />
    
                {/* max weeks from wger is 4 */}
                <label htmlFor="max-weeks">MAX WEEKS</label>
                <input
                    id="max-weeks"
                    type="number"
                    min={1}
                    placeholder="ex: 4"
                    value={maxWeeks}
                    onChange={(e) => setMaxWeeks(e.target.value)}
                    />
                </div>

                {loading && <p>Loading programs</p>}
                {error && <p className="form-error">{error}</p>}
            {!loading && !error && (
                <p className="program-count">
                    {total} program{total == 1 ? "" : "s"} found
                </p>
            )}

            <div className="program-list">
                {programs.map((p) => (
                    <article key={p.id} className="program-card">
                        <h3>{p.name}</h3>
                        <p>
                            {p.goal} - {p.experience_level} - {p.length_weeks} week
                            {p.length_weeks == 1 ? "" : "s"}
                        </p>
                        {p.description && <p>{p.description}</p>}
                        <Link href="/workouts">View Workouts</Link>
                    </article>
                ))}
            </div>

            {!loading && !error && programs.length === 0 && (
                <p>No current programs match selected filters</p>
            )}
            </section>
        </main>
    );
}