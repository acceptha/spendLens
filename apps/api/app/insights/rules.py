"""LLM 없이 집계 수치만으로 월간 인사이트 생성 (룰 기반 폴백).

ANTHROPIC_API_KEY가 설정되지 않았을 때 service가 이 모듈을 사용한다.
출력 형태는 llm.generate_insight와 동일: {"summary": str, "highlights": [...]}.
highlight type은 llm._ALLOWED_TYPES와 동일(top_growth / anomaly / saving_tip).
"""
from decimal import Decimal

from app.categorization.essential import ESSENTIAL_DEFAULTS


def _won(amount: object) -> str:
    return f"₩{int(Decimal(str(amount))):,}"


def _dec(amount: object) -> Decimal:
    return Decimal(str(amount if amount is not None else 0))


def build_insight(aggregates: dict) -> dict:
    """집계 dict → {summary, highlights}. LLM 호출 없음, 결정적."""
    summary_agg = aggregates.get("summary") or {}
    by_category = aggregates.get("by_category") or []
    top_merchants = aggregates.get("top_merchants") or []

    total = _dec(summary_agg.get("total_amount"))

    if total <= 0 and not by_category:
        return {"summary": "이번 달 지출 내역이 없습니다.", "highlights": []}

    # --- summary 문장 ---
    parts = [f"이번 달 지출 {_won(total)}"]
    diff = summary_agg.get("prev_month_diff_pct")
    if diff is not None:
        parts.append(f"전월 대비 {'+' if diff >= 0 else ''}{diff:.0f}%")
    net = summary_agg.get("net_savings")
    if net is not None:
        parts.append(f"순저축 {_won(net)}")
    rate = summary_agg.get("savings_rate")
    if rate is not None:
        parts.append(f"저축률 {rate:.0f}%")
    summary_text = " · ".join(parts) + "."

    highlights: list[dict] = []
    cats = sorted(by_category, key=lambda c: _dec(c["amount"]), reverse=True)

    # top_growth — 이번 달 최대 지출 카테고리
    if cats:
        top = cats[0]
        highlights.append({
            "type": "top_growth",
            "title": f"{top['category']} 최다 지출",
            "detail": f"이번 달 가장 큰 카테고리 — {_won(top['amount'])} ({top['count']}건)",
        })

    # anomaly — 최대 단일 가맹점
    if top_merchants:
        m = top_merchants[0]
        highlights.append({
            "type": "anomaly",
            "title": f"최대 지출처: {m['merchant_raw']}",
            "detail": f"{_won(m['amount'])} ({m['count']}건)",
        })

    # saving_tip — 비필수 카테고리 중 최대
    non_essential = [c for c in cats if not ESSENTIAL_DEFAULTS.get(c["category"], False)]
    if non_essential:
        s = non_essential[0]
        highlights.append({
            "type": "saving_tip",
            "title": f"절약 포인트: {s['category']}",
            "detail": f"비필수 지출 중 가장 큼 — {_won(s['amount'])}. 줄이면 저축 여력이 늘어요.",
        })

    return {"summary": summary_text, "highlights": highlights[:3]}
