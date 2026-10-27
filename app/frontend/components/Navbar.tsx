"use client";

import { useState } from "react";
import Link from "next/link";
import styles from "./Navbar.module.css";

const links = [
  { label: "Home", href: "/" },
  { label: "Profile", href: "/profile" },
  { label: "Assessment", href: "/assessment" },
  { label: "Programs", href: "/programs" },
  { label: "Exercises", href: "/search" },
  { label: "Workouts", href: "/workouts" },
  { label: "Workout History", href: "/history" },
  { label: "Team", href: "/about" },
];

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);

  function closeMenu() {
    setMenuOpen(false);
  }

  return (
    <header className={styles.navbar}>
      <Link href="/" className={styles.logo} onClick={closeMenu}>
        <span className={styles.logoSymbol}>A</span>
        ASCENDA
      </Link>

      <div className={styles.actions}>
        <Link href="/login" className={styles.login} onClick={closeMenu}>
          LOG IN
        </Link>
        <Link href="/signup" className={styles.signup} onClick={closeMenu}>
          SIGN UP ↗
        </Link>
        <button
          type="button"
          className={styles.menuButton}
          aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={menuOpen}
          aria-controls="ascenda-site-menu"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className={menuOpen ? styles.barOpenTop : styles.bar} />
          <span className={menuOpen ? styles.barHidden : styles.bar} />
          <span className={menuOpen ? styles.barOpenBottom : styles.bar} />
        </button>
      </div>

      {menuOpen && (
        <nav id="ascenda-site-menu" className={styles.menu} aria-label="Main navigation">
          <p className={styles.menuLabel}>NAVIGATION</p>
          {links.map((link) => (
            <Link key={link.href} href={link.href} onClick={closeMenu} className={styles.menuLink}>
              <span>{link.label}</span>
              <span aria-hidden="true">↗</span>
            </Link>
          ))}
          <div className={styles.menuFooter}>
            <Link href="/login" onClick={closeMenu}>Log in</Link>
            <Link href="/signup" onClick={closeMenu}>Create account</Link>
          </div>
        </nav>
      )}
    </header>
  );
}
