"use client";

import Link from "next/link";
import { useState } from "react";
import Navbar from "../../components/Navbar";
import { register } from "../../lib/auth";
import s from "../screens.module.css";

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    setBusy(true); setError("");
    try { await register(email, password, name || undefined); window.location.href = "/profile/setup"; }
    catch (err) { setError(err instanceof Error ? err.message : "Could not create the account"); setBusy(false); }
  }

  return (
    <main className={s.page}>
      <Navbar />
      <div className={`${s.wrap} ${s.narrow}`}>
        <p className={s.kicker}>Register</p>
        <h1 className={s.h1}>Start <span>training.</span></h1>
        <form className={s.form} onSubmit={submit}>
          <div className={s.field}><label htmlFor="name">First name</label>
            <input id="name" className={s.input} autoComplete="given-name" value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div className={s.field}><label htmlFor="email">Email</label>
            <input id="email" className={s.input} type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <div className={s.field}><label htmlFor="pw">Password</label>
            <input id="pw" className={s.input} type="password" required minLength={8} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
          {error && <p className={s.error} role="alert">{error}</p>}
          <button className={s.btn} disabled={busy}>{busy ? "Creating..." : "Create account ↗"}</button>
        </form>
        <p className={s.swap}>Already have an account? <Link href="/login">Log in</Link></p>
      </div>
    </main>
  );
}
