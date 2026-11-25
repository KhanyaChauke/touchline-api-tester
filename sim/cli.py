"""
Command-line interface for touchline-sim.
"""

import argparse
import os
import sys
from .constants import *
from .safety import check_safety
from .scenarios import SCENARIO_CATALOG
from .tester import run_simulation
from .db import connect, cleanup
from .engine import fake_squad

def main(argv=None):
    ap = argparse.ArgumentParser(prog="touchline-sim", description="Touchline match simulator and API tester")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # scenarios command
    sub.add_parser("scenarios", help="list all 18 test scenarios and expected points")

    # run command
    r = sub.add_parser("run", help="simulate fixture(s) and test Touchline API")
    r.add_argument("--scenario", "-s", action="append", default=[], help="repeatable or comma-separated scenario names")
    r.add_argument("--fixture-no", type=int, default=1, help="1-999; distinct numbers make distinct simulated fixtures")
    r.add_argument("--speed", type=float, default=0.0, help="seconds per match minute (0 = instant)")
    r.add_argument("--seed", type=int, default=1, help="deterministic random seed")
    r.add_argument("--offline", action="store_true", help="run offline with synthetic squads without database or API")
    r.add_argument("--write", action="store_true", help="actually write snapshots to staging database")
    r.add_argument("--api-url", type=str, default=None, help="staging Touchline API base URL (overrides TOUCHLINE_API_BASE_URL)")
    r.add_argument("--admin-token", type=str, default=None, help="Touchline admin JWT token (overrides TOUCHLINE_ADMIN_TOKEN)")

    # cleanup command
    c = sub.add_parser("cleanup", help="safely delete simulated rows (IDs >= %d)" % FIXTURE_BASE)
    c.add_argument("--write", action="store_true", help="actually perform the deletion")

    args = ap.parse_args(argv)

    # 1. Startup safety guard check
    check_safety(api_base_url=getattr(args, "api_url", None))

    if args.cmd == "scenarios":
        print("\n" + "=" * 80)
        print("TOUCHLINE MATCH SIMULATOR — 18 SCENARIOS & EXPECTED POINTS")
        print("=" * 80)
        for name, info in SCENARIO_CATALOG.items():
            print(f"{name:<24} | {info.expected_points_summary}")
            print(f"  Description: {info.description}")
            print("-" * 80)
        return 0

    if args.cmd == "cleanup":
        url = os.environ.get("DATABASE_URL")
        if not url:
            sys.exit("Set DATABASE_URL to clean up staging database.")
        check_safety(db_url=url)
        conn = connect(url)
        counts = cleanup(conn, args.write)
        for table, count in counts.items():
            action = "Deleted" if args.write else "Found"
            print(f"[{table}] {action} {count} simulated rows")
        if not args.write:
            print("\nDry run only. Pass --write to execute deletion.")
        return 0

    if args.cmd == "run":
        if not 1 <= args.fixture_no <= 999:
            sys.exit("--fixture-no must be between 1 and 999")

        # Parse scenarios list
        scenario_list = []
        if args.scenario:
            for s in args.scenario:
                for item in s.split(","):
                    item = item.strip()
                    if item == "all":
                        scenario_list.extend(list(SCENARIO_CATALOG.keys()))
                    elif item:
                        scenario_list.append(item)
        else:
            scenario_list = ["var_disallowed"]

        # Run simulation
        result = run_simulation(
            fixture_no=args.fixture_no,
            scenarios=scenario_list,
            speed=args.speed,
            seed=args.seed,
            offline=args.offline,
            write=args.write,
            api_url=args.api_url,
            admin_token=args.admin_token
        )
        return 0 if not result.get("failures") else 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
