import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const { postMock, navigateMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  navigateMock: vi.fn(),
}));

vi.mock("../lib/api", () => ({ api: { post: postMock } }));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return { ...actual, useNavigate: () => navigateMock };
});

import { Nav } from "./Nav";
import { useAuth } from "../stores/auth";

describe("Nav", () => {
  beforeEach(() => {
    useAuth.setState({ accessToken: null });
    postMock.mockReset();
    navigateMock.mockReset();
  });

  it("renders nothing when not authed", () => {
    const { container } = render(
      <MemoryRouter>
        <Nav />
      </MemoryRouter>,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders links when authed", () => {
    useAuth.setState({ accessToken: "fake-token" });
    render(
      <MemoryRouter>
        <Nav />
      </MemoryRouter>,
    );
    expect(screen.getByText("거래내역")).toBeInTheDocument();
    expect(screen.getByText("대시보드")).toBeInTheDocument();
    expect(screen.getByText("로그아웃")).toBeInTheDocument();
    expect(screen.getByText("spendLens")).toBeInTheDocument();
  });

  it("logout clears token + navigates to /login (even if api fails)", async () => {
    postMock.mockRejectedValueOnce(new Error("network down"));
    useAuth.setState({ accessToken: "fake-token" });
    render(
      <MemoryRouter>
        <Nav />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByText("로그아웃"));

    // api 실패와 무관하게 항상 setAccess(null) + navigate("/login")
    await waitFor(() => {
      expect(useAuth.getState().accessToken).toBeNull();
      expect(navigateMock).toHaveBeenCalledWith("/login");
    });
    expect(postMock).toHaveBeenCalledWith("/auth/logout");
  });
});
