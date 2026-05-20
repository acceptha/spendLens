import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LandingPage } from "./routes";
import { GuestPage } from "./routes/guest";
import { LoginPage } from "./routes/login";
import { SignupPage } from "./routes/signup";
import { AppPage } from "./routes/app";
import { DashboardPage } from "./routes/dashboard";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Nav } from "./components/Nav";

export function App() {
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
