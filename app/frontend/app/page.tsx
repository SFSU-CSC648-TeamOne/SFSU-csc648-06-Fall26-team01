import Link from "next/link";
import Header from "./components/Header";

export default function HomePage() {
  return <>
    <Header label="About Our Team" href="/about" />
    <main>
      <section className="hero">
        <div className="hero-text">
          <h1>UNDER CONSTRUCTION</h1><div className="title-line" />
          <p>We are building something useful for our community. Check back soon to see what our team has been working on.</p>
        </div>
        <div className="hero-art"><svg viewBox="0 0 600 280" role="img" aria-label="Fitness and AI">
          <ellipse cx="300" cy="245" rx="220" ry="14" fill="#dcecff" />
          <path d="M300 48 V92 M300 92 L225 132 M300 92 L375 132 M225 132 H375" fill="none" stroke="#1681f5" strokeWidth="8" strokeLinecap="round" />
          <circle cx="300" cy="48" r="16" fill="#ffb72d" /><circle cx="225" cy="132" r="16" fill="#ffb72d" /><circle cx="375" cy="132" r="16" fill="#ffb72d" /><circle cx="300" cy="92" r="13" fill="#17395f" />
          <path d="M170 190 H430" stroke="#17395f" strokeWidth="20" strokeLinecap="round" /><path d="M215 160 V220 M235 153 V227 M365 153 V227 M385 160 V220" stroke="#ffb72d" strokeWidth="18" strokeLinecap="round" /><path d="M270 190 H330" stroke="#1681f5" strokeWidth="24" strokeLinecap="round" />
        </svg></div>
      </section>
      <section className="team-section"><h2>OUR SITE IS COMING SOON</h2><div className="section-line" /><p className="construction-copy">While we put the finishing touches on the project, learn more about the people behind it.</p><Link className="deployed-button" href="/about">Meet Our Team</Link></section>
    </main>
  </>;
}
