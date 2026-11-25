import os
from urllib.parse import urlparse

PROD_DB_REF = "exyzbdbitrsidompguda"
PROD_API_HOST = "touchline-api-production-ed283561.up.railway.app"

class SafetyViolationError(RuntimeError):
    """Raised when an environment or target points to production or uses production keys."""
    pass

def check_safety(db_url: str = None, api_base_url: str = None) -> None:
    """
    Hard guard: refuse to run, with a clear error, if any of:
    1. The database host or user contains the production project ref 'exyzbdbitrsidompguda'
    2. The API base URL contains 'touchline-api-production-ed283561.up.railway.app'
    3. A real Sportmonks API key is configured
    """
    # 1. Sportmonks API key check
    for key in ("SPORTMONKS_API_KEY", "SPORTMONKS_TOKEN", "SPORTMONKS_KEY"):
        val = os.environ.get(key, "").strip()
        if val and not val.startswith("fake_") and not val.startswith("mock_") and not val.startswith("sim_"):
            raise SafetyViolationError(
                f"SAFETY VIOLATION: A real Sportmonks API key is configured in {key}. "
                "The simulator must never use a real Sportmonks API key."
            )

    # 2. Database URL check
    db = db_url or os.environ.get("DATABASE_URL", "")
    if db:
        parsed = urlparse(db)
        hostname = (parsed.hostname or "").lower()
        username = (parsed.username or "").lower()
        raw_db = db.lower()

        if PROD_DB_REF in hostname or PROD_DB_REF in username or PROD_DB_REF in raw_db:
            raise SafetyViolationError(
                f"SAFETY VIOLATION: Database connection contains production project ref '{PROD_DB_REF}'. "
                "Refusing to connect to production database."
            )

    # 3. API URL check
    api = api_base_url or os.environ.get("TOUCHLINE_API_BASE_URL", "") or os.environ.get("API_BASE_URL", "")
    if api:
        api_lower = api.lower()
        if PROD_API_HOST in api_lower:
            raise SafetyViolationError(
                f"SAFETY VIOLATION: API base URL points to production host '{PROD_API_HOST}'. "
                "Refusing to run tests against the production API."
            )
