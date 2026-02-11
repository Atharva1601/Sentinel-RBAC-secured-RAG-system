// src/api/client.ts

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  "https://sentinel-rag-backend.onrender.com";

export function authHeaders() {
  const token = localStorage.getItem("token");

  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}
