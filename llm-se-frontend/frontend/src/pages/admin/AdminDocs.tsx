import { API_BASE } from "../../api/client";
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";

interface DocumentRow {
  source: string;
  owner_department: string;
  min_role_level: number;
  min_clearance_level: number;
  status: string;
  chunks: number;
}

interface IngestForm {
  pdf_filename: string;
  owner_department: string;
  min_role_level: number;
  min_clearance_level: number;
}


export default function AdminDocs() {
  const navigate = useNavigate();

  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");

  const [departments, setDepartments] = useState<string[]>([]);

  const [ingestForm, setIngestForm] = useState<IngestForm>({
    pdf_filename: "",
    owner_department: "",
    min_role_level: 1,
    min_clearance_level: 1,
  });

  const [ingesting, setIngesting] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const token = localStorage.getItem("token") || "";

  /* ================= FETCH DOCUMENTS & DEPARTMENTS ================= */

  const fetchDocuments = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/admin/documents`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) throw new Error("Failed to fetch documents");

      const data = await res.json();

      // 🔑 CRITICAL FIX: normalize backend object → array
      const docsObj = data?.documents || {};
      const rows: DocumentRow[] = Object.entries(docsObj).map(
        ([source, meta]: any) => ({
          source,
          owner_department: meta.owner_department,
          min_role_level: meta.min_role_level,
          min_clearance_level: meta.min_clearance_level,
          status: meta.status || "ingested",
          chunks: meta.chunks || 0,
        })
      );

      setDocuments(rows);
    } catch (e: any) {
      setError(e.message || "Failed to fetch documents");
      setDocuments([]);
    } finally {
      if (!silent) setLoading(false);
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

      setIngestForm((prev) => {
        if ((!prev.owner_department || !names.includes(prev.owner_department)) && names.length > 0) {
          return { ...prev, owner_department: names[0] };
        }
        return prev;
      });
    } catch (e: any) {
      console.error(e.message || "Failed to fetch departments");
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchDocuments();
      fetchDepartments();
    }
  }, [fetchDocuments, fetchDepartments, token]);

  // 🔄 Auto-poll database status while any document is 'ingesting'
  useEffect(() => {
    if (!token) return;

    const hasIngesting = documents.some((d) => d.status === "ingesting");
    if (!hasIngesting) return;

    const interval = setInterval(() => {
      fetchDocuments(true); // silent fetch
    }, 2500);

    return () => clearInterval(interval);
  }, [documents, fetchDocuments, token]);

  /* ================= UPLOAD ================= */

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError("");
    setUploadMsg("");

    try {
      const fd = new FormData();
      fd.append("file", selectedFile);

      const res = await fetch(`${API_BASE}/admin/upload/pdf`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }

      setUploadMsg(`Uploaded successfully: ${selectedFile.name}`);
      
      // Auto-populate filename
      setIngestForm((prev) => ({
        ...prev,
        pdf_filename: selectedFile.name,
      }));

      setSelectedFile(null);
      fetchDocuments();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  /* ================= INGEST ================= */

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    setIngesting(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/admin/ingest/pdf`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          pdf_filename: ingestForm.pdf_filename,
          metadata: {
            owner_department: ingestForm.owner_department,
            min_role_level: ingestForm.min_role_level,
            min_clearance_level: ingestForm.min_clearance_level,
          },
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Ingest failed");
      }

      setIngestForm({
        pdf_filename: "",
        owner_department: departments[0] || "",
        min_role_level: 1,
        min_clearance_level: 1,
      });

      fetchDocuments();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIngesting(false);
    }
  };

  /* ================= DELETE ================= */

  const deleteDoc = async (source: string) => {
    if (!window.confirm(`Delete ${source}?`)) return;

    setDeleting(source);
    setError("");

    try {
      const res = await fetch(
        `${API_BASE}/admin/documents?source=${encodeURIComponent(source)}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!res.ok) throw new Error("Delete failed");

      fetchDocuments();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setDeleting(null);
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
        <h1 style={styles.title}>Document Management</h1>
      </div>

      {error && <div style={styles.error}>{error}</div>}
      {uploadMsg && <div style={styles.success}>{uploadMsg}</div>}

      {/* UPLOAD PANEL */}
      <div style={styles.panel}>
        <h2 style={styles.sectionTitle}>1. Upload PDF Document</h2>
        <div style={styles.uploadRow}>
          <input
            type="file"
            accept="application/pdf"
            style={styles.fileInput}
            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
          />
          <button
            style={styles.primaryBtn}
            disabled={uploading || !selectedFile}
            onClick={handleUpload}
          >
            {uploading ? "Uploading..." : "Upload PDF"}
          </button>
        </div>
      </div>

      {/* INGEST PANEL */}
      <div style={styles.panel}>
        <h2 style={styles.sectionTitle}>2. Ingest uploaded PDF (Embed & Secure)</h2>
        <form onSubmit={handleIngest} style={styles.form}>
          <select
            style={styles.select}
            value={ingestForm.pdf_filename}
            onChange={(e) =>
              setIngestForm({ ...ingestForm, pdf_filename: e.target.value })
            }
            required
          >
            <option value="">-- Select Uploaded PDF --</option>
            {documents.map((d) => (
              <option key={d.source} value={d.source}>
                {d.source}
              </option>
            ))}
          </select>
          <select
            style={styles.select}
            value={ingestForm.owner_department}
            onChange={(e) =>
              setIngestForm({ ...ingestForm, owner_department: e.target.value })
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
            <label style={styles.label}>Min Role Level</label>
            <input
              style={styles.inputNumber}
              type="number"
              min={1}
              max={3}
              value={ingestForm.min_role_level}
              onChange={(e) =>
                setIngestForm({
                  ...ingestForm,
                  min_role_level: +e.target.value,
                })
              }
            />
          </div>
          <div style={styles.inputWrapper}>
            <label style={styles.label}>Min Clearance Level</label>
            <input
              style={styles.inputNumber}
              type="number"
              min={1}
              max={3}
              value={ingestForm.min_clearance_level}
              onChange={(e) =>
                setIngestForm({
                  ...ingestForm,
                  min_clearance_level: +e.target.value,
                })
              }
            />
          </div>
          <button style={styles.successBtn} disabled={ingesting || !ingestForm.pdf_filename}>
            {ingesting ? "Ingesting (Please wait)..." : "Ingest PDF"}
          </button>
        </form>
      </div>

      {/* TABLE */}
      {loading ? (
        <p>Loading documents…</p>
      ) : (
        <div style={styles.tableWrapper}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Source</th>
                <th style={styles.th}>Department</th>
                <th style={styles.th}>Role</th>
                <th style={styles.th}>Clearance</th>
                <th style={styles.th}>Status</th>
                <th style={styles.th}>Chunks</th>
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={7} style={styles.empty}>
                    No documents found
                  </td>
                </tr>
              ) : (
                documents.map((d) => (
                  <tr key={d.source}>
                    <td style={styles.td}>{d.source}</td>
                    <td style={styles.td}>{d.owner_department}</td>
                    <td style={styles.td}>{d.min_role_level}</td>
                    <td style={styles.td}>{d.min_clearance_level}</td>
                    <td style={styles.td}>
                      <span style={getStatusBadgeStyle(d.status)}>
                        {d.status}
                      </span>
                    </td>
                    <td style={styles.td}>{d.chunks}</td>
                    <td style={styles.td}>
                      <button
                        style={styles.deleteBtn}
                        disabled={deleting === d.source}
                        onClick={() => deleteDoc(d.source)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ================= BADGE HELPER ================= */

const getStatusBadgeStyle = (status: string): React.CSSProperties => {
  let color = "#e2e8f0";
  let bg = "#334155";
  
  if (status === "uploaded") {
    color = "#38bdf8";
    bg = "rgba(56, 189, 248, 0.15)";
  } else if (status === "ingesting") {
    color = "#f59e0b";
    bg = "rgba(245, 158, 11, 0.15)";
  } else if (status === "ingested") {
    color = "#10b981";
    bg = "rgba(16, 185, 129, 0.15)";
  } else if (status === "failed") {
    color = "#ef4444";
    bg = "rgba(239, 68, 68, 0.15)";
  }

  return {
    color,
    background: bg,
    padding: "0.25rem 0.5rem",
    borderRadius: 6,
    fontSize: "0.75rem",
    fontWeight: 600,
    textTransform: "uppercase",
    border: `1px solid ${color}`,
    display: "inline-block",
  };
};

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
  success: {
    background: "rgba(16,185,129,.15)",
    border: "1px solid rgba(16,185,129,.3)",
    padding: "0.75rem",
    borderRadius: 6,
    marginBottom: "1.5rem",
    color: "#a7f3d0",
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
  uploadRow: {
    display: "flex",
    gap: "1rem",
    alignItems: "center",
    maxWidth: "600px",
  },
  fileInput: {
    background: "#0f172a",
    border: "1px solid #334155",
    color: "#e2e8f0",
    padding: "0.5rem",
    borderRadius: 6,
    outline: "none",
    flex: 1,
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
    padding: "0.625rem 1.25rem",
    cursor: "pointer",
    fontWeight: 500,
    whiteSpace: "nowrap",
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
    verticalAlign: "middle",
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
  empty: {
    textAlign: "center",
    padding: "1.5rem",
    color: "#94a3b8",
  },
};

