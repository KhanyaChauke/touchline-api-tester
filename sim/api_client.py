"""
HTTP client for communicating with the Staging Touchline API.
Records status codes, response data, and traceId for all checks.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple
from .safety import check_safety

class TouchlineApiClient:
    def __init__(self, base_url: Optional[str] = None, admin_token: Optional[str] = None):
        self.base_url = (base_url or os.environ.get("TOUCHLINE_API_BASE_URL", "")).rstrip("/")
        self.admin_token = admin_token or os.environ.get("TOUCHLINE_ADMIN_TOKEN", "")
        # Enforce safety check!
        check_safety(api_base_url=self.base_url)

    def request(
        self,
        method: str,
        endpoint: str,
        token: Optional[str] = None,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        """
        Send an HTTP request to the Touchline API.
        Returns: (status_code, response_json_or_dict, traceId)
        """
        check_safety(api_base_url=self.base_url)
        if not self.base_url:
            return (0, {"error": "API base URL not configured"}, None)

        url = f"{self.base_url}{endpoint}"
        req_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        if headers:
            req_headers.update(headers)
        
        auth_token = token or self.admin_token
        if auth_token:
            req_headers["Authorization"] = f"Bearer {auth_token}"

        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())

        trace_id = None
        status = 0
        res_json = None

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
                trace_id = resp.headers.get("x-trace-id") or resp.headers.get("traceparent")
                raw = resp.read().decode("utf-8")
                if raw:
                    try:
                        res_json = json.loads(raw)
                        if isinstance(res_json, dict) and not trace_id:
                            trace_id = res_json.get("traceId")
                    except Exception:
                        res_json = {"raw": raw}
        except urllib.error.HTTPError as e:
            status = e.code
            trace_id = e.headers.get("x-trace-id") or e.headers.get("traceparent")
            err_raw = e.read().decode("utf-8")
            if err_raw:
                try:
                    res_json = json.loads(err_raw)
                    if isinstance(res_json, dict) and not trace_id:
                        trace_id = res_json.get("traceId")
                except Exception:
                    res_json = {"error": err_raw}
        except Exception as e:
            status = 500
            res_json = {"error": str(e)}

        return (status, res_json, trace_id)

    # Specific Endpoints
    def get_fixture(self, fixture_id: int) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        return self.request("GET", f"/api/v1/fixtures/{fixture_id}")

    def list_fixtures(self) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        return self.request("GET", "/api/v1/fixtures")

    def create_gameweek(self, season_id: int, name: str, start_date: str, end_date: str, deadline_at: str) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        body = {
            "seasonId": season_id,
            "name": name,
            "startDate": start_date,
            "endDate": end_date,
            "deadlineAt": deadline_at
        }
        return self.request("POST", "/api/v1/admin/gameweeks", body=body)

    def assign_fixture_gameweek(self, fixture_id: int, gameweek_id: int, reason: str = "Sim gameweek setup") -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        body = {
            "gameweekId": gameweek_id,
            "reason": reason,
            "confirmLockedChange": True
        }
        return self.request("PUT", f"/api/v1/admin/fixtures/{fixture_id}/gameweek", body=body)

    def lock_gameweek(self, gameweek_id: int) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        return self.request("POST", f"/api/v1/admin/gameweeks/{gameweek_id}/lock")

    def resolve_fixture(self, fixture_id: int, outcome: str = "final", reason: str = "Sim completed") -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        body = {"outcome": outcome, "reason": reason}
        return self.request("POST", f"/api/v1/admin/fixtures/{fixture_id}/resolution", body=body)

    def settle_gameweek(self, gameweek_id: int) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        return self.request("POST", f"/api/v1/admin/gameweeks/{gameweek_id}/settlement")

    def get_points_explanation(self, gameweek_id: int, manager_token: Optional[str] = None) -> Tuple[int, Optional[Dict[str, Any]], Optional[str]]:
        return self.request("GET", f"/api/v1/fantasy/team/points/explain?gameweek={gameweek_id}", token=manager_token)
