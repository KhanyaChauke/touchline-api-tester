"""
Report generator for touchline-sim.
Saves JSON reports to reports/<timestamp>-fixture-<n>.json and prints clear summaries.
"""

import os
import json
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

@dataclass
class CheckResult:
    scenario: str
    minute: int
    endpoint: str
    expected: Any
    actual: Any
    status: str  # "PASS" or "FAIL"
    trace_id: Optional[str] = None
    detail: Optional[str] = None

class TestReporter:
    def __init__(self, fixture_no: int, scenario_name: str, reports_dir: str = "reports"):
        self.fixture_no = fixture_no
        self.scenario_name = scenario_name
        self.reports_dir = reports_dir
        self.checks: List[CheckResult] = []
        self.start_time = datetime.now(timezone.utc)

    def record_check(
        self,
        minute: int,
        endpoint: str,
        expected: Any,
        actual: Any,
        passed: bool,
        trace_id: Optional[str] = None,
        detail: Optional[str] = None
    ) -> CheckResult:
        res = CheckResult(
            scenario=self.scenario_name,
            minute=minute,
            endpoint=endpoint,
            expected=expected,
            actual=actual,
            status="PASS" if passed else "FAIL",
            trace_id=trace_id,
            detail=detail
        )
        self.checks.append(res)
        return res

    def save_and_print(self) -> str:
        os.makedirs(self.reports_dir, exist_ok=True)
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}-fixture-{self.fixture_no}.json"
        filepath = os.path.join(self.reports_dir, filename)

        passed_count = sum(1 for c in self.checks if c.status == "PASS")
        failed_count = sum(1 for c in self.checks if c.status == "FAIL")
        total_count = len(self.checks)

        report_data = {
            "fixtureNo": self.fixture_no,
            "scenario": self.scenario_name,
            "timestamp": self.start_time.isoformat(),
            "summary": {
                "total": total_count,
                "passed": passed_count,
                "failed": failed_count,
                "successRate": f"{(passed_count / total_count * 100):.1f}%" if total_count > 0 else "100%"
            },
            "checks": [asdict(c) for c in self.checks]
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        # Print console summary
        print("\n" + "=" * 70)
        print(f"TEST RUN SUMMARY — FIXTURE #{self.fixture_no} ({self.scenario_name})")
        print(f"Report File: {filepath}")
        print(f"Checks: Total={total_count} | Passed={passed_count} | Failed={failed_count}")
        print("-" * 70)

        if failed_count > 0:
            print("FAILURES:")
            for c in self.checks:
                if c.status == "FAIL":
                    trace_str = f" [traceId={c.trace_id}]" if c.trace_id else ""
                    print(f"  [FAIL] Min {c.minute:2d}' {c.endpoint}: Expected={c.expected} | Actual={c.actual}{trace_str}")
                    if c.detail:
                        print(f"         Detail: {c.detail}")
        else:
            print("All checks PASSED successfully.")
        print("=" * 70 + "\n")

        return filepath
