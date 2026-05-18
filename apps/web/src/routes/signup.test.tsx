import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

const postMock = vi.hoisted(() => vi.fn());
vi.mock("../lib/api", () => ({ api: { post: postMock } }));

import { SignupPage } from "./signup";

function setup() {
  return render(
    <MemoryRouter>
      <SignupPage />
    </MemoryRouter>,
  );
}

describe("SignupPage", () => {
  beforeEach(() => {
    postMock.mockReset();
    navigate.mockReset();
  });

  it("submits signup and navigates to /app", async () => {
    postMock.mockResolvedValueOnce({ data: { access_token: "tok-123" } });
    setup();
    fireEvent.change(screen.getByPlaceholderText(/이메일/), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByPlaceholderText(/비번/), { target: { value: "abcd1234" } });
    fireEvent.click(screen.getByRole("button", { name: /가입/ }));
    await waitFor(() =>
      expect(postMock).toHaveBeenCalledWith("/auth/signup", {
        email: "new@example.com",
        password: "abcd1234",
      }),
    );
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/app"));
  });

  it("shows WEAK_PASSWORD message", async () => {
    postMock.mockRejectedValueOnce({ response: { status: 400, data: { detail: "WEAK_PASSWORD" } } });
    setup();
    fireEvent.change(screen.getByPlaceholderText(/이메일/), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText(/비번/), { target: { value: "abcd1234" } });
    fireEvent.click(screen.getByRole("button", { name: /가입/ }));
    expect(await screen.findByText(/영문과 숫자/)).toBeInTheDocument();
  });

  it("shows EMAIL_ALREADY_EXISTS message", async () => {
    postMock.mockRejectedValueOnce({ response: { status: 409, data: { detail: "EMAIL_ALREADY_EXISTS" } } });
    setup();
    fireEvent.change(screen.getByPlaceholderText(/이메일/), { target: { value: "dup@a.com" } });
    fireEvent.change(screen.getByPlaceholderText(/비번/), { target: { value: "abcd1234" } });
    fireEvent.click(screen.getByRole("button", { name: /가입/ }));
    expect(await screen.findByText(/이미 가입된/)).toBeInTheDocument();
  });

  it("shows TOO_MANY_REQUESTS message", async () => {
    postMock.mockRejectedValueOnce({ response: { status: 429, data: { detail: "TOO_MANY_REQUESTS" } } });
    setup();
    fireEvent.change(screen.getByPlaceholderText(/이메일/), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText(/비번/), { target: { value: "abcd1234" } });
    fireEvent.click(screen.getByRole("button", { name: /가입/ }));
    expect(await screen.findByText(/요청이 너무 많/)).toBeInTheDocument();
  });
});
