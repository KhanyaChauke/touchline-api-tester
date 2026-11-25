# touchline-sim

Match simulator for **TouchlineZA**. It stands in for *Touchline sync* (FastAPI + Sports Monks): it writes fake
fixtures, lineups and match events straight into the `football` schema, in the same shape the sync produces, so the
**Touchline API (C#, ASP.NET)** and the React front end run for real on top of it. Everything downstream of the
database is the system under test: scoring, clean sheets, captain/bench logic, leaderboards.

```
 touchline-sim  ──writes──▶  football.* (Supabase)  ◀──reads──  Touchline API  ◀──  React front end
 (replaces Sports Monks + sync)
```

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # set DATABASE_URL to a Supabase BRANCH or throwaway project, not production
```

## Use
```bash
python -m sim.cli scenarios                                    # list edge cases
python -m sim.cli run --offline --seed 7 -s var_disallowed     # dry run, no database needed
python -m sim.cli run --seed 7 -s late_events                  # dry run against real teams/lineups (read-only)
export $(cat .env | xargs)
python -m sim.cli run --write --speed 1 --seed 7 -s hattrick   # live: 1 second per match minute
python -m sim.cli cleanup --write                              # remove every simulated row
```
Runs are dry by default. Writing needs both `--write` and `SIM_ALLOW_WRITE=1`, and prints the target host first.
`--replay-fixture <fixtures.id>` picks which real fixture supplies the teams, competition, season and lineups
(default: the latest finished fixture with full lineups). `--fixture-no N` lets you keep several simulated fixtures.

## Safety
Every simulated `sportmonks_*` id is `>= 9,000,000,000`, so `cleanup` removes exactly the simulated rows and
nothing real. Simulated fixtures use real teams, season and competition, so they are visible to the API and front
end like any other fixture. Don't run against production data you can't afford to clutter.

## Scenarios
| name | what it tests |
|---|---|
| `var_disallowed` | goal arrives, then is flipped to `rescinded = true` 3 minutes later; points must be reversed |
| `duplicates` | same `sportmonks_event_id` delivered twice; must not double count |
| `late_events` | events arrive minutes late and out of order |
| `missing_player` | goal with no player id |
| `hattrick` | one player, three goals |
| `own_goal` | own goal, credited to the opponent |
| `early_red` | defender sent off at 12' |
| `bench_card` | unused substitute booked (`on_bench = true`) |
| `clean_sheet_gk_sub` | clean sheet where the goalkeeper is subbed off at 70' |
| `postponed` | fixture state 10, no events |
| `abandoned` | stops at 60', state 15 |

## Data conventions (from TouchLineDB)
Event types 14 goal, 16 penalty, 15 own goal, 17 missed pen, 18 sub, 19 yellow, 20 red, 21 second yellow, 10 VAR.
Assists are the `sportmonks_related_player_id` on the goal row (not separate events). Fixture states 1, 5, 10, 15.
Lineup types 11 starter / 12 bench. Positions 24 GK, 25 DEF, 26 MID, 27 ATT.

## Conventions verified against TouchLineDB
- **Own goals:** the row's `team_id` is the team that *benefits*; the player is from the opposing team (16 of 16 real rows).
- **Substitutions:** `player` = coming on (bench), `related` = going off (starter) (2,336 of ~2,400 rows).

## Still an assumption
**States 2 / 3 / 22** (first half / half time / second half) are standard Sports Monks but don't appear in your data
yet. If the API treats unknown states oddly, that is a finding, not a simulator bug. `sql/check_assumptions.sql`
re-runs the checks above.

## Not simulated yet
`football.player_match_stats` (per-type stat rows, ids like 34, 45, 56...). If the C# fantasy logic reads minutes
played or tackles from stats rather than from events and lineups, add a stats generator. Also untouched:
`sync.gameweek_sync_status` (`events_complete`, `stats_complete`); the fixture's `starting_at` is "now", so it falls
in whichever gameweek date range covers today.

## Tests
`python -m pytest` (or run the functions in `tests/test_engine.py` directly). They cover determinism, score/event
consistency across 40 seeds and every scenario, and replay behaviour (late delivery, duplicates, rescinding).
