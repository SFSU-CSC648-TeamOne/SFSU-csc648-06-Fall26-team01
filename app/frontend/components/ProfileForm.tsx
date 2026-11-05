"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, displayName, type User } from "../lib/auth";
import styles from "./ProfileForm.module.css";
import { useRouter } from "next/navigation"; // For redirect after saving profile and first-time setup.

// Matches GET/PUT /api/profile (user_profiles table). Equipment comes from GET /api/equipment as ids.
type Profile = {
  goals: string[]; experience_level: string | null; days_per_week: number | null;
  session_minutes: number | null; physical_constraints: string | null; equipment_ids: number[];
};
type Equipment = { id: number; name: string };
const EMPTY: Profile = { goals: [], experience_level: null, days_per_week: 4, session_minutes: 45, physical_constraints: null, equipment_ids: [] };

const GOALS = [
  { v: "Build strength", d: "Get stronger on the main lifts" },
  { v: "Build muscle", d: "Add size with higher volume" },
  { v: "Lose fat", d: "Burn more, keep your muscle" },
  { v: "Stay active", d: "Stay consistent and healthy" },
];
const LEVELS = [
  { v: "beginner", d: "New to training, or coming back" },
  { v: "intermediate", d: "Training regularly for 6+ months" },
  { v: "advanced", d: "Years of consistent training" },
];
const DAYS = [1, 2, 3, 4, 5, 6, 7];
const MINUTES = [20, 30, 45, 60, 90];
const LIMITS = ["Knee", "Lower back", "Shoulder", "Wrist"];

const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

type Props = { user: User | null; 
  kicker: string; 
  title: React.ReactNode; 
  lead: string; 
  submitLabel: string;
  afterSaveHref?: string; // redirect after saving profile (first-time setup)
  };

/** Full-page profile editor, used by Profile setup (first time) and Profile (edit later). */
export default function ProfileForm({ user, kicker, title, lead, submitLabel, afterSaveHref, }: Props) {
  const router = useRouter(); // For redirect after saving profile and first-time setup.
  const [p, setP] = useState<Profile>(EMPTY);
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [existing, setExisting] = useState(false); // a profile was already saved before
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [toast, setToast] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api<Equipment[]>("/equipment").then(setEquipment).catch(() => {});
    api<Profile>("/profile").then((r) => { setP({ ...EMPTY, ...r }); setExisting(true); }).catch(() => {}); // 404 = not set up yet
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, []);

  // limitations are stored as one comma-separated text (physical_constraints)
  const limits = (p.physical_constraints ?? "").split(",").map((x) => x.trim()).filter(Boolean);
  const setLimits = (l: string[]) => { setP({ ...p, physical_constraints: l.join(", ") || null }); setSaved(false); };
  const edit = (next: Profile) => { setP(next); setSaved(false); };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;

    setBusy(true); 
    setError("");
    
    try {
      await api("/profile", { method: "PUT", body: JSON.stringify(p), });
      setSaved(true); 
      setExisting(true); 

      if (afterSaveHref) {router.replace(afterSaveHref); return;} // Redirect after saving profile (first-time setup)

      setToast(true); 

      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setToast(false), 4000);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save Profile");
    } finally {
    setBusy(false);
    }
  }

  const eqNames = useMemo(() => equipment.filter((q) => p.equipment_ids.includes(q.id)).map((q) => q.name), [equipment, p.equipment_ids]);
  const filled = [p.goals.length > 0, !!p.experience_level, !!p.days_per_week, !!p.session_minutes, p.equipment_ids.length > 0].filter(Boolean).length;
  const name = displayName(user);

  const chip = (on: boolean, text: string, click: () => void) => (
    <button type="button" key={text} className={`${styles.chip} ${on ? styles.chipOn : ""}`} aria-pressed={on} onClick={click}>{text}</button>
  );

  return (
    <form className={styles.page} onSubmit={submit}>
      {toast && <div className={styles.toast} role="status"><span aria-hidden="true">✓</span> Profile updated</div>}

      <header className={styles.head}>
        <p className={styles.kicker}>{kicker}</p>
        <h1 className={styles.h1}>{title}</h1>
        <p className={styles.lead}>{lead}</p>
      </header>

      <div className={styles.grid}>
        {/* Left: live summary */}
        <aside className={styles.summary} aria-label="Profile summary">
          <div className={styles.avatar} aria-hidden="true">{(name || user?.email || "A").charAt(0).toUpperCase()}</div>
          <p className={styles.sumName}>{name || "Your profile"}</p>
          <p className={styles.sumMail}>{user?.email}</p>
          <div className={styles.meter}><span style={{ width: `${(filled / 5) * 100}%` }} /></div>
          <p className={styles.meterText}>{filled} of 5 sections filled</p>
          <dl className={styles.sumList}>
            <div><dt>Goal</dt><dd>{p.goals[0] ?? "Not set"}</dd></div>
            <div><dt>Level</dt><dd>{p.experience_level ?? "Not set"}</dd></div>
            <div><dt>Schedule</dt><dd>{p.days_per_week ?? "-"} days · {p.session_minutes ?? "-"} min</dd></div>
            <div><dt>Equipment</dt><dd>{eqNames.length ? eqNames.join(", ") : "Not set"}</dd></div>
            <div><dt>Limitations</dt><dd>{limits.length ? limits.join(", ") : "None"}</dd></div>
          </dl>
        </aside>

        {/* Right: form sections */}
        <div className={styles.sections}>
          <section className={styles.card}>
            <h2><span>01</span> Your goal</h2>
            <div className={styles.options}>
              {GOALS.map((g) => (
                <button type="button" key={g.v} className={`${styles.option} ${p.goals[0] === g.v ? styles.optionOn : ""}`}
                  aria-pressed={p.goals[0] === g.v} onClick={() => edit({ ...p, goals: [g.v] })}>
                  <b>{g.v}</b><small>{g.d}</small>
                </button>
              ))}
            </div>
          </section>

          <section className={styles.card}>
            <h2><span>02</span> Experience level</h2>
            <div className={styles.options3}>
              {LEVELS.map((l) => (
                <button type="button" key={l.v} className={`${styles.option} ${p.experience_level === l.v ? styles.optionOn : ""}`}
                  aria-pressed={p.experience_level === l.v} onClick={() => edit({ ...p, experience_level: l.v })}>
                  <b>{l.v}</b><small>{l.d}</small>
                </button>
              ))}
            </div>
          </section>

          <section className={styles.card}>
            <h2><span>03</span> Schedule</h2>
            <p className={styles.label}>Days per week</p>
            <div className={styles.seg} role="group" aria-label="Days per week">
              {DAYS.map((d) => chip(p.days_per_week === d, String(d), () => edit({ ...p, days_per_week: d })))}
            </div>
            <p className={styles.label}>Minutes per session</p>
            <div className={styles.seg} role="group" aria-label="Minutes per session">
              {MINUTES.map((m) => chip(p.session_minutes === m, String(m), () => edit({ ...p, session_minutes: m })))}
            </div>
          </section>

          <div className={styles.two}>
            <section className={styles.card}>
              <h2><span>04</span> Equipment</h2>
              <div className={styles.chips}>
                {equipment.length === 0 && <p className={styles.muted}>Loading equipment...</p>}
                {equipment.map((q) => chip(p.equipment_ids.includes(q.id), q.name, () => edit({ ...p, equipment_ids: toggle(p.equipment_ids, q.id) })))}
              </div>
            </section>
            <section className={styles.card}>
              <h2><span>05</span> Limitations</h2>
              <div className={styles.chips}>
                {LIMITS.map((l) => chip(limits.includes(l), l, () => setLimits(toggle(limits, l))))}
              </div>
              <p className={styles.muted}>Optional. We avoid movements that load these areas.</p>
            </section>
          </div>

          {error && <p className={styles.error} role="alert">{error}</p>}

          <div className={styles.actions}>
            <p className={styles.state} role="status">{saved ? "All changes saved." : "You have unsaved changes."}</p>
            <button className={styles.save} disabled={busy}>{busy ? "Saving..." : submitLabel}</button>
            {(saved || existing) && <Link href="/programs" className={styles.go}>Go to Programs →</Link>}
          </div>
        </div>
      </div>
    </form>
  );
}
