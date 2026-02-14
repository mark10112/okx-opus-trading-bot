"""ScreenResult Pydantic model."""

from datetime import datetime

from pydantic import BaseModel


class ScreenResult(BaseModel):
    signal: bool = False
    reason: str = ""
    tokens_used: int = 0
    timestamp: datetime = datetime.utcnow()
