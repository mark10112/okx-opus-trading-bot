"""Playbook, StrategyDef, Lesson Pydantic models."""

from datetime import datetime

from pydantic import BaseModel


class RegimeRule(BaseModel):
    preferred_strategies: list[str] = []
    avoid_strategies: list[str] = []
    max_position_pct: float = 0.05
    preferred_timeframe: str = "1H"


class StrategyDef(BaseModel):
    entry: str = ""
    exit: str = ""
    filters: list[str] = []
    historical_winrate: float = 0.0
    avg_rr: float = 0.0


class Lesson(BaseModel):
    id: str = ""
    date: str = ""
    lesson: str = ""
    evidence: str = ""
    impact: str = ""


class TimeFilter(BaseModel):
    avoid_hours_utc: list[int] = []
    preferred_hours_utc: list[int] = []


class CalibrationEntry(BaseModel):
    stated_confidence: float = 0.0
    actual_winrate: float = 0.0
    sample_size: int = 0


class Playbook(BaseModel):
    version: int = 1
    last_updated: datetime = datetime.utcnow()
    market_regime_rules: dict[str, RegimeRule] = {}
    strategy_definitions: dict[str, StrategyDef] = {}
    lessons_learned: list[Lesson] = []
    confidence_calibration: dict[str, CalibrationEntry] = {}
    time_filters: TimeFilter = TimeFilter()
