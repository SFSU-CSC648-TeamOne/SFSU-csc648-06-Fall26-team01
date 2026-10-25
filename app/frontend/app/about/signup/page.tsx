
"use client";

import Link from "next/link";

export default function SignupPage() {
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

        <form className="auth-form" onSubmit={(event) => event.preventDefault()}>
          <label htmlFor="name">FULL NAME</label>
          <input id="name" type="text" placeholder="Your name" required />

          <label htmlFor="email">EMAIL ADDRESS</label>
          <input id="email" type="email" placeholder="you@example.com" required />

          <label htmlFor="password">PASSWORD</label>
          <input id="password" type="password" placeholder="Create a password" required />

          <label htmlFor="confirm-password">CONFIRM PASSWORD</label>
          <input id="confirm-password" type="password" placeholder="Confirm your password" required />

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
