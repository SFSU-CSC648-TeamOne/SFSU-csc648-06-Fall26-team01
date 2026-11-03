"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./chat.module.css";
import { useChat } from "./ChatProvider";

// Messages + message box. Used by both the widget and the full page.
export default function ChatPanel({ greeting }: { greeting?: React.ReactNode }) {
  const { active, send, sending, error } = useChat();
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [active?.messages.length, sending]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const t = text;
    setText("");
    void send(t);
  }

  const empty = !active || active.messages.length === 0;
  return (
    <div className={styles.panel}>
      <div className={styles.messages} role="log" aria-live="polite" aria-label="Chat messages">
        {empty && (greeting ?? <p className={styles.hint}>Ask me about exercises, programs or your training.</p>)}
        {active?.messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? styles.msgUser : styles.msgBot}>{m.content}</div>
        ))}
        {error && <p className={styles.hint} role="alert" style={{ color: "var(--red)" }}>{error}</p>}
        {sending && <div className={styles.msgBot}><span className={styles.dots}>···</span></div>}
        <div ref={endRef} />
      </div>
      <form className={styles.inputRow} onSubmit={submit}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask Ascenda..." aria-label="Message" />
        <button type="submit" disabled={!text.trim() || sending} aria-label="Send">↑</button>
      </form>
    </div>
  );
}

export function HistoryList({ onPick }: { onPick?: () => void }) {
  const { conversations, active, select, newChat, remove } = useChat();
  return (
    <div className={styles.history}>
      <button className={styles.newChat} onClick={() => { newChat(); onPick?.(); }}>+ New chat</button>
      <p className={styles.histLabel}>Chat history</p>
      {conversations.length === 0 && <p className={styles.hint}>No conversations yet.</p>}
      <ul>
        {conversations.map((c) => (
          <li key={c.id} className={c.id === active?.id ? styles.histOn : ""}>
            <button className={styles.histItem} onClick={() => { void select(c.id); onPick?.(); }}>{c.title}</button>
            <button className={styles.histDel} onClick={() => void remove(c.id)} aria-label={`Delete ${c.title}`}>×</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
