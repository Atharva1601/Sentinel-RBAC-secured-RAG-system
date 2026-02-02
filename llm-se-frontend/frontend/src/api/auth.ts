const API_BASE = import.meta.env.VITE_API_BASE_URL;

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
