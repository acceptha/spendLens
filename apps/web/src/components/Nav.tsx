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
    `px-2 sm:px-3 py-1 rounded text-sm sm:text-base whitespace-nowrap shrink-0 ${
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
    <nav className="flex items-center gap-1 sm:gap-2 px-3 sm:px-4 py-3 border-b border-zinc-800 bg-zinc-950">
      {/* 모바일(375px)에선 메뉴 4개가 들어가도록 로고 숨김 */}
      <span className="hidden sm:inline font-bold text-base text-white mr-4 shrink-0 whitespace-nowrap">spendLens</span>
      <Link to="/app" className={linkCls("/app")}>거래내역</Link>
      <Link to="/dashboard" className={linkCls("/dashboard")}>대시보드</Link>
      <Link to="/budget" className={linkCls("/budget")}>예산</Link>
      <Link to="/report" className={linkCls("/report")}>결산</Link>
      <div className="flex-1" />
      <button onClick={logout} className="text-sm text-zinc-400 hover:text-white whitespace-nowrap shrink-0">
        로그아웃
      </button>
    </nav>
  );
}
