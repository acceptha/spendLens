import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../stores/auth";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const authReady = useAuth((s) => s.authReady);
  const isAuthed = useAuth((s) => s.isAuthed());

  // 부팅 시 refresh 쿠키로 access token을 재수화하는 중 — 끝나기 전엔 리다이렉트 보류
  // (새로고침/직접 진입 시 로그인 페이지로 튕기는 문제 방지).
  if (!authReady) {
    return (
      <div className="min-h-screen flex items-center justify-center text-zinc-400 text-sm">
        로딩…
      </div>
    );
  }
  if (!isAuthed) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
