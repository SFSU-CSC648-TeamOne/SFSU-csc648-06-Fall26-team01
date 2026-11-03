"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./Navbar.module.css";
import { useAuth } from "../lib/auth";

// Main items from the UI/UX flow (numbered like the diagram: ☰1, ☰2, ☰3).
const mainLinks = [
  { label: "Home", href: "/dashboard" },
  { label: "Profile", href: "/profile" },
  { label: "Training history", href: "/history" },
  { label: "Ascenda Chat", href: "/chat" },
];

// Extra shortcuts kept from the old menu. Delete this list if you want only the three above.
const moreLinks = [
  { label: "Programs", href: "/programs" },
  { label: "Program library", href: "/programs/library" },
  { label: "Exercises", href: "/search" },
  { label: "Workouts", href: "/workouts" },
  { label: "Team", href: "/about" },
];

type Props = {
  /** Optional override. Normally leave it out: the navbar checks the login itself. */
  signedIn?: boolean;
  /** Optional top-right content that replaces the built-in LOG IN / SIGN UP buttons (used by the landing page). */
  actions?: React.ReactNode;
};

export default function Navbar({ signedIn: forced, actions }: Props) {
  const { user, loading, logout } = useAuth();
  const signedIn = forced ?? !!user;
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const pathname = usePathname();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  useEffect(() => setMounted(true), []);

  // Close when the route changes.
  useEffect(() => setOpen(false), [pathname]);

  // Escape closes; page behind does not scroll while the panel is open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [open]);

  // Give focus back to the hamburger when the panel closes.
  useEffect(() => {
    if (wasOpen.current && !open) buttonRef.current?.focus();
    wasOpen.current = open;
  }, [open]);

  const close = () => setOpen(false);

  const panel = (
    <>
      <div className={`${styles.overlay} ${open ? styles.overlayOn : ""}`} onClick={close} aria-hidden="true" />
      <aside
        id="ascenda-site-menu"
        className={`${styles.drawer} ${open ? styles.drawerOn : ""}`}
        aria-label="Main navigation"
        aria-hidden={!open}
        inert={!open}
      >
        <div className={styles.drawerTop}>
          <Link href="/" className={styles.logo} onClick={close}>
            <span className={styles.logoSymbol}>A</span>
            ASCENDA
          </Link>
          <button ref={closeRef} type="button" className={styles.closeBtn} onClick={close} aria-label="Close navigation menu">✕</button>
        </div>

        <nav className={styles.drawerNav}>
          <p className={styles.menuLabel}>MENU</p>
          {mainLinks.map((l, i) => (
            <Link key={l.href} href={l.href} onClick={close} className={`${styles.menuLink} ${pathname === l.href ? styles.menuLinkOn : ""}`}>
              <span className={styles.menuNum}>{i + 1}</span>
              <span>{l.label}</span>
              <span aria-hidden="true">↗</span>
            </Link>
          ))}

          <p className={`${styles.menuLabel} ${styles.menuLabelGap}`}>MORE</p>
          {moreLinks.map((l) => (
            <Link key={l.href} href={l.href} onClick={close} className={`${styles.menuLink} ${styles.menuLinkSmall} ${pathname === l.href ? styles.menuLinkOn : ""}`}>
              <span />
              <span>{l.label}</span>
              <span aria-hidden="true">↗</span>
            </Link>
          ))}
        </nav>

        <div className={styles.menuFooter}>
          {signedIn ? (
            <>
              <span>{user?.email}</span>
              <Link href="/" onClick={() => { logout(); close(); }}>Log out</Link>
            </>
          ) : (
            <>
              <Link href="/login" onClick={close}>Log in</Link>
              <Link href="/signup" onClick={close}>Create account</Link>
            </>
          )}
        </div>
      </aside>
    </>
  );

  return (
    <header className={styles.navbar}>
      <div className={styles.left}>
        <button
          ref={buttonRef}
          type="button"
          className={styles.menuButton}
          aria-label="Open navigation menu"
          aria-expanded={open}
          aria-controls="ascenda-site-menu"
          onClick={() => setOpen(true)}
        >
          <span className={styles.bar} />
          <span className={styles.bar} />
          <span className={styles.bar} />
        </button>

        <Link href="/" className={styles.logo}>
          <span className={styles.logoSymbol}>A</span>
          ASCENDA
        </Link>
      </div>

      {actions ?? (!signedIn && !loading && (
        <div className={styles.actions}>
          <Link href="/login" className={styles.login}>LOG IN</Link>
          <Link href="/signup" className={styles.signup}>SIGN UP ↗</Link>
        </div>
      ))}

      {/* Rendered into <body> so no parent can clip it or sit above it. */}
      {mounted && createPortal(panel, document.body)}
    </header>
  );
}
