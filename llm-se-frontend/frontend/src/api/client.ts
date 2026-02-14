console.log("VITE_API_URL =", import.meta.env.VITE_API_URL);

export const API_BASE = import.meta.env.VITE_API_URL;

export function authHeaders(extraHeaders: Record<string, string> = {}) {
  const token = localStorage.getItem("token");

  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extraHeaders,
  };
}
