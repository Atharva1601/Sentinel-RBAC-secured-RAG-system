import { useAuth } from "../context/AuthContext";

export default function Admin() {
  const { user } = useAuth();

  if (!user || user.role_level !== 3) {
    return <p>Access denied</p>;
  }

  return (
    <div style={{ padding: 40 }}>
      <h2>Admin Panel</h2>
      <p>User management and document ingestion will go here.</p>
    </div>
  );
}
