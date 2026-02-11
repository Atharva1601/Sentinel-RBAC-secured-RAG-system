import { useState, useEffect, useCallback } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

interface User {
  username: string;
  role_level: number;
  clearance_level: number;
  department: string;
  is_active: boolean;
}

interface CreateUserForm {
  username: string;
  role_level: number;
  clearance_level: number;
  department: string;
}

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  "https://sentinel-rag-backend.onrender.com";


export default function AdminUsers() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const token = user?.username || "";

  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [updating, setUpdating] = useState(false);

  const [createForm, setCreateForm] = useState<CreateUserForm>({
    username: "",
    role_level: 1,
    clearance_level: 1,
    department: "",
  });

  /* ================= FETCH USERS ================= */

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/admin/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) throw new Error("Failed to fetch users");

      const data: User[] = await res.json();
      setUsers(data);
    } catch (e: any) {
      setError(e.message || "Failed to fetch users");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) fetchUsers();
  }, [fetchUsers, token]);

  /* ================= CREATE USER ================= */

  const handleCreateUser = async (e: FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/admin/users`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(createForm),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Create failed");
      }

      setCreateForm({
        username: "",
        role_level: 1,
        clearance_level: 1,
        department: "",
      });

      fetchUsers();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  };

  /* ================= TOGGLE ACTIVE ================= */

  const toggleActive = async (u: User) => {
    setUpdating(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/admin/users/${u.username}`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ is_active: !u.is_active }),
      });

      if (!res.ok) throw new Error("Update failed");

      fetchUsers();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUpdating(false);
    }
  };

  /* ================= DELETE USER ================= */

  const deleteUser = async (username: string) => {
    if (!window.confirm(`Delete user "${username}" permanently?`)) return;

    setUpdating(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/admin/users/${username}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Delete failed");
      }

      fetchUsers();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUpdating(false);
    }
  };

  /* ================= UI ================= */

  return (
    <div style={styles.container}>
      {/* TOP BAR */}
      <div style={styles.topBar}>
        <button style={styles.backBtn} onClick={() => navigate("/chat")}>
          ← Back to Chat
        </button>
        <h1 style={styles.title}>User Management</h1>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* CREATE USER */}
      <form onSubmit={handleCreateUser} style={styles.form}>
        <input
          style={styles.input}
          placeholder="Username"
          value={createForm.username}
          onChange={(e) =>
            setCreateForm({ ...createForm, username: e.target.value })
          }
          required
        />
        <input
          style={styles.input}
          placeholder="Department"
          value={createForm.department}
          onChange={(e) =>
            setCreateForm({ ...createForm, department: e.target.value })
          }
          required
        />
        <input
          style={styles.input}
          type="number"
          min={1}
          value={createForm.role_level}
          onChange={(e) =>
            setCreateForm({ ...createForm, role_level: +e.target.value })
          }
        />
        <input
          style={styles.input}
          type="number"
          min={1}
          value={createForm.clearance_level}
          onChange={(e) =>
            setCreateForm({ ...createForm, clearance_level: +e.target.value })
          }
        />
        <button style={styles.primaryBtn} disabled={creating}>
          {creating ? "Creating…" : "Create User"}
        </button>
      </form>

      {/* USERS TABLE */}
      {loading ? (
        <p>Loading users…</p>
      ) : (
        <div style={styles.tableWrapper}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Username</th>
                <th style={styles.th}>Department</th>
                <th style={styles.th}>Role</th>
                <th style={styles.th}>Clearance</th>
                <th style={styles.th}>Active</th>
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.username === user?.username;
                const isAdminUser = u.username === "admin";

                return (
                  <tr key={u.username}>
                    <td style={styles.td}>{u.username}</td>
                    <td style={styles.td}>{u.department}</td>
                    <td style={styles.td}>{u.role_level}</td>
                    <td style={styles.td}>{u.clearance_level}</td>
                    <td style={styles.td}>
                      <input
                        type="checkbox"
                        checked={u.is_active}
                        disabled={updating || isAdminUser}
                        onChange={() => toggleActive(u)}
                      />
                    </td>
                    <td style={styles.td}>
                      <button
                        style={styles.deleteBtn}
                        disabled={updating || isSelf || isAdminUser}
                        onClick={() => deleteUser(u.username)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ================= STYLES ================= */

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: "100vh",
    padding: "2rem",
    background: "#0f1115",
    color: "#e5e7eb",
  },
  topBar: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    marginBottom: "1.5rem",
  },
  backBtn: {
    background: "transparent",
    color: "#93c5fd",
    border: "1px solid #374151",
    padding: "0.35rem 0.75rem",
    borderRadius: 4,
    cursor: "pointer",
  },
  title: {
    fontSize: "1.75rem",
  },
  error: {
    background: "rgba(239,68,68,.15)",
    border: "1px solid rgba(239,68,68,.3)",
    padding: "0.75rem",
    marginBottom: "1rem",
  },
  form: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))",
    gap: "0.75rem",
    marginBottom: "2rem",
  },
  input: {
    background: "#111827",
    border: "1px solid #374151",
    color: "#e5e7eb",
    padding: "0.5rem",
    borderRadius: 4,
  },
  primaryBtn: {
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    padding: "0.5rem",
    cursor: "pointer",
  },
  tableWrapper: {
    border: "1px solid #374151",
    borderRadius: 6,
    overflow: "hidden",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    background: "#020617",
  },
  th: {
    textAlign: "left",
    padding: "10px",
    fontSize: "0.75rem",
    textTransform: "uppercase",
    color: "#9ca3af",
    borderBottom: "1px solid #374151",
  },
  td: {
    padding: "10px",
    borderBottom: "1px solid #1f2937",
    fontSize: "0.875rem",
  },
  deleteBtn: {
    background: "#dc2626",
    color: "#fff",
    border: "none",
    padding: "0.35rem 0.6rem",
    borderRadius: 4,
    cursor: "pointer",
  },
};
