import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

const ERROR_MESSAGES: Record<string, string> = {
  WEAK_PASSWORD: "비밀번호는 8자 이상, 영문과 숫자를 모두 포함해야 합니다.",
  EMAIL_ALREADY_EXISTS: "이미 가입된 이메일입니다.",
  TOO_MANY_REQUESTS: "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
};

export function SignupPage() {
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const setAccess = useAuth((s) => s.setAccess);
  const nav = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSubmitting(true);
    try {
      const resp = await api.post("/auth/signup", { email, password: pwd });
      setAccess(resp.data.access_token);
      nav("/app");
    } catch (e) {
      const code =
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "UNKNOWN";
      setErr(ERROR_MESSAGES[code] ?? "가입에 실패했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <form onSubmit={submit} className="w-full max-w-sm space-y-3">
        <h2 className="text-2xl mb-2">회원가입</h2>
        <input className="w-full p-2 bg-zinc-900 border border-zinc-700 rounded"
               type="email" placeholder="이메일" value={email}
               onChange={(e) => setEmail(e.target.value)} required />
        <input className="w-full p-2 bg-zinc-900 border border-zinc-700 rounded"
               type="password" placeholder="비번 (8자 이상, 영문+숫자)" value={pwd}
               onChange={(e) => setPwd(e.target.value)} required minLength={8} />
        {err && <p className="text-red-400 text-sm">{err}</p>}
        <button className="w-full p-2 bg-blue-600 rounded disabled:opacity-50"
                disabled={submitting}>
          {submitting ? "처리 중…" : "가입"}
        </button>
        <p className="text-sm text-zinc-400 mt-2">
          이미 계정이 있으신가요?{" "}
          <Link to="/login" className="underline">로그인</Link>
        </p>
      </form>
    </div>
  );
}
