import { api } from "../../lib/auth";

export type Message = { id: number | string; role: "user" | "assistant"; content: string; created_at?: string };
export type ConversationSummary = { id: number; title: string; created_at: string; updated_at: string };
export type Conversation = ConversationSummary & { messages: Message[] };

export const listConversations = () => api<ConversationSummary[]>("/chat/conversations");
export const createConversation = () => api<ConversationSummary>("/chat/conversations", { method: "POST" });
export const getConversation = (id: number) => api<Conversation>(`/chat/conversations/${id}`);
export const deleteConversation = (id: number) => api<void>(`/chat/conversations/${id}`, { method: "DELETE" });
export const sendMessage = (id: number, content: string) =>
  api<{ user_message: Message; reply: Message }>(`/chat/conversations/${id}/messages`, { method: "POST", body: JSON.stringify({ content }) });
