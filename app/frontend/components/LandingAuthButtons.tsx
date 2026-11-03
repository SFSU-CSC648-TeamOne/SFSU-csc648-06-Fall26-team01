"use client";

import Link from "next/link";
import { useAuth } from "../lib/auth";
import styles from "./LandingAuthButtons.module.css";

/** Top-right buttons of the landing page: Sign in + Register, or "Go to Programs" when already signed in.
 *  Drop it in place of the old EXPLORE button in the landing page's top bar. */
export default function LandingAuthButtons() {
  const { user, loading } = useAuth();
  if (loading) return <div className={styles.box} aria-hidden="true" />;
  if (user) return <div className={styles.box}><Link href="/programs" className={styles.fill}>Go to Programs</Link></div>;
  return (
    <div className={styles.box}>
      <Link href="/login" className={styles.ghost}>Sign in</Link>
      <Link href="/signup" className={styles.fill}>Register</Link>
    </div>
  );
}
