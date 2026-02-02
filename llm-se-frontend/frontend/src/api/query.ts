import { API_BASE, authHeaders } from "./client";

export async function sendQuery(query: string) {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      request_id: crypto.randomUUID(),
      query,
    }),
  });

  return res.json();
}
