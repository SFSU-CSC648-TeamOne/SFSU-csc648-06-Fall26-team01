
"use client";

import Link from "next/link";
import ModelViewer from "./about/ModelViewer";
import WorkoutMain from "../components/WorkoutMain";
import Navbar from "../components/Navbar";

const features = [
  {
    number: "01",
    title: "PROFILE",
    text: "Set your goals, experience, equipment, and schedule.",
    href: "/profile",
  },
  {
    number: "02",
    title: "ASSESSMENT",
    text: "Establish your fitness experience and training starting point.",
    href: "/assessment",
  },
  {
    number: "03",
    title: "EXERCISE CATALOG",
    text: "Search and filter exercises by muscle, equipment, and duration.",
    href: "/search",
  },
  {
    number: "04",
    title: "ADAPTIVE WORKOUTS",
    text: "Explore workouts and find sessions that fit your schedule.",
    href: "/workouts",
  },
  {
    number: "05",
    title: "WORKOUT HISTORY",
    text: "Review completed workouts and track your progress.",
    href: "/history",
  },
];

export default function HomePage() {
  return (
    <main className="site">
      {/* SHARED HAMBURGER NAVIGATION */}
      <Navbar />

      {/* HERO */}
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="status-dot" />
            ADAPTIVE FITNESS PLATFORM
          </div>

          <h1>
            TRAIN
            <br />
            <span>YOUR WAY.</span>
          </h1>

          <p>
            Ascenda creates a more flexible training experience by combining
            fitness assessments, exercise discovery, adaptive workouts, and
            long-term progress tracking.
          </p>

          <div className="hero-actions">
            <a href="#features" className="button-primary">
              EXPLORE ASCENDA <span>↗</span>
            </a>

            <Link href="/search" className="button-secondary">
              VIEW CATALOG
            </Link>
          </div>
        </div>

        {/* PRODUCT PREVIEW */}
        <div className="hero-product">
          <div className="product-window">
            <div className="window-top">
              <div className="window-dots">
                <i />
                <i />
                <i />
              </div>
              <span>ASCENDA / SESSION</span>
              <span className="ready">● READY</span>
            </div>

            <div className="session">
              <span className="mini-label">TODAY'S SESSION</span>
              <h2>UPPER BODY</h2>

              <div className="session-meta">
                <div>
                  <span>DURATION</span>
                  <strong>42 MIN</strong>
                </div>
                <div>
                  <span>EXERCISES</span>
                  <strong>06</strong>
                </div>
                <div>
                  <span>STATUS</span>
                  <strong className="lime">READY</strong>
                </div>
              </div>

              <div className="session-progress">
                <div />
              </div>

              <div className="session-exercises">
                <div>
                  <span>01</span>
                  <strong>Barbell Bench Press</strong>
                  <small>CORE · 08 MIN</small>
                </div>
                <div>
                  <span>02</span>
                  <strong>Lat Pulldown</strong>
                  <small>CORE · 07 MIN</small>
                </div>
                <div className="accessory">
                  <span>03</span>
                  <strong>Cable Fly</strong>
                  <small>ACCESSORY · 06 MIN</small>
                </div>
              </div>
            </div>
          </div>

          <div className="time-card">
            <span>AVAILABLE TIME</span>
            <strong>35 MIN</strong>
            <small>Workout can adapt</small>
          </div>
        </div>
      </section>

      {/* INTRO */}
      <section className="intro">
        <span className="section-number">01 — ASCENDA</span>
        <h2>
          FITNESS SHOULD
          <br />
          <span>ADAPT TO YOU.</span>
        </h2>
        <p>
          Real schedules change. Equipment availability changes. Your training
          shouldn't have to completely fall apart when they do.
        </p>
      </section>

      {/* CLICKABLE FEATURES */}
      <section className="features" id="features">
        <div className="section-heading">
          <span>02 — FEATURES</span>
          <p>FIVE PARTS OF THE ASCENDA EXPERIENCE</p>
        </div>

        <div className="feature-list">
          {features.map((feature) => (
            <Link
              href={feature.href}
              className="feature"
              key={feature.number}
              aria-label={`Open ${feature.title}`}
            >
              <span className="feature-number">{feature.number}</span>
              <h3>{feature.title}</h3>
              <p>{feature.text}</p>
              <span className="feature-arrow" aria-hidden="true">
                ↗
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* EXERCISE CATALOG */}
      <section className="catalog" id="catalog">
        <div className="catalog-copy">
          <span className="section-number">03 — WORKOUT SEARCH</span>
          <h2>
            FIND THE
            <br />
            <span>RIGHT WORKOUT.</span>
          </h2>
          <p>
            Search and filter database-backed workouts by exercise, muscle
            group, difficulty, and duration.
          </p>
          <Link href="/workouts" className="button-primary">
            FIND WORKOUTS <span>↗</span>
          </Link>
        </div>

        <div className="catalog-ui">
          <WorkoutMain />
        </div>
      </section>

      {/* INTERACTIVE EXERCISE LAB */}
      <section className="exercise-lab" id="exercise-lab">
        <div className="lab-heading">
          <span className="section-number">
            04 — INTERACTIVE EXERCISE LAB
          </span>
          <h2>
            EXPLORE THE
            <br />
            <span>MOVEMENT.</span>
          </h2>
          <p>
            Explore exercise equipment in 3D and watch demonstrations to learn
            proper exercise technique.
          </p>
        </div>

        <div className="lab-grid">
          <div className="viewer-panel">
            <div className="lab-panel-top">
              <span>3D MODEL VIEWER</span>
              <span className="viewer-status">INTERACTIVE</span>
            </div>

            <ModelViewer />

            <div className="viewer-footer">
              <span>DRAG TO ROTATE · SCROLL TO ZOOM</span>
            </div>
          </div>

          <div className="video-panel">
            <div className="lab-panel-top">
              <span>EXERCISE DEMONSTRATIONS</span>
              <span className="video-count">02 VIDEOS</span>
            </div>

            <div className="demo-video">
              <video controls preload="metadata" playsInline>
                <source src="/about/demo_one.mp4" type="video/mp4" />
                Your browser does not support this video.
              </video>
              <div className="video-info">
                <span>DEMO / 01</span>
                <h3>Hercules Squat</h3>
                <p>
                  Watch the movement and review the exercise technique in the
                  3D scanned room.
                </p>
              </div>
            </div>

            <div className="demo-video">
              <video controls preload="metadata" playsInline>
                <source src="/about/demo_two.mp4" type="video/mp4" />
                Your browser does not support this video.
              </video>
              <div className="video-info">
                <span>DEMO / 02</span>
                <h3>Pistol Squat Jesus</h3>
                <p>Follow the demonstration to understand the movement.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ADAPTIVE TRAINING */}
      <section className="adaptive" id="adaptive">
        <div className="adaptive-copy">
          <span className="section-number">05 — ADAPTIVE TRAINING</span>
          <h2>
            LESS TIME?
            <br />
            <span>NO PROBLEM.</span>
          </h2>
          <p>
            Ascenda separates core exercises from accessory exercises, allowing
            lower-priority movements to be removed when available time is
            shorter than the expected workout duration.
          </p>
          <Link href="/workouts" className="button-secondary">
            EXPLORE WORKOUTS
          </Link>
        </div>

        <div className="adaptive-ui">
          <div className="available">
            <span>AVAILABLE TIME</span>
            <strong>35 MIN</strong>
          </div>
          <div className="expected">
            EXPECTED SESSION
            <strong>45 MIN</strong>
          </div>
          <div className="adaptive-line">
            <span />
          </div>
          <div className="adaptive-exercises">
            <div className="keep">
              <span>✓</span>
              <strong>CORE EXERCISES</strong>
              <small>KEEP</small>
            </div>
            <div className="remove">
              <span>−</span>
              <strong>ACCESSORY EXERCISES</strong>
              <small>OPTIONAL</small>
            </div>
          </div>
          <div className="result">
            <span>ADAPTED SESSION</span>
            <strong>32 MIN</strong>
            <b>TRAINING GOAL PRESERVED</b>
          </div>
        </div>
      </section>

      {/* WORKOUT HISTORY */}
      <section className="progress" id="history">
        <div className="progress-copy">
          <span className="section-number">06 — WORKOUT HISTORY</span>
          <h2>
            SEE YOUR
            <br />
            <span>PROGRESS.</span>
          </h2>
          <p>
            Completed workouts and performance history give users a measurable
            record of their training over time.
          </p>
          <Link href="/history" className="button-primary">
            VIEW HISTORY <span>↗</span>
          </Link>
        </div>

        <div className="progress-card">
          <div className="progress-card-top">
            <span>TRAINING HISTORY</span>
            <span>EXAMPLE</span>
          </div>
          <div className="progress-number">
            89%
            <small>CONSISTENCY</small>
          </div>
          <div className="chart">
            <div className="chart-line line-one" />
            <div className="chart-line line-two" />
            <div className="chart-line line-three" />
          </div>
          <div className="progress-stats">
            <div>
              <strong>18</strong>
              <span>WORKOUTS</span>
            </div>
            <div>
              <strong>16</strong>
              <span>COMPLETED</span>
            </div>
            <div>
              <strong>+12%</strong>
              <span>PROGRESS</span>
            </div>
          </div>
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="final">
        <div className="final-glow" />
        <span className="section-number">ASCENDA</span>
        <h2>
          KEEP
          <br />
          <span>ASCENDING.</span>
        </h2>
        <p>Structured training. Flexible workouts. Measurable progress.</p>
        <Link href="/signup" className="button-primary">
          GET STARTED <span>↗</span>
        </Link>
      </section>

      {/* FOOTER */}
      <footer>
        <Link href="/" className="logo">
          <span className="logo-symbol">A</span>
          ASCENDA
        </Link>
        <span>SFSU CSC648 · FALL 2026</span>
        <Link href="/about">OUR TEAM ↗</Link>
      </footer>
    </main>
  );
}