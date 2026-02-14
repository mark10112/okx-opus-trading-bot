"""TradeReview, DeepReflectionResult Pydantic models."""

from pydantic import BaseModel

from orchestrator.models.playbook import Playbook


class TradeReview(BaseModel):
    outcome: str = ""
    execution_quality: str = ""
    entry_timing: str = ""
    exit_timing: str = ""
    what_went_right: list[str] = []
    what_went_wrong: list[str] = []
    lesson: str = ""
    should_update_playbook: bool = False
    playbook_suggestion: str | None = None


class DeepReflectionResult(BaseModel):
    updated_playbook: Playbook = Playbook()
    pattern_insights: list[str] = []
    bias_findings: list[str] = []
    discipline_score: int = 0
    summary: str = ""
