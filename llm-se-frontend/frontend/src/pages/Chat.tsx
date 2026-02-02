import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import ChatBox from "../components/ChatBox";

export default function Chat() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    setUser(null);
    localStorage.removeItem("token");
    navigate("/");
  }

  const isAdmin = user && user.role_level >= 3;

  return (
    <div style={styles.page}>
      {/* Top Bar */}
      <div style={styles.header}>
        <div style={styles.titleGroup}>
          <div style={styles.title}>Sentinel</div>
          <div style={styles.subtitle}>
            Enterprise RBAC-secured RAG System
          </div>
        </div>

        <div style={styles.actions}>
          {isAdmin && (
            <>
              <button style={styles.navButton} onClick={() => navigate("/admin/users")}>
                Users
              </button>
              <button style={styles.navButton} onClick={() => navigate("/admin/documents")}>
                Documents
              </button>
            </>
          )}

          <span style={styles.welcome}>
  Welcome{" "}
  <span style={styles.username}>
    {user?.username}
  </span>
</span>


          <button style={styles.logout} onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>

      {/* Chat Area */}
      <div style={styles.chatArea}>
        <ChatBox />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  username: {
  fontWeight: 600,
  color: "#e5e7eb",
  letterSpacing: "0.3px",
},

  page: {
    height: "100vh",
    width: "100vw",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    background:
      "linear-gradient(135deg, #0f1115 0%, #151922 40%, #0b0d12 100%)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "14px 24px",
    borderBottom: "1px solid #1f2430",
    background:
      "linear-gradient(135deg, #0f1115 0%, #151922 60%)",
  },
  titleGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  },
  title: {
    fontSize: "1.2rem",
    fontWeight: 600,
    color: "#e5e7eb",
    letterSpacing: "0.3px",
  },
  subtitle: {
    fontSize: "0.75rem",
    color: "#9ca3af",
  },
  actions: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  navButton: {
    backgroundColor: "#1f2430",
    border: "1px solid #2d3342",
    color: "#e5e7eb",
    padding: "6px 12px",
    borderRadius: "6px",
    cursor: "pointer",
    fontSize: "0.8rem",
  },
  welcome: {
    fontSize: "1rem",
    color: "#9ca3af",
  },
  logout: {
    backgroundColor: "#3b82f6",
    border: "none",
    color: "#ffffff",
    padding: "6px 14px",
    borderRadius: "6px",
    cursor: "pointer",
    fontSize: "0.8rem",
  },
  chatArea: {
    flex: 1,
    overflow: "hidden",
  },
};
