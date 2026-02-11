// src/api/auth.ts

import { API_BASE } from "./client";

export async function validateLogin(username: string) {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${username}`,
    },
    body: JSON.stringify({
      query: "ping",
    }),
  });

  if (!res.ok) {
    throw new Error("Unauthorized");
  }

  return true;
}
