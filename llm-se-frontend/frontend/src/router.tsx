import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Chat from "./pages/Chat";
import AdminUsers from "./pages/admin/AdminUsers";
import AdminDocuments from "./pages/admin/AdminDocs";
import { useAuth } from "./context/AuthContext";
import React from "react";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/" replace />;
  if (user.role_level < 3) return <Navigate to="/chat" replace />;
  return <>{children}</>;
}

export default function Router() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />

        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          }
        />

        {/* 🔐 Admin Pages */}
        <Route
          path="/admin/users"
          element={
            <AdminRoute>
              <AdminUsers />
            </AdminRoute>
          }
        />

        <Route
          path="/admin/documents"
          element={
            <AdminRoute>
              <AdminDocuments />
            </AdminRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
