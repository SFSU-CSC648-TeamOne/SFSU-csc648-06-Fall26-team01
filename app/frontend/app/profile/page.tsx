
import Link from "next/link";

export default function ProfilePage() {
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
<div className="feature">
  <h3>WELCOME TO ASCENDA</h3>
  <p>Log in or create an account to manage your fitness profile.</p>
  <Link href="/login" className="button-primary">LOG IN</Link>{" "}
  <Link href="/signup" className="button-secondary">SIGN UP</Link>
</div>
      <section className="intro">
        <span className="section-number">01 — YOUR ACCOUNT</span>
        <h2>
          YOUR FITNESS
          <br />
          <span>PROFILE.</span>
        </h2>
        <p>
          Set up your fitness goals, experience, available equipment,
          and weekly training schedule.
        </p>
      </section>

      <section className="features">
        <div className="section-heading">
          <span>PROFILE SETTINGS</span>
          <p>YOUR TRAINING STARTING POINT</p>
        </div>

        <div className="feature-list">
          <div className="feature">
            <h3>FITNESS GOALS</h3>
            <p>Choose your personal training goals.</p>
          </div>
          <div className="feature">
            <h3>EXPERIENCE LEVEL</h3>
            <p>Set your current training experience.</p>
          </div>
          <div className="feature">
            <h3>EQUIPMENT</h3>
            <p>Identify the equipment you can access.</p>
          </div>
          <div className="feature">
            <h3>WEEKLY SCHEDULE</h3>
            <p>Choose your available training days and time.</p>
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
