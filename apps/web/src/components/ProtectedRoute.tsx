import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../stores/auth";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const isAuthed = useAuth((s) => s.isAuthed());
  if (!isAuthed) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
