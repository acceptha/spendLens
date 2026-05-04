import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-5xl font-bold">spendLens</h1>
      <p className="text-zinc-400 text-center max-w-xl">
        광고 없는 가계부 · 데이터는 내 서버 · AI 코칭 (W2 예정)
      </p>
      <div className="flex gap-4">
        <Link to="/guest" className="px-6 py-3 bg-blue-600 rounded">▶ Guest Demo</Link>
        <Link to="/login" className="px-6 py-3 border border-zinc-600 rounded">로그인</Link>
      </div>
    </div>
  );
}
