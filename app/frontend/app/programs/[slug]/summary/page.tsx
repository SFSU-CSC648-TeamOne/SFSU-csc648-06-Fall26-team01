"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Navbar from "../../../../components/Navbar";
import { useAuth } from "../../../../lib/auth";
import { readProgress, TOTAL_DAYS } from "../../../../lib/programProgress";
import { getProgram, buildSchedule } from "../../programsData";
import styles from "../../programs.module.css";

export default function ProgramSummaryPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const { user, loading } = useAuth();

  const program = getProgram(slug);
  const days = program ? buildSchedule(program) : [];

  const [done, setDone] = useState<Record<number, string>>({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (loading) return;

    const progress = readProgress(user?.id ?? "guest", slug);
    setDone(progress.done);
    setLoaded(true);
  }, [loading, user?.id, slug]);

  if (!program) {
    return (
      <main className={styles.page}>
        <Navbar />
        <p className={styles.banner}>Program not found.</p>
      </main>
    );
  }

  if (loading || !loaded) {
    return (
      <main className={styles.page}>
        <Navbar />
        <p className={styles.banner}>Loading your program summary...</p>
      </main>
    );
  }

  const workoutDays = days.filter((day) => !day.rest);
  const completedDays = workoutDays.filter((day) => !!done[day.number]);
  const percent = Math.round((completedDays.length / TOTAL_DAYS) * 100);

  return (
    <>
      <Navbar />

      <main className={styles.page}>
        <div style={{ maxWidth: 900, margin: "0 auto", padding: "30px 20px" }}>
          <Link href={`/programs/${slug}`} className={styles.back}>
            ← Back to Program
          </Link>

          <p className={styles.kicker}>PROGRAM COMPLETION</p>

          <h1 className={styles.h1}>
            {program.name} <span>{percent === 100 ? "Complete." : "Summary."}</span>
          </h1>

          <div
            style={{
              padding: 24,
              margin: "24px 0",
              borderRadius: 16,
              background: "var(--card, #252b38)",
            }}
          >
            <h2>{completedDays.length} / {TOTAL_DAYS} workout days completed</h2>

            <div
              style={{
                height: 12,
                background: "rgba(255,255,255,0.12)",
                borderRadius: 20,
                overflow: "hidden",
                marginTop: 16,
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${percent}%`,
                  background: "var(--lime, #b6f36b)",
                  transition: "width 0.3s ease",
                }}
              />
            </div>

            <p style={{ marginTop: 12 }}>
              {percent}% complete
            </p>

            {percent === 100 && (
              <h3 style={{ marginTop: 20 }}>
                Congratulations! You completed the {program.fullName}.
              </h3>
            )}
          </div>

          <h2 style={{ marginBottom: 16 }}>Workout History</h2>

          {workoutDays.map((day) => (
            <div
              key={day.number}
              style={{
                padding: 18,
                marginBottom: 12,
                borderRadius: 12,
                background: "var(--card, #252b38)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 16,
                flexWrap: "wrap",
              }}
            >
              <div>
                <strong>Day {day.number} — {day.title}</strong>
                <p style={{ marginTop: 6, opacity: 0.7 }}>
                  Week {day.week}
                </p>
              </div>

              <div style={{ textAlign: "right" }}>
                {done[day.number] ? (
                  <>
                    <strong>Completed ✓</strong>
                    <p style={{ marginTop: 6, opacity: 0.7 }}>
                      {done[day.number]}
                    </p>
                  </>
                ) : (
                  <span style={{ opacity: 0.65 }}>Not completed</span>
                )}
              </div>
            </div>
          ))}

          <div style={{ marginTop: 24 }}>
            <Link href={`/programs/${slug}`} className={styles.btnPrimary}>
              Return to Program
            </Link>
          </div>
        </div>
      </main>
    </>
  );
}