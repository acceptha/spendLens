import { useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LandingPage } from "./routes";
import { GuestPage } from "./routes/guest";
import { LoginPage } from "./routes/login";
import { SignupPage } from "./routes/signup";
import { AppPage } from "./routes/app";
import { DashboardPage } from "./routes/dashboard";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Nav } from "./components/Nav";
import { refreshAccessToken } from "./lib/api";
import { useAuth } from "./stores/auth";

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
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/guest" element={<GuestPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/app" element={<ProtectedRoute><AppPage /></ProtectedRoute>} />
        <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  );
}
