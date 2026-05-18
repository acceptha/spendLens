import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const setAccess = useAuth((s) => s.setAccess);
  const nav = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const resp = await api.post("/auth/login", { email, password: pwd });
      setAccess(resp.data.access_token);
      nav("/app");
    } catch {
      setErr("이메일 또는 비번 불일치");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <form onSubmit={submit} className="w-full max-w-sm space-y-3">
        <h2 className="text-2xl mb-2">로그인</h2>
        <input className="w-full p-2 bg-zinc-900 border border-zinc-700 rounded"
               placeholder="이메일" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="w-full p-2 bg-zinc-900 border border-zinc-700 rounded" type="password"
               placeholder="비번" value={pwd} onChange={(e) => setPwd(e.target.value)} />
        {err && <p className="text-red-400 text-sm">{err}</p>}
        <button className="w-full p-2 bg-blue-600 rounded">로그인</button>
        <p className="text-sm text-zinc-400 mt-2">
          계정이 없으신가요?{" "}
          <Link to="/signup" className="underline">회원가입</Link>
        </p>
      </form>
    </div>
  );
}
