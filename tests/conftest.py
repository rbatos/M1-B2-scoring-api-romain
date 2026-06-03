"""Shared fixtures for M1-B2 tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """TestClient with lifespan triggered (model loaded)."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_payload() -> dict:
    """Valid loan application payload.

    TODO — Align with the actual LoanApplication schema and feature_columns
    of pyrenex_risk_v2.json. The example below is a placeholder.
    """
    return {
        "loan_amnt": 10000,
        "term": "36 months",
        "int_rate": 12.5,
        "annual_inc": 60000,
        "purpose": "debt_consolidation",
        # TODO — Add the remaining fields
    }
