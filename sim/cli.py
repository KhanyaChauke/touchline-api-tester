import argparse, os, sys
from .constants import *
from .engine import SCENARIOS, Player, generate, credited_side
from .runner import play

LABELS = {GOAL: "goal", PENALTY: "penalty", OWN_GOAL: "own goal", MISSED_PENALTY: "missed pen", SUBSTITUTION: "sub",
          YELLOW: "yellow", RED: "red", YELLOW_RED: "2nd yellow", VAR: "VAR"}

def fake_squad(side):
    pos = [GK] + [DEF] * 4 + [MID] * 4 + [ATT] * 2 + [GK, DEF, DEF, MID, MID, ATT, ATT]
    base = 1000 if side == "home" else 2000
    return [Player(base + i, f"{side.title()} Player {i + 1}", p, i < 11, side) for i, p in enumerate(pos)]

class PrintSink:
    def create_fixture(self, m): print(f"fixture created, state=1, home squad {len(m.squads['home'])}, away squad {len(m.squads['away'])}")
    def insert_event(self, e, rescinded=False, duplicate=False):
        who = e.player_name or "(no player)"; rel = f" <- {e.related.name}" if e.related else ""
        print(f"  {e.minute:>2}'{('+' + str(e.extra_minute)) if e.extra_minute else '':<3}{LABELS[e.type_id]:<11}{e.side:<5}{who}{rel}"
              f"{'  [DUPLICATE]' if duplicate else ''}{'  [rescinded]' if rescinded else ''}  {e.result or ''}")
    def rescind(self, e): print(f"  -- update: event {e.seq} ({e.player_name or 'goal'}) now rescinded")
    def update_fixture(self, state, h, a, minute):
        if state in (HALF_TIME, FULL_TIME, ABANDONED, POSTPONED): print(f"  == state {state} score {h}-{a} (minute {minute})")

def main(argv=None):
    ap = argparse.ArgumentParser(prog="touchline-sim")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scenarios", help="list scenario names")
    r = sub.add_parser("run", help="simulate one fixture")
    r.add_argument("--scenario", "-s", action="append", default=[], help="repeatable; see `scenarios`")
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--fixture-no", type=int, default=1, help="1-999; distinct numbers make distinct simulated fixtures")
    r.add_argument("--replay-fixture", type=int, help="internal fixtures.id whose teams and lineups to use")
    r.add_argument("--offline", action="store_true", help="synthetic squads, no database needed")
    r.add_argument("--speed", type=float, default=0.0, help="seconds per match minute (0 = instant)")
    r.add_argument("--write", action="store_true", help="actually write to the database (default is dry run)")
    c = sub.add_parser("cleanup", help="delete every simulated row (ids >= %d)" % SIM_BASE)
    c.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "scenarios":
        for k, v in SCENARIOS.items(): print(f"{k:<20}{v}")
        return 0

    url = os.environ.get("DATABASE_URL")
    need_db = a.cmd == "cleanup" or (a.cmd == "run" and (a.write or not a.offline))
    if need_db and not url: sys.exit("Set DATABASE_URL (see .env.example)")
    if getattr(a, "write", False):
        from .db import host_of
        if os.environ.get("SIM_ALLOW_WRITE") != "1": sys.exit("Refusing to write: set SIM_ALLOW_WRITE=1")
        print(f"WRITING to {host_of(url)}")

    if a.cmd == "cleanup":
        from .db import connect, cleanup
        counts = cleanup(connect(url), a.write)
        print(("Deleted" if a.write else "Would delete (dry run)"), counts); return 0

    if not 1 <= a.fixture_no <= 999: sys.exit("--fixture-no must be 1-999")
    ctx = None
    if a.offline: home, away = fake_squad("home"), fake_squad("away")
    else:
        from .db import connect, fetch_squads
        conn = connect(url); ctx, home, away = fetch_squads(conn, a.replay_fixture)
        print(f"Using teams/lineups from real fixture id {ctx['replayed']}")
    match = generate(home, away, a.seed, set(a.scenario))
    print(f"Simulating seed={a.seed} scenarios={a.scenario or ['none']}  ->  final {match.home}-{match.away}, state {match.state}")
    if a.write:
        from .db import PgSink
        sink = PgSink(conn, ctx, a.fixture_no)
    else: sink = PrintSink()
    play(match, sink, a.speed)
    if a.write: print(f"Done. sportmonks_fixture_id = {SIM_BASE + a.fixture_no}")
    return 0

if __name__ == "__main__": sys.exit(main())
