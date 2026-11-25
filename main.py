"""
Railway Web Server and CLI entrypoint for touchline-sim.
Supports HTTP endpoints protected by X-Sim-Key header:
- POST /sim/start
- POST /sim/stop
- GET  /sim/status
- GET  /sim/report
"""

import os
import sys
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any

from sim.cli import main as sim_main
from sim.scenarios import SCENARIO_CATALOG
from sim.tester import run_simulation
from sim.safety import check_safety, SafetyViolationError

# Global simulation state
CURRENT_SIM_STATE: Dict[str, Any] = {
    "status": "idle",
    "scenario": None,
    "fixture_no": None,
    "current_minute": 0,
    "last_result": None,
    "last_report": None
}
SIM_STOP_REQUESTED = False
SIM_THREAD: Optional[threading.Thread] = None

class SimRequestHandler(BaseHTTPRequestHandler):
    def _check_auth(self) -> bool:
        expected_key = os.environ.get("SIM_KEY", os.environ.get("X_SIM_KEY", "touchline-secret-key"))
        client_key = self.headers.get("X-Sim-Key", "")
        return client_key == expected_key

    def _send_json(self, status_code: int, data: Dict[str, Any]):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Unprotected healthcheck endpoints for Railway
        if path in ("/", "/health"):
            self._send_json(200, {
                "status": "healthy",
                "service": "touchline-sim",
                "sim_status": CURRENT_SIM_STATE["status"],
                "scenarios_available": list(SCENARIO_CATALOG.keys()),
                "endpoints": [
                    "POST /sim/start (Header: X-Sim-Key)",
                    "POST /sim/stop  (Header: X-Sim-Key)",
                    "GET  /sim/status (Header: X-Sim-Key)",
                    "GET  /sim/report (Header: X-Sim-Key)"
                ]
            })
            return

        if path == "/scenarios":
            self._send_json(200, {k: v.description for k, v in SCENARIO_CATALOG.items()})
            return

        # Protected endpoints require X-Sim-Key
        if not self._check_auth():
            self._send_json(401, {"error": "Unauthorized: valid X-Sim-Key header required"})
            return

        if path == "/sim/status":
            self._send_json(200, CURRENT_SIM_STATE)
            return

        if path == "/sim/report":
            if CURRENT_SIM_STATE.get("last_report"):
                self._send_json(200, CURRENT_SIM_STATE["last_report"])
            else:
                self._send_json(404, {"error": "No simulation report available yet."})
            return

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if not self._check_auth():
            self._send_json(401, {"error": "Unauthorized: valid X-Sim-Key header required"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_length > 0:
            try:
                body = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except Exception:
                body = {}

        if path == "/sim/start":
            global SIM_THREAD, SIM_STOP_REQUESTED
            if CURRENT_SIM_STATE["status"] == "running":
                self._send_json(409, {"error": "A simulation is already running", "state": CURRENT_SIM_STATE})
                return

            scenario = body.get("scenario", "var_disallowed")
            fixture_no = int(body.get("fixtureNo", body.get("fixture_no", 1)))
            speed = float(body.get("speed", 0.0))
            seed = int(body.get("seed", 1))
            offline = bool(body.get("offline", not bool(os.environ.get("DATABASE_URL"))))
            write = bool(body.get("write", not offline))

            SIM_STOP_REQUESTED = False
            CURRENT_SIM_STATE.update({
                "status": "running",
                "scenario": scenario,
                "fixture_no": fixture_no,
                "current_minute": 0
            })

            def worker():
                try:
                    res = run_simulation(
                        fixture_no=fixture_no,
                        scenarios=[scenario],
                        speed=speed,
                        seed=seed,
                        offline=offline,
                        write=write
                    )
                    CURRENT_SIM_STATE["status"] = "idle"
                    CURRENT_SIM_STATE["last_result"] = "completed"
                    CURRENT_SIM_STATE["last_report"] = res
                except Exception as e:
                    CURRENT_SIM_STATE["status"] = "error"
                    CURRENT_SIM_STATE["last_result"] = str(e)

            SIM_THREAD = threading.Thread(target=worker, daemon=True)
            SIM_THREAD.start()

            self._send_json(202, {
                "message": "Simulation started",
                "scenario": scenario,
                "fixtureNo": fixture_no,
                "offline": offline
            })
            return

        if path == "/sim/stop":
            SIM_STOP_REQUESTED = True
            CURRENT_SIM_STATE["status"] = "idle"
            CURRENT_SIM_STATE["last_result"] = "stopped by user"
            self._send_json(200, {"message": "Simulation stop requested"})
            return

        self._send_json(404, {"error": "Not Found"})

def run_server(port: int):
    # Safety check on server start
    check_safety()
    server = HTTPServer(("0.0.0.0", port), SimRequestHandler)
    print(f"Touchline Sim server listening on port {port}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(sim_main())

    port_env = os.environ.get("PORT")
    if port_env:
        run_server(int(port_env))
    else:
        print("PORT environment variable not set. Running default offline test scenario...")
        sys.exit(sim_main(["run", "--offline", "--seed", "7", "-s", "var_disallowed"]))
