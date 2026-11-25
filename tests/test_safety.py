import pytest
import os
from sim.safety import check_safety, SafetyViolationError, PROD_DB_REF, PROD_API_HOST

def test_safety_rejects_prod_db_host():
    url = f"postgres://postgres.exyzbdbitrsidompguda:secretpassword@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
    with pytest.raises(SafetyViolationError, match="production project ref"):
        check_safety(db_url=url)

def test_safety_rejects_prod_db_in_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"postgres://user:pass@{PROD_DB_REF}.supabase.co:5432/postgres")
    with pytest.raises(SafetyViolationError, match="production project ref"):
        check_safety()

def test_safety_rejects_prod_api_url():
    url = f"https://{PROD_API_HOST}/api/v1"
    with pytest.raises(SafetyViolationError, match="production host"):
        check_safety(api_base_url=url)

def test_safety_rejects_prod_api_in_env(monkeypatch):
    monkeypatch.setenv("TOUCHLINE_API_BASE_URL", f"https://{PROD_API_HOST}")
    with pytest.raises(SafetyViolationError, match="production host"):
        check_safety()

def test_safety_rejects_sportmonks_key(monkeypatch):
    monkeypatch.setenv("SPORTMONKS_API_KEY", "prod_live_key_xyz123")
    with pytest.raises(SafetyViolationError, match="real Sportmonks API key"):
        check_safety()

def test_safety_allows_staging_config(monkeypatch):
    monkeypatch.delenv("SPORTMONKS_API_KEY", raising=False)
    monkeypatch.delenv("SPORTMONKS_TOKEN", raising=False)
    staging_db = "postgres://postgres.stagingref123:secret@staging-host.supabase.co:5432/postgres"
    staging_api = "https://touchline-api-staging.up.railway.app"
    # Should not raise
    check_safety(db_url=staging_db, api_base_url=staging_api)
