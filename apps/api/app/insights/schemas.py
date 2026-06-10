from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class InsightHighlight(BaseModel):
    type: Literal["top_growth", "anomaly", "saving_tip"]
    title: str
    detail: str


class InsightResponse(BaseModel):
    month: str
    summary: str
    highlights: list[InsightHighlight]
    generated_at: datetime


class InsightGenerateRequest(BaseModel):
    month: str
