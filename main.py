import os
import sys
import json
import io
import contextlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from sim.cli import main as sim_main
from sim.engine import SCENARIOS

class SimHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "status": "healthy",
                "service": "touchline-sim",
                "scenarios": list(SCENARIOS.keys()),
                "usage": "GET /run?scenario=var_disallowed&offline=true"
            }
            self.wfile.write(json.dumps(resp, indent=2).encode("utf-8"))
            return

        if path == "/scenarios":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(SCENARIOS, indent=2).encode("utf-8"))
            return

        if path == "/run":
            scenario = params.get("scenario", [os.environ.get("SIM_SCENARIO", "var_disallowed")])[0]
            is_offline = "offline" in params or not os.environ.get("DATABASE_URL")
            speed = params.get("speed", ["0"])[0]
            seed = params.get("seed", ["7"])[0]

            args = ["run", "--seed", seed, "--speed", speed, "-s", scenario]
            if is_offline:
                args.append("--offline")
            else:
                args.append("--write")

            out = io.StringIO()
            err = io.StringIO()
            try:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    sim_main(args)
                status_code = 200
                result = {"status": "success", "output": out.getvalue()}
            except SystemExit as se:
                status_code = 500 if se.code != 0 else 200
                result = {
                    "status": "exit" if se.code == 0 else "error",
                    "code": str(se.code),
                    "output": out.getvalue(),
                    "error": err.getvalue()
                }
            except Exception as e:
                status_code = 500
                result = {"status": "exception", "error": str(e), "output": out.getvalue()}

            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode("utf-8"))
            return

        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "not found"}).encode("utf-8"))

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]} {args[1]} {args[2]}")

def run_server(port):
    server = HTTPServer(("0.0.0.0", port), SimHandler)
    print(f"Server listening on http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    # If explicit CLI arguments were passed (e.g., python main.py run ...), run CLI directly
    if len(sys.argv) > 1:
        sys.exit(sim_main())

    # Railway / cloud environments always inject the PORT variable
    port_env = os.environ.get("PORT")
    if port_env:
        run_server(int(port_env))
    else:
        # Local fallback: run the offline test simulation
        print("PORT environment variable not set. Running offline simulation dry run...")
        sys.exit(sim_main(["run", "--offline", "--seed", "7", "-s", "var_disallowed"]))
