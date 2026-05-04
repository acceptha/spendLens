import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LandingPage } from "./routes";
import { GuestPage } from "./routes/guest";
import { LoginPage } from "./routes/login";
import { AppPage } from "./routes/app";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/guest" element={<GuestPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app" element={<AppPage />} />
      </Routes>
    </BrowserRouter>
  );
}
