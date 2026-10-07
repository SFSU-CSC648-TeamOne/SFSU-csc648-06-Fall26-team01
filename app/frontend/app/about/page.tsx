import Link from "next/link";

const team = [
  {
    number: "01",
    name: "Alisha Sinha",
    role: "Team Lead",
    description:
      "Leads planning and coordination to keep the team on track.",
    focus: "Project Planning, Agile, Documentation",
    joined: "August 2026",
    education: "Computer Science, San Francisco State University",
    about:
      "Interested in Project Management and project planning, and building creative and useful applications that make a difference in society and world of business.",
    initials: "AS",
    color: "blue",
  },
  {
    number: "02",
    name: "Ian Brown",
    role: "SCRUM Master",
    description:
      "Facilitator and coach for improving team performance and collaboration.",
    focus: "Lean Six Sigma, Supabase, React, Exercise Programming",
    joined: "August 2026",
    education: "Computer Science, San Francisco State University",
    about:
      "Interested in information security, developing services useful to the health and safety of users, and creative lean design.",
    initials: "IB",
    color: "green",
  },
  {
    number: "03",
    name: "Zaw Htut",
    role: "Git Master",
    description:
      "Manages source control, CI/CD pipelines, and cloud infrastructure to keep the team shipping reliably.",
    focus: "DevOps, CI/CD, Git and Cloud Infrastructure",
    joined: "August 2026",
    education: "Computer Science, San Francisco State University",
    about:
      "Focused on source control, automated delivery pipelines, and reliable cloud environments.",
    initials: "ZH",
    color: "purple",
  },
  {
    number: "04",
    name: "Prashrit Magar",
    role: "AI Jesus",
    description:
      "Focuses on integrating AI features into the app to create helpful and personalized fitness experiences.",
    focus: "AI Integration, OpenAI API, Personalized Fitness Features",
    joined: "August 2026",
    education: "Computer Science, San Francisco State University",
    about:
      "Interested in artificial intelligence, self-driving car systems, and building technology that can solve real-world problems.",
    initials: "PM",
    color: "red",
  },
  {
    number: "05",
    name: "Geo Wong",
    role: "Backend Developer",
    description:
      "Focus on developing and maintaining server-side logic and managing API endpoints.",
    focus: "Supabase",
    joined: "August 2026",
    education: "Computer Science, San Francisco State University",
    about: "Backend Development, Database, API Development",
    initials: "GW",
    color: "orange",
  },
  {
    number: "06",
    name: "Peter Yu",
    role: "Front End Developer",
    description:
      "Focus on developing and maintaining friendly User UX/UI and front-end functionality.",
    focus: "REACT",
    joined: "August 2026",
    education: "Computer Science, San Francisco State University",
    about: "Front End Development, UX/UI Design, functionality",
    initials: "PY",
    color: "orange",
  },
];

export default function AboutPage() {
  return (
    <main className="about-page">
      <header className="navbar">
        <Link href="/" className="logo">
          <span className="logo-symbol">A</span>
          ASCENDA
        </Link>

        <nav>
          <Link href="/">Home</Link>
          <a href="#team">Team</a>
        </nav>

        <Link href="/" className="nav-button">
          BACK HOME
        </Link>
      </header>

      <section className="about-hero">
        <div className="about-hero-content">
          <div className="eyebrow">
            <span className="status-dot" />
            SFSU CSC648 · FALL 2026
          </div>

          <h1>
            ABOUT
            <br />
            <span>OUR TEAM.</span>
          </h1>

          <p>
            Six students working together to build Ascenda, an adaptive
            fitness platform designed to make structured training more
            flexible.
          </p>
        </div>

        <div className="hero-index">
          <span>ABOUT / 01</span>
          <strong>ASCENDA</strong>
        </div>
      </section>

      <section className="team-section" id="team">
        <div className="section-heading">
          <div>
            <span>02 — THE TEAM</span>

            <h2>
              THE PEOPLE
              <br />
              BEHIND ASCENDA.
            </h2>
          </div>

          <p>
            SIX STUDENTS.
            <br />
            ONE PROJECT.
          </p>
        </div>

        <div className="team-grid">
          {team.map((member) => (
            <article className="team-card" key={member.number}>
              <div className="card-top">
                <span>{member.number}</span>
                <span>ASCENDA / TEAM</span>
              </div>

              <div className={`member-avatar ${member.color}`}>
                {member.initials}
              </div>

              <div className="member-info">
                <span className="member-role">{member.role}</span>

                <h3>{member.name}</h3>

                <p>{member.description}</p>

                <div className="member-focus">
                  <span>FOCUS</span>
                  <strong>{member.focus}</strong>
                </div>
              </div>

              <div className="card-bottom">
                <span>{member.joined}</span>
                <span className="arrow">↗</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <footer>
        <Link href="/" className="logo">
          <span className="logo-symbol">A</span>
          ASCENDA
        </Link>

        <span>SFSU CSC648 · FALL 2026</span>

        <Link href="/">HOME ↗</Link>
      </footer>
    </main>
  );
}