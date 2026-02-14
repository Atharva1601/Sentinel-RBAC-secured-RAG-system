import { API_BASE } from "../../api/client";
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";

interface DocumentRow {
  source: string;
  owner_department: string;
  min_role_level: number;
  min_clearance_level: number;
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

  const [ingestForm, setIngestForm] = useState<IngestForm>({
    pdf_filename: "",
    owner_department: "",
    min_role_level: 1,
    min_clearance_level: 1,
  });

  const [ingesting, setIngesting] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const token = localStorage.getItem("token") || "";

  /* ================= FETCH DOCUMENTS ================= */

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
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
        })
      );

      setDocuments(rows);
    } catch (e: any) {
      setError(e.message || "Failed to fetch documents");
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) fetchDocuments();
  }, [fetchDocuments, token]);

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

      if (!res.ok) throw new Error("Upload failed");

      setUploadMsg(`Uploaded: ${selectedFile.name}`);
      setSelectedFile(null);
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

      if (!res.ok) throw new Error("Ingest failed");

      setIngestForm({
        pdf_filename: "",
        owner_department: "",
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

      {/* UPLOAD */}
      <div style={styles.form}>
        <input
          type="file"
          accept="application/pdf"
          style={styles.input}
          onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
        />
        <button
          style={styles.primaryBtn}
          disabled={uploading || !selectedFile}
          onClick={handleUpload}
        >
          Upload PDF
        </button>
      </div>

      {/* INGEST */}
      <form onSubmit={handleIngest} style={styles.form}>
        <input
          style={styles.input}
          placeholder="PDF filename"
          value={ingestForm.pdf_filename}
          onChange={(e) =>
            setIngestForm({ ...ingestForm, pdf_filename: e.target.value })
          }
          required
        />
        <input
          style={styles.input}
          placeholder="Department"
          value={ingestForm.owner_department}
          onChange={(e) =>
            setIngestForm({ ...ingestForm, owner_department: e.target.value })
          }
          required
        />
        <input
          style={styles.input}
          type="number"
          min={1}
          value={ingestForm.min_role_level}
          onChange={(e) =>
            setIngestForm({
              ...ingestForm,
              min_role_level: +e.target.value,
            })
          }
        />
        <input
          style={styles.input}
          type="number"
          min={1}
          value={ingestForm.min_clearance_level}
          onChange={(e) =>
            setIngestForm({
              ...ingestForm,
              min_clearance_level: +e.target.value,
            })
          }
        />
        <button style={styles.primaryBtn} disabled={ingesting}>
          Ingest PDF
        </button>
      </form>

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
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={5} style={styles.empty}>
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

/* ================= STYLES (MATCH ADMIN USERS) ================= */

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
  title: { fontSize: "1.75rem" },
  error: {
    background: "rgba(239,68,68,.15)",
    border: "1px solid rgba(239,68,68,.3)",
    padding: "0.75rem",
    marginBottom: "1rem",
  },
  success: {
    background: "rgba(59,130,246,.15)",
    border: "1px solid rgba(59,130,246,.3)",
    padding: "0.75rem",
    marginBottom: "1rem",
  },
  form: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))",
    gap: "0.75rem",
    marginBottom: "1.5rem",
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
    padding: "10px",
    fontSize: "0.75rem",
    textTransform: "uppercase",
    color: "#9ca3af",
    borderBottom: "1px solid #374151",
    textAlign: "left",
  },
  td: {
    padding: "10px",
    borderBottom: "1px solid #1f2937",
  },
  deleteBtn: {
    background: "#dc2626",
    color: "#fff",
    border: "none",
    padding: "0.35rem 0.6rem",
    borderRadius: 4,
    cursor: "pointer",
  },
  empty: {
    textAlign: "center",
    padding: "1.5rem",
    color: "#9ca3af",
  },
};
