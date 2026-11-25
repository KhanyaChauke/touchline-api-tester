# touchline-sim

Edge-case match simulator and API verification suite for **Touchline**, the South African PSL fantasy football platform.

`touchline-sim` writes realistic match data (full snapshots) into a **staging** Supabase Postgres database, verifies that the downstream **Touchline API (C#, ASP.NET)** serves the correct football states and event timelines, verifies fantasy points calculations against the official **Touchline 2026/27 Fantasy Rulebook v1**, and generates structured PASS/FAIL audit reports.

---

## Architecture & Flow

```
                  ┌────────────────┐
                  │ touchline-sim  │ (this tester)
                  └───────┬────────┘
             writes       │        calls & checks
          snapshots       ▼             ▼
       ┌────────────────────────┐   ┌────────────────────────┐
       │ Staging DB (Supabase)  │◀──│  Staging Touchline API │
       │   football.* & sync.*  │   │      (ASP.NET Core)    │
       └────────────────────────┘   └────────────────────────┘
```

1. **The API never receives direct football ingest calls:** It reads match data from the `football` schema in PostgreSQL.
2. **The sim acts as the Sportmonks sync worker:** It ingests minute-by-minute match data directly into the staging database.
3. **The sim tests the API downstream:** It polls API endpoints (`/api/v1/fixtures/{id}`, `/api/v1/admin/...`, `/api/v1/fantasy/...`) to verify live updates and final points calculations.

---

## Safety Rules & Production Guard

The simulator features an automated hard startup guard (`sim/safety.py`). It immediately halts execution with `SafetyViolationError` if:
1. `DATABASE_URL` contains the production project ref `exyzbdbitrsidompguda`.
2. `TOUCHLINE_API_BASE_URL` contains the production host `touchline-api-production-ed283561.up.railway.app`.
3. A real Sportmonks API key (`SPORTMONKS_API_KEY`, `SPORTMONKS_TOKEN`, or `SPORTMONKS_KEY`) is detected.

All test data uses reserved ID ranges to prevent colliding with real data:
- **Fixtures:** `9,000,000,000 + fixture_no`
- **Lineups:** starting from `9,100,000,000`
- **Events:** starting from `9,200,000,000`

---

## Write Option Chosen & Rationale

**Chosen: Option A (Direct Schema-Compliant Staging Writes)**

**Why:**
- **Zero extra worker dependency:** Option B requires hosting and orchestrating a separate Python sync worker container with custom URL overrides. Option A connects directly to the staging Supabase pooler via `psycopg`.
- **Full fidelity with Flyway migrations:** Writes match the exact column structures established in Flyway migrations `V007`, `V013`, `V021`, `V030`, `V040`, and `V041`.
- **Accurate revision & withdrawal semantics:** Snapshot withdrawals (`withdrawn_at`, `rescinded`) and idempotency are enforced on every tick. An empty events list never withdraws anything; withdrawals occur only if a non-empty snapshot omits a previously recorded event.

---

## Staging Setup on Railway

### 1. Environment Variables
Configure the following under **Variables** in your Railway service (variable names only):

| Variable | Description |
|---|---|
| `DATABASE_URL` | Staging Supabase connection pooler string (port 6543, user `app_api_user.<staging-ref>`) |
| `SIM_ALLOW_WRITE` | Set to `1` to enable database writes |
| `TOUCHLINE_API_BASE_URL` | Staging API URL (e.g. `https://touchline-api-staging.up.railway.app`) |
| `TOUCHLINE_ADMIN_TOKEN` | Staging Admin JWT token (for gameweek management & fixture resolution) |
| `SIM_KEY` | Secret token required in `X-Sim-Key` header for HTTP control |
| `PORT` | Injected automatically by Railway (defaults to `8080`) |

---

## How to Run

### Mode 1: CLI Execution

```bash
# 1. List all 18 test scenarios and expected points
python -m sim.cli scenarios

# 2. Run an offline dry run (synthetic squads, no DB or network needed)
python -m sim.cli run --offline --seed 7 -s hattrick

# 3. Run against the Staging Database (instant simulation)
python -m sim.cli run --write --seed 7 -s var_disallowed

# 4. Run real-time paced simulation (e.g., 1 second per match minute)
python -m sim.cli run --write --speed 1 --seed 7 -s second_yellow

# 5. Clean up simulated rows (IDs >= 9,000,000,000)
python -m sim.cli cleanup --write
```

### Mode 2: Always-On HTTP Service (Railway)

When deployed on Railway, the service listens on `$PORT` and exposes endpoints protected by the `X-Sim-Key` header:

* `GET /health` / `GET /` — Public health check (returns status 200 for Railway).
* `GET /scenarios` — Public scenario catalog and descriptions.
* `POST /sim/start` (Header: `X-Sim-Key: <SIM_KEY>`) — Trigger a test run:
  ```json
  {
    "scenario": "hattrick",
    "fixtureNo": 1,
    "speed": 0,
    "seed": 7,
    "offline": false,
    "write": true
  }
  ```
* `POST /sim/stop` (Header: `X-Sim-Key: <SIM_KEY>`) — Stop active simulation.
* `GET /sim/status` (Header: `X-Sim-Key: <SIM_KEY>`) — View running state and minute progress.
* `GET /sim/report` (Header: `X-Sim-Key: <SIM_KEY>`) — Fetch the latest simulation audit report.

---

## All 18 Test Scenarios & Expected Points

| # | Scenario | Expected Points per Rulebook 2026/27 v1 |
|---|---|---|
| 1 | `hattrick` | 2 (full match) + 9 (3x goal) = **11 pts** (no hat-trick bonus) |
| 2 | `var_disallowed` | That goal = **0 pts** (event withdrawn via VAR) |
| 3 | `duplicates` | Same event delivered twice = **counted once** |
| 4 | `penalty_goal` | 2 (full match) + 3 (penalty goal) = **5 pts** |
| 5 | `own_goal` | 2 (full match) − 2 (own goal) = **0 pts** |
| 6 | `early_red` | Straight red at 30': 0 (<45m) − 2 = **−2 pts** |
| 7 | `second_yellow` | 2nd yellow at 70': 1 (>=45m) − 2 = **−1 pt** |
| 8 | `clean_sheet_gk_sub_60` | GK subbed off at 60': 1 (>=45m) + 2 (CS >=60m) = **3 pts** |
| 9 | `clean_sheet_gk_sub_59` | GK subbed off at 59': 1 (>=45m) + 0 (no CS <60m) = **1 pt** |
| 10 | `sub_on_46` | Subbed on at 46' (plays 45m): **1 pt** |
| 11 | `sub_off_45_plus_3` | Subbed off at 45+3' (counts as 45m): **1 pt** |
| 12 | `scorer_corrected` | Same event ID, updated player: points move cleanly once |
| 13 | `reissued_goal` | Old event dropped, new event added: 3 goals total, no double counting |
| 14 | `missing_player` | Goal with `sportmonksPlayerId = null`: counts for score, 0 goal points |
| 15 | `abandoned` | Match stops at 60' (state 15): stays under review, not auto-settled |
| 16 | `captain_inactive` | Captain plays 0 min in both fixtures: vice gets **×3** multiplier |
| 17 | `late_lineup` | Lineup delayed past kickoff: detail opens with lineups pending |
| 18 | `stale_feed` | No feed updates for 5+ min during play: API sets `stale: true` |

---

## Test Reports

Every run outputs a report to `reports/<timestamp>-fixture-<n>.json`:
```json
{
  "fixtureNo": 1,
  "scenario": "hattrick",
  "timestamp": "2026-11-25T20:40:53Z",
  "summary": {
    "total": 5,
    "passed": 5,
    "failed": 0,
    "successRate": "100.0%"
  },
  "checks": [
    {
      "scenario": "hattrick",
      "minute": 90,
      "endpoint": "/api/v1/fixtures/9000000001",
      "expected": "State=5, Score=3-1",
      "actual": "Score=3-1",
      "status": "PASS",
      "trace_id": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    }
  ]
}
```

---

## Notes for Leruo (API Review & Observations)

1. **Fixture Resolution Endpoint:** The staging environment lacks automatic completeness data from Sportmonks. Calling `POST /api/v1/admin/fixtures/{id}/resolution` with `{ "outcome": "final", "reason": "Simulated match completed" }` before gameweek settlement works as specified in OpenAPI v1.
2. **Stoppage Time Format:** The Touchline API expects stoppage time represented with numeric minute and extraMinute fields (`"minute": 45, "extraMinute": 2`), never formatted strings (`"45+2"`), and parses them correctly.
3. **Fixture-Gameweek Assignment:** Route `PUT /api/v1/admin/fixtures/{id}/gameweek` exists and accepts `{ "gameweekId": ..., "reason": ..., "confirmLockedChange": true }`.
