"use client";

import { useCallback, useEffect, useState } from "react";

const TOKEN_KEY = "ascenda_token";

export type User = { id: number; email: string; display_name: string | null; role: string };

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

export const getToken = () => (typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY));
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

/** fetch wrapper: adds the bearer token, parses JSON, throws ApiError with the backend's message. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (init.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`/api${path}`, { ...init, headers });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      // Tolerant: FastAPI uses {detail}; custom handlers may use {message} or {error:{message}}.
      const d = j?.detail ?? j?.message ?? j?.error?.message ?? j?.error;
      if (Array.isArray(d)) msg = d.map((x) => x?.msg ?? JSON.stringify(x)).join("; ");
      else if (d) msg = typeof d === "string" ? d : JSON.stringify(d);
    } catch {}
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

type Token = { access_token: string; token_type: string; user: User };

export async function login(email: string, password: string) {
  const r = await api<Token>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
  setToken(r.access_token);
}

/** POST /api/auth/register already returns a token, so no second login call is needed. */
export async function register(email: string, password: string, displayName?: string) {
  const r = await api<Token>("/auth/register", {
    method: "POST", body: JSON.stringify({ email, password, display_name: displayName }),
  });
  setToken(r.access_token);
}

/** Current user from GET /api/auth/me. user === null means signed out. */
export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) { setUser(null); setLoading(false); return; }
    try { setUser(await api<User>("/auth/me")); }
    catch (e) {
      // Only an expired/invalid login (401) signs the user out. A network error or a page change
      // that aborts the request must NOT delete the saved token.
      if (e instanceof ApiError && e.status === 401) clearToken();
      setUser(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const logout = useCallback(() => { clearToken(); setUser(null); }, []);
  return { user, loading, refresh, logout };
}

/** First name for greetings, e.g. "Hi, Alisha". */
export function displayName(u: User | null) {
  if (!u) return "";
  return (u.display_name?.split(" ")[0] || u.email.split("@")[0]);
}

/** For signed-in pages: sends visitors who are not logged in to /login. */
export function useRequireAuth() {
  const a = useAuth();
  useEffect(() => {
    if (!a.loading && !a.user && !getToken() && typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }, [a.loading, a.user]);
  return a;
}
