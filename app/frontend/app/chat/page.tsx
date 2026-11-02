"use client";

import styles from "./chat.module.css";
import Navbar from "../../components/Navbar";
import { displayName, useRequireAuth } from "../../lib/auth";
import ChatPanel, { HistoryList } from "./ChatPanel";

// Full chat page. Chat history is always visible on the left.
export default function ChatPage() {
  const { user } = useRequireAuth();
  return (
    <>
    <Navbar />
    <main className={styles.fullPage}>
      <aside className={styles.sideHist}><HistoryList /></aside>
      <section className={styles.fullMain}>
        <ChatPanel
          greeting={
            <div className={styles.greeting}>
              <p className={styles.hi}>Hi, {displayName(user)}</p>
              <p className={styles.pill}>ASCENDA</p>
            </div>
          }
        />
      </section>
    </main>
    </>
  );
}
