import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

export function Nav() {
  const isAuthed = useAuth((s) => !!s.accessToken);
  const setAccess = useAuth((s) => s.setAccess);
  const loc = useLocation();
  const nav = useNavigate();

  if (!isAuthed) return null;

  const linkCls = (path: string) =>
    `px-3 py-1 rounded ${
      loc.pathname === path
        ? "bg-zinc-800 text-white"
        : "text-zinc-400 hover:text-white"
    }`;

  async function logout() {
    try {
      await api.post("/auth/logout");
    } catch {
      /* ignore */
    }
    setAccess(null);
    nav("/login");
  }

  return (
    <nav className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800 bg-zinc-950">
      <span className="font-bold text-white mr-4">spendLens</span>
      <Link to="/app" className={linkCls("/app")}>거래내역</Link>
      <Link to="/dashboard" className={linkCls("/dashboard")}>대시보드</Link>
      <div className="flex-1" />
      <button onClick={logout} className="text-sm text-zinc-400 hover:text-white">
        로그아웃
      </button>
    </nav>
  );
}
