"use client";

import Link from "next/link";
import { useState } from "react";
import Navbar from "../../components/Navbar";
import { login } from "../../lib/auth";
import s from "../screens.module.css";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try { await login(email, password); window.location.replace("/profile"); } // Redirect to profile page on successful login to match M2.
    catch (err) { setError(err instanceof Error ? err.message : "Could not log in"); setBusy(false); }
  }

  return (
    <main className={s.page}>
      <Navbar />
      <div className={`${s.wrap} ${s.narrow}`}>
        <p className={s.kicker}>Log in</p>
        <h1 className={s.h1}>Welcome <span>back.</span></h1>
        <form className={s.form} onSubmit={submit}>
          <div className={s.field}><label htmlFor="email">Email</label>
            <input id="email" className={s.input} type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <div className={s.field}><label htmlFor="pw">Password</label>
            <input id="pw" className={s.input} type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
          {error && <p className={s.error} role="alert">{error}</p>}
          <button className={s.btn} disabled={busy}>{busy ? "Logging in..." : "Log in ↗"}</button>
        </form>
        <p className={s.swap}>New here? <Link href="/signup">Create an account</Link></p>
      </div>
    </main>
  );
}
