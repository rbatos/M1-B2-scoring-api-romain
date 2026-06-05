"""Pydantic schemas for the Pyrenex Risk API.

Align LoanApplication with the feature_columns from your
pyrenex_risk_v2.json metadata (M1-B1 output).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoanApplication(BaseModel):
    """Input schema for /predict.

    Les bornes des champs reflètent les plages observées dans le dataset
    d'entraînement et servent de garde-fou contre les entrées aberrantes.
    """

    loan_amnt: float = Field(..., ge=500, le=40_000, description="Loan amount (USD)")
    term: str = Field(..., description="Loan term, e.g. '36 months' or '60 months'")
    int_rate: float = Field(..., ge=0, le=50, description="Interest rate (%)")
    annual_inc: float = Field(..., ge=0, le=10_000_000, description="Annual income (USD)")
    purpose: str = Field(..., description="Purpose of the loan")
    installment: float = Field(..., ge=0, description="Monthly installment (USD)")
    grade: str = Field(..., description="Loan grade, e.g. 'A', 'B', ..., G")
    emp_length: str = Field(..., description="Employment length, e.g. '3 years', '10+ years'")
    home_ownership: str = Field(..., description="Home ownership status, e.g. 'RENT', 'MORTGAGE', 'OWN'")
    verification_status: str = Field(..., description="Verification status, e.g. 'Verified', 'Not Verified', 'Source Verified'")
    dti: float = Field(..., ge=0, le=50, description="Debt-to-income ratio")
    delinq_2yrs: int = Field(..., ge=0, le=10, description="Number of delinquencies in the past 2 years")
    fico_range_low: int = Field(..., ge=300, le=850, description="Lower bound of FICO score range")
    revol_util: float = Field(..., ge=0, le=200, description="Revolving line utilization rate (%)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "loan_amnt": 10000,
                "term": "36 months",
                "int_rate": 12.5,
                "annual_inc": 75000,
                "purpose": "debt_consolidation",
                "installment": 333.33,
                "grade": "B",
                "emp_length": "5 years",
                "home_ownership": "MORTGAGE",
                "verification_status": "Verified",
                "dti": 15.0,
                "delinq_2yrs": 0,
                "fico_range_low": 700,
                "revol_util": 30.0,
                "loan_amnt": 7600,
            }
        }
    }


class Prediction(BaseModel):
    """Output schema for /predict."""

    prediction: int = Field(..., description="0 = Fully Paid, 1 = Charged Off")
    probability: float = Field(..., ge=0.0, le=1.0)
    model_version: str
    request_id: str


class HealthResponse(BaseModel):
    status: str
