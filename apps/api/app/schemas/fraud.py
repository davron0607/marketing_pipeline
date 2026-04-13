from pydantic import BaseModel
from datetime import datetime


class FraudFlagResponse(BaseModel):
    id: int
    respondent_id: str
    flag_type: str
    confidence: float
    details: str | None

    model_config = {"from_attributes": True}


class FraudSummaryResponse(BaseModel):
    total_respondents: int
    flagged_count: int
    fraud_rate: float
    flags: list[FraudFlagResponse]
