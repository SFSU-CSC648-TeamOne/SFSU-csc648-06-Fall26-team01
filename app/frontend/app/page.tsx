import Link from "next/link";

export default function HomePage() {
  return (
    <main className="site">

      {/* NAVBAR */}
      <header className="navbar">
        <div className="logo">
          <span className="logo-mark">✦</span>
          FITNESS - AI CREATED BY PETER
        </div>

        <nav>
          <Link href="/">Home</Link>
          <Link href="/about">About Us</Link>
          <a href="#programs">Programs</a>
          <a href="#features">Features</a>
        </nav>

        <Link href="#get-started" className="nav-button">
          GET STARTED <span>→</span>
        </Link>
      </header>


      {/* HERO */}
      <section className="hero-section">

        <div className="hero-content">

          <div className="hero-small-text">
            Hee Hee Hee 
          </div>

          <h1>
            Hello
            <br />
            Kitty
            <br />
            <span>SANRIO.</span>
          </h1>

          <p className="hero-description">
            Are you ready to get your ass kicked by Sanrio Characters?????
          </p>

          <div className="hero-buttons">
            <Link href="#get-started" className="primary-button">
              GET STARTED <span>→</span>
            </Link>

            <Link href="#features" className="secondary-button">
              EXPLORE FEATURES
            </Link>
          </div>

        </div>

        {/* IMAGE PLACEHOLDER */}
        <div className="hero-image">
          <div className="image-placeholder">
            <span>Picture of Prash idk</span>
          </div>

          <div className="hero-overlay-text">
            <span>could be carasoul number here</span>
            <p>Hello Kitty<br />Is watching.</p>
          </div>
        </div>

      </section>


      {/* MARQUEE */}
      <section className="marquee">
        <div className="marquee-track">
          <span>Hello Kitty</span>
          <span>•</span>
          <span>Cinnaroll</span>
          <span>•</span>
          <span>Penguin</span>
          <span>•</span>
          <span>Yellow Dog??</span>
          <span>•</span>
          <span>Kuromi</span>
          <span>•</span>
        </div>
      </section>


      {/* ABOUT */}
      <section className="about-section" id="features">

        <div className="section-label">
          ABOUT THE APP
        </div>

        <div className="about-content">

          <h2>
            WHERE
            <br />
            <span>IS MY</span>
            <br />
            EXTRA CREDIT.
          </h2>

          <div className="about-text">
            <p>
              wE CAN PUT A DESCRIPTION OF OUR APP HERE OR SMTG SO LET ME KNOW DURING MEETING.
            </p>

            <Link href="/about" className="text-link">
              MEET THE TEAM THIS SHOULD BRING US TO THE ABOUT US PAGE→
            </Link>
          </div>

        </div>

      </section>


      {/* FEATURES */}
      <section className="features-section" id="programs">

        <div className="section-label">
          WHAT WE OFFER
        </div>

        <div className="feature-grid">

          <div className="feature-card">
            <span className="feature-number">01</span>
            <h3>SMART TRAINING</h3>
            <p>
              nIANTIC?
            </p>
          </div>

          <div className="feature-card">
            <span className="feature-number">02</span>
            <h3>PROGRESS TRACKING</h3>
            <p>
              TRACKING AND MONITORING
            </p>
          </div>

          <div className="feature-card">
            <span className="feature-number">03</span>
            <h3>AI ASSISTANT</h3>
            <p>
              nIANTIC 2.0??
            </p>
          </div>

        </div>

      </section>


      {/* CTA */}
      <section className="cta-section" id="get-started">

        <div className="cta-content">
          <span>YOUR JOURNEY STARTS HERE.</span>

          <h2>
            READY TO
            <br />
            <span>goto?</span>
          </h2>

          <button className="primary-button">
            LA LA LANDDDDDDDDDDD <span>→</span>
          </button>
        </div>

      </section>


      {/* FOOTER */}
      <footer>
        <div className="logo">
          <span className="logo-mark">✦</span>
          local host 3000 on Peters Pc btw
        </div>

        <p>Built by SFSU CSC648 Team One</p>
      </footer>

    </main>
  );
}