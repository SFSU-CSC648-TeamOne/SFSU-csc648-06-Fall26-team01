"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import styles from "./chat.module.css";
import ChatPanel, { HistoryList } from "./ChatPanel";
import { useChat } from "./ChatProvider";
import { useAuth } from "../../lib/auth";

// The icon shows on every page except the full chat page itself.
const HIDDEN = ["/chat"];

export default function ChatWidget() {
  const path = usePathname();
  const { user } = useAuth();
  const { isOpen, setOpen } = useChat();
  const [showHistory, setShowHistory] = useState(false);
  const iconRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, setOpen]);

  useEffect(() => {
    if (wasOpen.current && !isOpen) iconRef.current?.focus();
    wasOpen.current = isOpen;
  }, [isOpen]);

  if (HIDDEN.includes(path)) return null;

  return (
    <>
      {!isOpen && (
        <button ref={iconRef} className={styles.launcher} onClick={() => setOpen(true)} aria-label="Open chat">✦</button>
      )}
      {isOpen && (
        <aside className={styles.drawer} aria-label="Ascenda chat">
          <header className={styles.drawerHead}>
            <b>ASCENDA CHAT</b>
            <span className={styles.headBtns}>
              {user && <button onClick={() => setShowHistory((s) => !s)}>{showHistory ? "Chat" : "History"}</button>}
              {user && <Link href="/chat" onClick={() => setOpen(false)}>Full page</Link>}
              <button onClick={() => setOpen(false)} aria-label="Close chat">✕</button>
            </span>
          </header>
          {!user ? (
            <div className={styles.signIn}>
              <p>Sign in to chat with Ascenda. Your conversations are saved to your account.</p>
              <Link href="/login" onClick={() => setOpen(false)}>Log in</Link>
              <Link href="/signup" onClick={() => setOpen(false)}>Create account</Link>
            </div>
          ) : showHistory ? <HistoryList onPick={() => setShowHistory(false)} /> : <ChatPanel />}
        </aside>
      )}
    </>
  );
}
