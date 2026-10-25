
"use client";

import Link from "next/link";

export default function LoginPage() {
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
