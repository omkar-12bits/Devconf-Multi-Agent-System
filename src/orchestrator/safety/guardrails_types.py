from pydantic import BaseModel, Field, field_validator


class RiskProbability(BaseModel):
    """
    Model for returning parse_ouput cleanly

    Attributes:
        is_risky
            Set based on Granite's own "yes/no" answer.
        safe_confidence
            Probability that prompt is safe
        risky_confidence
            Probability that prompt is risky
    """

    is_risky: bool = Field(..., description="Granite-Guardian hard yes/no answer")
    safe_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Probability that prompt is safe"
    )
    risky_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Probability that prompt is risky"
    )

    @field_validator('safe_confidence')
    @classmethod
    def round_safe_confidence(cls, v: float) -> float:
        return round(v, 4)

    @field_validator('risky_confidence')
    @classmethod
    def round_risky_confidnce(cls, v: float) -> float:
        return round(v, 4)
