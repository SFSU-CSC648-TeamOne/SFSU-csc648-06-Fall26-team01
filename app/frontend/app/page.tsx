import Link from "next/link";

const features = [
  {
    number: "01",
    title: "PROFILE",
    text: "Set your goals, experience, equipment, and schedule.",
  },
  {
    number: "02",
    title: "ASSESSMENT",
    text: "Establish your fitness experience and training starting point.",
  },
  {
    number: "03",
    title: "EXERCISE CATALOG",
    text: "Search and filter exercises by muscle, equipment, and duration.",
  },
  {
    number: "04",
    title: "ADAPTIVE WORKOUTS",
    text: "Adjust your session when time or equipment changes.",
  },
  {
    number: "05",
    title: "WORKOUT HISTORY",
    text: "Log completed workouts and follow your progress over time.",
  },
];

const exercises = [
  {
    name: "Barbell Bench Press",
    muscle: "CHEST",
    equipment: "BARBELL",
    duration: "08 MIN",
    type: "CORE",
  },
  {
    name: "Lat Pulldown",
    muscle: "BACK",
    equipment: "MACHINE",
    duration: "07 MIN",
    type: "CORE",
  },
  {
    name: "Cable Fly",
    muscle: "CHEST",
    equipment: "CABLE",
    duration: "06 MIN",
    type: "ACCESSORY",
  },
];

export default function HomePage() {
  return (
    <main className="site">

      {/* NAVIGATION */}

      <header className="navbar">
        <Link href="/" className="logo">
          <span className="logo-symbol">A</span>
          ASCENDA
        </Link>

        <nav>
          <a href="#features">Features</a>
          <a href="#catalog">Exercise Catalog</a>
          <a href="#adaptive">Adaptive Training</a>
          <Link href="/about">Team</Link>
        </nav>

        <Link href="#features" className="nav-button">
          EXPLORE
        </Link>
      </header>


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
              EXPLORE ASCENDA
              <span>↗</span>
            </a>

            <a href="#catalog" className="button-secondary">
              VIEW CATALOG
            </a>
          </div>

        </div>


        {/* PRODUCT UI */}

        <div className="hero-product">

          <div className="product-window">

            <div className="window-top">
              <div className="window-dots">
                <i />
                <i />
                <i />
              </div>

              <span>ASCENDA / SESSION</span>

              <span className="ready">
                ● READY
              </span>
            </div>


            <div className="session">

              <span className="mini-label">
                TODAY'S SESSION
              </span>

              <h2>
                UPPER BODY
              </h2>

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
                  <strong className="lime">
                    READY
                  </strong>
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

        <span className="section-number">
          01 — ASCENDA
        </span>

        <h2>
          FITNESS SHOULD
          <br />
          <span>ADAPT TO YOU.</span>
        </h2>

        <p>
          Real schedules change. Equipment availability changes.
          Your training shouldn't have to completely fall apart when they do.
        </p>

      </section>


      {/* FEATURES */}

      <section className="features" id="features">

        <div className="section-heading">

          <span>
            02 — FEATURES
          </span>

          <p>
            FIVE PARTS OF THE ASCENDA EXPERIENCE
          </p>

        </div>


        <div className="feature-list">

          {features.map((feature) => (

            <div className="feature" key={feature.number}>

              <span className="feature-number">
                {feature.number}
              </span>

              <h3>
                {feature.title}
              </h3>

              <p>
                {feature.text}
              </p>

              <span className="feature-arrow">
                ↗
              </span>

            </div>

          ))}

        </div>

      </section>


      {/* CATALOG */}

      <section className="catalog" id="catalog">

        <div className="catalog-copy">

          <span className="section-number">
            03 — EXERCISE CATALOG
          </span>

          <h2>
            FIND THE
            <br />
            <span>RIGHT MOVEMENT.</span>
          </h2>

          <p>
            Browse exercises based on muscle group, equipment,
            duration, and training requirements.
          </p>

        </div>


        <div className="catalog-ui">

          <div className="catalog-top">

            <div className="search">
              <span>⌕</span>
              Search exercises...
            </div>

            <button>
              MUSCLE GROUP
              <span>⌄</span>
            </button>

            <button>
              EQUIPMENT
              <span>⌄</span>
            </button>

          </div>


          <div className="exercise-table">

            {exercises.map((exercise, index) => (

              <div className="exercise" key={exercise.name}>

                <span className="exercise-index">
                  0{index + 1}
                </span>

                <div className="exercise-title">
                  <strong>
                    {exercise.name}
                  </strong>

                  <small>
                    {exercise.muscle}
                  </small>
                </div>

                <span>
                  {exercise.equipment}
                </span>

                <span>
                  {exercise.duration}
                </span>

                <b className={exercise.type === "CORE" ? "core" : "accessory-tag"}>
                  {exercise.type}
                </b>

              </div>

            ))}

          </div>

          <div className="catalog-footer">
            <span>
              DATABASE / EXERCISES
            </span>

            <span>
              10+ EXERCISES
            </span>
          </div>

        </div>

      </section>


      {/* ADAPTIVE TRAINING */}

      <section className="adaptive" id="adaptive">

        <div className="adaptive-copy">

          <span className="section-number">
            04 — ADAPTIVE TRAINING
          </span>

          <h2>
            LESS TIME?
            <br />
            <span>NO PROBLEM.</span>
          </h2>

          <p>
            Ascenda separates core exercises from accessory exercises,
            allowing lower-priority movements to be removed when your
            available time is shorter than the expected workout duration.
          </p>

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


      {/* PROGRESS */}

      <section className="progress">

        <div className="progress-copy">

          <span className="section-number">
            05 — WORKOUT HISTORY
          </span>

          <h2>
            SEE YOUR
            <br />
            <span>PROGRESS.</span>
          </h2>

          <p>
            Completed workouts and performance history give users
            a measurable record of their training over time.
          </p>

        </div>


        <div className="progress-card">

          <div className="progress-card-top">
            <span>TRAINING HISTORY</span>
            <span>SEPTEMBER</span>
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

        <span className="section-number">
          ASCENDA
        </span>

        <h2>
          KEEP
          <br />
          <span>ASCENDING.</span>
        </h2>

        <p>
          Structured training. Flexible workouts.
          Measurable progress.
        </p>

        <a href="#features" className="button-primary">
          EXPLORE ASCENDA
          <span>↗</span>
        </a>

      </section>


      {/* FOOTER */}

      <footer>

        <Link href="/" className="logo">
          <span className="logo-symbol">
            A
          </span>
          ASCENDA
        </Link>

        <span>
          SFSU CSC648 · FALL 2026
        </span>

        <Link href="/about">OUR TEAM ↗</Link>

      </footer>

    </main>
  );
}