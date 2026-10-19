import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

const postMock = vi.hoisted(() => vi.fn());
vi.mock("../lib/api", () => ({ api: { post: postMock } }));

import { LoginPage } from "./login";

function submitWith(error: unknown) {
  postMock.mockRejectedValueOnce(error);
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByPlaceholderText(/이메일/), { target: { value: "a@b.com" } });
  fireEvent.change(screen.getByPlaceholderText(/비번/), { target: { value: "abcd1234" } });
  fireEvent.click(screen.getByRole("button", { name: /로그인/ }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    postMock.mockReset();
    navigate.mockReset();
  });

  it("shows credential mismatch on 401", async () => {
    submitWith({ response: { status: 401, data: { detail: "INVALID_CREDENTIALS" } } });
    expect(await screen.findByText("이메일 또는 비번 불일치")).toBeInTheDocument();
  });

  it("shows rate limit message on 429", async () => {
    submitWith({ response: { status: 429, data: { detail: "TOO_MANY_REQUESTS" } } });
    expect(await screen.findByText(/로그인 시도가 너무 많습니다/)).toBeInTheDocument();
  });

  it("shows generic failure on network/server error", async () => {
    submitWith(new Error("Network Error"));
    expect(await screen.findByText(/로그인에 실패했습니다/)).toBeInTheDocument();
  });
});
