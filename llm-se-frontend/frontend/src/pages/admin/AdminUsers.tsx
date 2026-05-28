import { API_BASE } from "../../api/client";
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

export default function AdminUsers() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token") || user?.username || "";

  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [updating, setUpdating] = useState(false);

  const [departments, setDepartments] = useState<string[]>([]);
  const [newDeptName, setNewDeptName] = useState("");
  const [addingDept, setAddingDept] = useState(false);

  const [createForm, setCreateForm] = useState<CreateUserForm>({
    username: "",
    role_level: 1,
    clearance_level: 1,
    department: "",
  });

  /* ================= FETCH USERS & DEPARTMENTS ================= */

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

  const fetchDepartments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/departments`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) throw new Error("Failed to fetch departments");

      const data = await res.json();
      const names = data.map((d: any) => d.name);
      setDepartments(names);

      setCreateForm((prev) => {
        if ((!prev.department || !names.includes(prev.department)) && names.length > 0) {
          return { ...prev, department: names[0] };
        }
        return prev;
      });
    } catch (e: any) {
      console.error(e.message || "Failed to fetch departments");
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchUsers();
      fetchDepartments();
    }
  }, [fetchUsers, fetchDepartments, token]);

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
        department: departments[0] || "",
      });

      fetchUsers();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  };

  /* ================= ADD DEPARTMENT ================= */

  const handleAddDept = async (e: FormEvent) => {
    e.preventDefault();
    if (!newDeptName.trim()) return;
    setAddingDept(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/admin/departments`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: newDeptName.trim() }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to add department");
      }

      setNewDeptName("");
      await fetchDepartments();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setAddingDept(false);
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
        <h1 style={styles.title}>User & Department Management</h1>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* ADD NEW DEPARTMENT PANEL */}
      <div style={styles.panel}>
        <h2 style={styles.sectionTitle}>Add New Department</h2>
        <form onSubmit={handleAddDept} style={styles.inlineForm}>
          <input
            style={styles.inputDept}
            placeholder="Department Name (e.g. Marketing)"
            value={newDeptName}
            onChange={(e) => setNewDeptName(e.target.value)}
            required
          />
          <button style={styles.successBtn} disabled={addingDept}>
            {addingDept ? "Adding…" : "Add Department"}
          </button>
        </form>
      </div>

      {/* CREATE USER PANEL */}
      <div style={styles.panel}>
        <h2 style={styles.sectionTitle}>Create New User</h2>
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
          <select
            style={styles.select}
            value={createForm.department}
            onChange={(e) =>
              setCreateForm({ ...createForm, department: e.target.value })
            }
            required
          >
            {departments.length === 0 ? (
              <option value="">No departments available</option>
            ) : (
              departments.map((dept) => (
                <option key={dept} value={dept}>
                  {dept}
                </option>
              ))
            )}
          </select>
          <div style={styles.inputWrapper}>
            <label style={styles.label}>Role Level (1-3)</label>
            <input
              style={styles.inputNumber}
              type="number"
              min={1}
              max={3}
              value={createForm.role_level}
              onChange={(e) =>
                setCreateForm({ ...createForm, role_level: +e.target.value })
              }
            />
          </div>
          <div style={styles.inputWrapper}>
            <label style={styles.label}>Clearance (1-3)</label>
            <input
              style={styles.inputNumber}
              type="number"
              min={1}
              max={3}
              value={createForm.clearance_level}
              onChange={(e) =>
                setCreateForm({ ...createForm, clearance_level: +e.target.value })
              }
            />
          </div>
          <button style={styles.primaryBtn} disabled={creating}>
            {creating ? "Creating…" : "Create User"}
          </button>
        </form>
      </div>

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
    background: "#0f172a",
    color: "#e2e8f0",
    fontFamily: "'Inter', sans-serif",
  },
  topBar: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    marginBottom: "2rem",
  },
  backBtn: {
    background: "transparent",
    color: "#38bdf8",
    border: "1px solid #334155",
    padding: "0.5rem 1rem",
    borderRadius: 6,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  title: {
    fontSize: "1.75rem",
    fontWeight: 600,
    color: "#f8fafc",
  },
  error: {
    background: "rgba(239,68,68,.15)",
    border: "1px solid rgba(239,68,68,.3)",
    padding: "0.75rem",
    borderRadius: 6,
    marginBottom: "1.5rem",
    color: "#fca5a5",
  },
  panel: {
    background: "#1e293b",
    padding: "1.5rem",
    borderRadius: 8,
    marginBottom: "1.5rem",
    border: "1px solid #334155",
    boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
  },
  sectionTitle: {
    fontSize: "1.25rem",
    fontWeight: 500,
    marginBottom: "1rem",
    color: "#f1f5f9",
  },
  inlineForm: {
    display: "flex",
    gap: "0.75rem",
    maxWidth: "500px",
  },
  form: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))",
    gap: "1rem",
    alignItems: "end",
  },
  input: {
    background: "#0f172a",
    border: "1px solid #334155",
    color: "#e2e8f0",
    padding: "0.625rem",
    borderRadius: 6,
    outline: "none",
    width: "100%",
  },
  inputDept: {
    background: "#0f172a",
    border: "1px solid #334155",
    color: "#e2e8f0",
    padding: "0.625rem",
    borderRadius: 6,
    outline: "none",
    flex: 1,
  },
  inputNumber: {
    background: "#0f172a",
    border: "1px solid #334155",
    color: "#e2e8f0",
    padding: "0.625rem",
    borderRadius: 6,
    outline: "none",
    width: "100%",
  },
  select: {
    background: "#0f172a",
    border: "1px solid #334155",
    color: "#e2e8f0",
    padding: "0.625rem",
    borderRadius: 6,
    outline: "none",
    width: "100%",
    cursor: "pointer",
  },
  inputWrapper: {
    display: "flex",
    flexDirection: "column",
    gap: "0.35rem",
  },
  label: {
    fontSize: "0.75rem",
    color: "#94a3b8",
  },
  primaryBtn: {
    background: "#0284c7",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "0.625rem",
    cursor: "pointer",
    fontWeight: 500,
    transition: "background 0.2s",
  },
  successBtn: {
    background: "#059669",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "0.625rem 1.25rem",
    cursor: "pointer",
    fontWeight: 500,
    whiteSpace: "nowrap",
    transition: "background 0.2s",
  },
  tableWrapper: {
    border: "1px solid #334155",
    borderRadius: 8,
    overflow: "hidden",
    boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    background: "#0f172a",
  },
  th: {
    textAlign: "left",
    padding: "12px 16px",
    fontSize: "0.75rem",
    fontWeight: 600,
    textTransform: "uppercase",
    color: "#94a3b8",
    borderBottom: "1px solid #334155",
    background: "#1e293b",
  },
  td: {
    padding: "12px 16px",
    borderBottom: "1px solid #1e293b",
    fontSize: "0.875rem",
    color: "#cbd5e1",
  },
  deleteBtn: {
    background: "#e11d48",
    color: "#fff",
    border: "none",
    padding: "0.35rem 0.75rem",
    borderRadius: 6,
    cursor: "pointer",
    fontWeight: 500,
    transition: "background 0.2s",
  },
};

