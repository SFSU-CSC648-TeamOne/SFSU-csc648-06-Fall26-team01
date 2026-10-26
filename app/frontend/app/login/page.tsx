
"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, saveSession } from "../lib/api";

// added functions for signing up / handling submit logic
export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);

    try {
      const data = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      saveSession(data);
      router.push("/profile");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    }
  }

  // original code from frontend
  return (
    <main className="site">
      <header className="navbar">
        <Link href="/" className="logo">
          <span className="logo-symbol">A</span>
          ASCENDA
        </Link>
        <Link href="/" className="nav-button">
          ← BACK TO HOME
        </Link>
      </header>

      <section className="intro">
        <span className="section-number">ACCOUNT / 01</span>
        <h2>
          WELCOME
          <br />
          <span>BACK.</span>
        </h2>
        <p>Log in to access your fitness profile and training journey.</p>

        <form className="auth-form" onSubmit={(event) => event.preventDefault()}>
          <label htmlFor="email">EMAIL ADDRESS</label>
          <input id="email" type="email" placeholder="you@example.com" required />

          <label htmlFor="password">PASSWORD</label>
          <input id="password" type="password" placeholder="Enter your password" required />

          <button className="button-primary" type="submit">
            LOG IN ↗
          </button>
          <p>
            Don't have an account? <Link href="/signup">Sign up</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
