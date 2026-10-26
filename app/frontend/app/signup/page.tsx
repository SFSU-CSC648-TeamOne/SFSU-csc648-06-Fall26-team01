"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, saveSession } from "../lib/api";

// added functions for signing up / handling submit logic
export default function SignupPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);

    if (form.get("password") != form.get("confirm")) {
      setError("Passwords do not match");
      return;
    }

    try {
      const data = await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
          display_name: form.get("name"),
        }),
      });
      saveSession(data);
      router.push("/profile");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Signup failed");
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
        <span className="section-number">ACCOUNT / 02</span>
        <h2>
          START YOUR
          <br />
          <span>JOURNEY.</span>
        </h2>
        <p>Create an account to begin building your fitness experience.</p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label htmlFor="name">FULL NAME</label>
          <input id="name" name="name" type="text" placeholder="Your name" required />

          <label htmlFor="email">EMAIL ADDRESS</label>
          <input id="email" name="email" type="email" placeholder="you@example.com" required />

          <label htmlFor="password">PASSWORD</label>
          <input id="password" name="password" type="password" placeholder="Create a password" required />

          <label htmlFor="confirm-password">CONFIRM PASSWORD</label>
          <input id="confirm-password" name="confirm" type="password" placeholder="Confirm your password" required />

          <button className="button-primary" type="submit">
            CREATE ACCOUNT ↗
          </button>
          <p>
            Already have an account? <Link href="/login">Log in</Link>
          </p>
        </form>
      </section>
    </main>
  );
}
