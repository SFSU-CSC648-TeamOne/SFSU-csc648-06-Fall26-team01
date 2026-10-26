// file calls backend through the /api in next.config.ts
// automatically sends the saved login token

export async function api(path: string, options: RequestInit = {}) {
    const token = 
        typeof window !== "undefined" ? localStorage.getItem("token") : null;

    const res = await fetch(`/api${path}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorized: `Bearer ${token}` } : {}),
            ...options.headers,
        },
    });

    const data = await res.json().catch(() => null);
    if (!res.ok) {
        const detail = data && typeof data.detail == "string" ? data.detail : null;
        throw new Error(detail ?? `Request failed (${res.status})`);
    }
    return data;
}

// keeps current token so other pages can use without having 
// to login again
export function saveSession(data: { access_token: string; user: unknown}) {
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("user", JSON.stringify(data.user));
}