import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const API_BASE = "http://127.0.0.1:8000";

export default function Login() {
  const [username, setUsername] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const { setUser } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const cleanUsername = username.trim();
    if (!cleanUsername) {
      setError("Username is required");
      return;
    }

    setError("");
    setIsLoading(true);

    try {
      // 1️⃣ Validate user via /query
      const response = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${cleanUsername}`,
        },
        body: JSON.stringify({
          request_id: "login_check",
          query: "auth_check",
        }),
      });

      if (response.status === 401) {
        throw new Error("User not found");
      }

      if (response.status === 403) {
        throw new Error("User is inactive");
      }

      if (!response.ok) {
        throw new Error("Login failed");
      }

      // 2️⃣ Fetch real user profile
      const meRes = await fetch(`${API_BASE}/auth/me`, {
        headers: {
          Authorization: `Bearer ${cleanUsername}`,
        },
      });

      if (!meRes.ok) {
        throw new Error("Failed to load user profile");
      }

      const user = await meRes.json();

      // 3️⃣ Persist auth
      localStorage.setItem("token", cleanUsername);
      setUser(user);

      navigate("/chat");
    } catch (err: any) {
      localStorage.removeItem("token");
      setError(err.message || "Login failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.brand}>Sentinel</h1>
        <p style={styles.tagline}>RBAC-secured RAG System</p>
        <p style={styles.subtitle}>Login</p>

        <form onSubmit={handleLogin} style={styles.form}>
          <div style={styles.inputGroup}>
            <label htmlFor="username" style={styles.label}>
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isLoading}
              style={styles.input}
              autoComplete="username"
              autoFocus
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{
              ...styles.button,
              ...(isLoading ? styles.buttonDisabled : {}),
            }}
          >
            {isLoading ? "Logging in…" : "Login"}
          </button>

          {error && <div style={styles.error}>{error}</div>}
        </form>
      </div>
    </div>
  );
}

/* =========================
   STYLES
   ========================= */

const styles: Record<string, React.CSSProperties> = {
  brand: {
  fontSize: "2.6rem",
  fontWeight: 700,
  color: "#e5e7eb",
  textAlign: "center",
  letterSpacing: "0.02em",
  marginBottom: "0.1rem",
},

tagline: {
  fontSize: "1.2rem",
  fontWeight: 500,
  color: "#9ca3af",
  textAlign: "center",
  marginTop: 0,
  marginBottom: "1.75rem",
},

  container: {
    height: "100vh",
    width: "100vw",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background:
      "radial-gradient(circle at top, #1f2937 0%, #0f1115 60%)",
    overflow: "hidden",
  },
  card: {
    width: "100%",
    maxWidth: "420px",
    backgroundColor: "#1b1f27",
    borderRadius: "8px",
    padding: "2.75rem",
    boxShadow: "0 20px 40px rgba(0,0,0,0.45)",
    border: "1px solid rgba(255,255,255,0.04)",
  },
  title: {
    fontSize: "1.4rem",
    fontWeight: 600,
    color: "#e5e7eb",
    textAlign: "center",
    marginBottom: "0.25rem",
    letterSpacing: "-0.01em",
  },
  subtitle: {
    fontSize: "1.3rem",
    color: "#9ca3af",
    textAlign: "center",
    marginBottom: "2rem",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "1.5rem",
  },
  inputGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem",
  },
  label: {
    fontSize: "0.8rem",
    fontWeight: 500,
    color: "#9ca3af",
  },
  input: {
    width: "100%",
    padding: "0.75rem 1rem",
    fontSize: "1rem",
    backgroundColor: "#0f1115",
    border: "1px solid #2d3139",
    borderRadius: "4px",
    color: "#e5e7eb",
    outline: "none",
    boxSizing: "border-box",
  },
  button: {
    width: "100%",
    padding: "0.75rem 1rem",
    fontSize: "1rem",
    fontWeight: 500,
    backgroundColor: "#3b82f6",
    color: "#ffffff",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    transition: "background-color 0.2s ease, transform 0.1s ease",
  },
  buttonDisabled: {
    backgroundColor: "#1e40af",
    cursor: "not-allowed",
    opacity: 0.7,
  },
  error: {
    padding: "0.75rem 1rem",
    fontSize: "0.85rem",
    backgroundColor: "rgba(239, 68, 68, 0.1)",
    border: "1px solid rgba(239, 68, 68, 0.3)",
    borderRadius: "4px",
    color: "#f87171",
    textAlign: "center",
  
  },
};
