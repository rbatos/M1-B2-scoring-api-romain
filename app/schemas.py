"""Pydantic schemas for the Pyrenex Risk API.

TODO — Align LoanApplication with the feature_columns from your
pyrenex_risk_v2.json metadata (M1-B1 output).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoanApplication(BaseModel):
    """Input schema for /predict.

    TODO — Replace placeholder fields with the actual feature_columns
    from your pyrenex_risk_v2.json. Add Field(..., ge=…, le=…) bounds
    where your EDA showed reasonable ranges.
    """

    loan_amnt: float = Field(..., ge=500, le=40_000, description="Loan amount (USD)")
    term: str = Field(..., description="Loan term, e.g. '36 months' or '60 months'")
    int_rate: float = Field(..., ge=0, le=50, description="Interest rate (%)")
    annual_inc: float = Field(..., ge=0, le=10_000_000, description="Annual income (USD)")
    purpose: str = Field(..., description="Purpose of the loan")
    # TODO — Add the rest of your feature columns


class Prediction(BaseModel):
    """Output schema for /predict."""

    prediction: int = Field(..., description="0 = Fully Paid, 1 = Charged Off")
    probability: float = Field(..., ge=0.0, le=1.0)
    model_version: str
    request_id: str


class HealthResponse(BaseModel):
    status: str
