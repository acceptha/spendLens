import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LandingPage } from "./routes";
import { LoginPage } from "./routes/login";
import { SignupPage } from "./routes/signup";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Nav } from "./components/Nav";
import { refreshAccessToken } from "./lib/api";
import { useAuth } from "./stores/auth";

// 무거운/비초기 라우트는 지연 로딩 — 특히 대시보드의 Tremor+recharts를 별도 청크로 분리해
// 랜딩/로그인 초기 번들을 가볍게 유지한다.
const GuestPage = lazy(() =>
  import("./routes/guest").then((m) => ({ default: m.GuestPage })),
);
const AppPage = lazy(() =>
  import("./routes/app").then((m) => ({ default: m.AppPage })),
);
const DashboardPage = lazy(() =>
  import("./routes/dashboard").then((m) => ({ default: m.DashboardPage })),
);

export function App() {
  const setAuthReady = useAuth((s) => s.setAuthReady);

  // 부팅 시 refresh 쿠키로 access token을 선제 재수화. 성공/실패와 무관하게
  // authReady=true로 만들어 ProtectedRoute가 그제서야 인증을 판정하게 한다.
  useEffect(() => {
    refreshAccessToken().finally(() => setAuthReady(true));
  }, [setAuthReady]);

  return (
    <BrowserRouter>
      <Nav />
      <Suspense fallback={<div className="p-8 text-zinc-400 text-sm">로딩…</div>}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/guest" element={<GuestPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/app" element={<ProtectedRoute><AppPage /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
