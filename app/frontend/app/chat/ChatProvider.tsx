"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useAuth } from "../../lib/auth";
import * as chat from "./chatApi";
import type { Conversation, ConversationSummary, Message } from "./chatApi";

type Ctx = {
  conversations: ConversationSummary[];
  active: Conversation | null;
  isOpen: boolean;
  sending: boolean;
  error: string;
  setOpen: (v: boolean) => void;
  newChat: () => void;
  select: (id: number) => Promise<void>;
  send: (text: string) => Promise<void>;
  remove: (id: number) => Promise<void>;
};

const ChatCtx = createContext<Ctx | null>(null);
const UI_KEY = "ascenda-chat-ui"; // open state + active conversation id, survives a page refresh

export function useChat() {
  const c = useContext(ChatCtx);
  if (!c) throw new Error("useChat must be used inside <ChatProvider>");
  return c;
}

export default function ChatProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [active, setActive] = useState<Conversation | null>(null);
  const [isOpen, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

  const refreshList = useCallback(async () => {
    try { setConversations(await chat.listConversations()); } catch (e) { setError(e instanceof Error ? e.message : "Could not load chats"); }
  }, []);

  const select = useCallback(async (id: number) => {
    try { setActive(await chat.getConversation(id)); setError(""); } catch { setActive(null); }
  }, []);

  // Restore the open panel and the active chat after a refresh, once we know who the user is.
  useEffect(() => {
    if (!user) { setConversations([]); setActive(null); return; }
    void refreshList();
    try {
      const u = JSON.parse(sessionStorage.getItem(UI_KEY) ?? "null");
      if (u) { setOpen(!!u.isOpen); if (u.activeId) void select(u.activeId); }
    } catch {}
    setReady(true);
  }, [user, refreshList, select]);

  useEffect(() => {
    if (!ready) return;
    try { sessionStorage.setItem(UI_KEY, JSON.stringify({ isOpen, activeId: active?.id ?? null })); } catch {}
  }, [isOpen, active?.id, ready]);

  const newChat = useCallback(() => setActive(null), []);

  const remove = useCallback(async (id: number) => {
    await chat.deleteConversation(id);
    setActive((a) => (a?.id === id ? null : a));
    await refreshList();
  }, [refreshList]);

  const send = useCallback(async (text: string) => {
    const content = text.trim();
    if (!content || sending) return;
    setSending(true); setError("");
    const temp: Message = { id: `tmp-${Date.now()}`, role: "user", content };
    try {
      let conv = active;
      if (!conv) {
        const created = await chat.createConversation();
        conv = { ...created, messages: [] };
      }
      setActive({ ...conv, messages: [...conv.messages, temp] }); // show the user's message at once
      const r = await chat.sendMessage(conv.id, content);
      setActive({ ...conv, messages: [...conv.messages, r.user_message, r.reply] });
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Message failed");
      setActive((a) => (a ? { ...a, messages: a.messages.filter((m) => m.id !== temp.id) } : a));
    } finally { setSending(false); }
  }, [active, sending, refreshList]);

  return (
    <ChatCtx.Provider value={{ conversations, active, isOpen, sending, error, setOpen, newChat, select, send, remove }}>
      {children}
    </ChatCtx.Provider>
  );
}
