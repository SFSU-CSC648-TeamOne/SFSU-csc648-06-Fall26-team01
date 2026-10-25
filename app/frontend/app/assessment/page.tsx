
import Link from "next/link";

export default function AssessmentPage() {
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
        <span className="section-number">02 — FITNESS ASSESSMENT</span>
        <h2>
          START WHERE
          <br />
          <span>YOU ARE.</span>
        </h2>
        <p>
          Establish your fitness experience, goals, and training needs
          to help guide your workout planning.
        </p>
      </section>

      <section className="features">
        <div className="section-heading">
          <span>YOUR ASSESSMENT</span>
          <p>BUILD YOUR TRAINING FOUNDATION</p>
        </div>

        <div className="feature-list">
          <div className="feature">
            <h3>01 — EXPERIENCE</h3>
            <p>Describe your current fitness and lifting experience.</p>
          </div>
          <div className="feature">
            <h3>02 — GOALS</h3>
            <p>Identify what you want to achieve through training.</p>
          </div>
          <div className="feature">
            <h3>03 — AVAILABILITY</h3>
            <p>Consider your weekly schedule and workout duration.</p>
          </div>
          <div className="feature">
            <h3>04 — RESULTS</h3>
            <p>Use your answers as a starting point for workout planning.</p>
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
