import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import { useAuth } from "../stores/auth";

function renderProtected() {
  return render(
    <MemoryRouter initialEntries={["/secret"]}>
      <Routes>
        <Route
          path="/secret"
          element={
            <ProtectedRoute>
              <div>SECRET</div>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<div>LOGIN PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    useAuth.setState({ accessToken: null, authReady: false });
  });

  it("shows loading while auth is bootstrapping (no redirect yet)", () => {
    useAuth.setState({ authReady: false, accessToken: null });
    renderProtected();
    expect(screen.getByText("로딩…")).toBeInTheDocument();
    // must NOT have bounced to /login while the refresh attempt is in flight
    expect(screen.queryByText("LOGIN PAGE")).not.toBeInTheDocument();
    expect(screen.queryByText("SECRET")).not.toBeInTheDocument();
  });

  it("redirects to /login once ready and not authed", () => {
    useAuth.setState({ authReady: true, accessToken: null });
    renderProtected();
    expect(screen.getByText("LOGIN PAGE")).toBeInTheDocument();
  });

  it("renders children once ready and authed", () => {
    useAuth.setState({ authReady: true, accessToken: "tok" });
    renderProtected();
    expect(screen.getByText("SECRET")).toBeInTheDocument();
  });
});
