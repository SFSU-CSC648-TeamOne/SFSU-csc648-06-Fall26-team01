import Link from "next/link";
import Header from "../../components/Header";

export default function ZawPage() {
  return <>
    <Header label="About Our Team" href="/about" />
    <main>
      <section className="hero"><div className="hero-text"><h1>ZAW HTUT</h1><div className="title-line" /><h2>Git Master</h2><p>Manages source control, CI/CD pipelines, and cloud infrastructure to keep the team shipping reliably.</p></div><div className="hero-art"><div className="portrait portrait-purple individual-portrait" role="img" aria-label="Portrait placeholder for Zaw Htut">ZH</div></div></section>
      <section className="team-section"><h2>FOCUS AREAS</h2><div className="section-line" /><p className="construction-copy">Git, CI/CD, Cloud Infrastructure</p><div className="socials"><a href="https://github.com/zawhtut" target="_blank" rel="noopener noreferrer">GitHub</a></div><Link className="deployed-button" href="/about">Back to About Our Team</Link></section>
    </main>
  </>;
}
