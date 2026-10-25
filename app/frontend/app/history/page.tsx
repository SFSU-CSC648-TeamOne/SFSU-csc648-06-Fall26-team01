
import Link from "next/link";

export default function HistoryPage() {
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
        <span className="section-number">03 — WORKOUT HISTORY</span>
        <h2>
          TRACK YOUR
          <br />
          <span>PROGRESS.</span>
        </h2>
        <p>
          Review completed sessions and follow your training progress
          over time.
        </p>
      </section>

      <section className="features">
        <div className="section-heading">
          <span>YOUR TRAINING RECORD</span>
          <p>WORKOUTS AND PERFORMANCE</p>
        </div>

        <div className="feature-list">
          <div className="feature">
            <h3>COMPLETED WORKOUTS</h3>
            <p>Your past training sessions will appear here when connected.</p>
          </div>
          <div className="feature">
            <h3>TRAINING CONSISTENCY</h3>
            <p>Review how regularly you complete workouts.</p>
          </div>
          <div className="feature">
            <h3>PERFORMANCE</h3>
            <p>Track recorded sets, repetitions, and weights.</p>
          </div>
        </div>
      </section>

      <footer>
        <Link href="/" className="logo">
          <span className="logo-symbol">A</span>
          ASCENDA
        </Link>
        <span>YOUR FITNESS JOURNEY</span>
        <Link href="/">HOME ↗</Link>
      </footer>
    </main>
  );
}
