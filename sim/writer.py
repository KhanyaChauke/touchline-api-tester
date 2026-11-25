"""
Staging DB Writer for touchline-sim.
Writes snapshots to the staging PostgreSQL database conforming to the Touchline sync migrations.
Implements Option A (Sync observation logic with fallback to direct schema-compliant transactions).
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from .constants import *
from .safety import check_safety

try:
    import psycopg
except ImportError:
    psycopg = None

class StagingWriter:
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.environ.get("DATABASE_URL")
        # Enforce safety guard!
        check_safety(db_url=self.db_url)
        if not self.db_url:
            raise ValueError("DATABASE_URL must be provided or set in environment.")
        self.conn = None

    def connect(self):
        if psycopg is None:
            raise RuntimeError("psycopg is not installed. Install requirements with: pip install -r requirements.txt")
        if self.conn is None or self.conn.closed:
            self.conn = psycopg.connect(self.db_url, autocommit=False)
        return self.conn

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()

    def write_snapshot(self, snapshot: Dict[str, Any]) -> int:
        """
        Write a complete snapshot to the staging database.
        Returns the internal football.fixtures.id.
        """
        check_safety(db_url=self.db_url)
        conn = self.connect()

        fix = snapshot["fixture"]
        lineups = snapshot.get("lineups", [])
        events = snapshot.get("events", [])

        sm_fix_id = fix["sportmonksFixtureId"]
        state_id = fix["stateId"]
        home_score = fix["homeScore"] if fix["homeScore"] is not None else 0
        away_score = fix["awayScore"] if fix["awayScore"] is not None else 0
        kickoff = fix["kickoffUtc"]

        with conn.cursor() as cur:
            # 1. Resolve internal competition_id and season_id and team_ids
            # We look up existing records by sportmonks IDs or fall back to defaults
            cur.execute("select id from football.competitions limit 1")
            row = cur.fetchone()
            comp_id = row[0] if row else 1

            cur.execute("select id from football.seasons limit 1")
            row = cur.fetchone()
            season_id = row[0] if row else 1

            cur.execute("select id from football.teams where sportmonks_team_id = %s", (fix["homeTeamSportmonksId"],))
            row = cur.fetchone()
            home_team_id = row[0] if row else 1

            cur.execute("select id from football.teams where sportmonks_team_id = %s", (fix["awayTeamSportmonksId"],))
            row = cur.fetchone()
            away_team_id = row[0] if row else 2

            # 2. Upsert fixture
            cur.execute("""
                insert into football.fixtures (
                    sportmonks_fixture_id, competition_id, season_id, state_id,
                    home_team_id, away_team_id, home_score, away_score,
                    starting_at, length, updated_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 90, now())
                on conflict (sportmonks_fixture_id) do update set
                    state_id = excluded.state_id,
                    home_score = excluded.home_score,
                    away_score = excluded.away_score,
                    updated_at = now()
                returning id
            """, (sm_fix_id, comp_id, season_id, state_id, home_team_id, away_team_id, home_score, away_score, kickoff))
            fixture_id = cur.fetchone()[0]

            # 3. Upsert Lineups (if provided)
            if lineups:
                for l in lineups:
                    team_id = home_team_id if l["teamSportmonksId"] == fix["homeTeamSportmonksId"] else away_team_id
                    # Lookup player internal id if exists
                    cur.execute("select id, common_name from football.players where sportmonks_player_id = %s", (l["sportmonksPlayerId"],))
                    prow = cur.fetchone()
                    player_id = prow[0] if prow else None
                    player_name = prow[1] if prow else f"Player {l['sportmonksPlayerId']}"

                    cur.execute("""
                        insert into football.player_lineups (
                            sportmonks_lineup_id, fixture_id, team_id,
                            sportmonks_player_id, player_id, player_name,
                            position_id, type_id, updated_at
                        ) values (%s, %s, %s, %s, %s, %s, %s, %s, now())
                        on conflict (sportmonks_lineup_id) do update set
                            team_id = excluded.team_id,
                            position_id = excluded.position_id,
                            type_id = excluded.type_id,
                            updated_at = now()
                    """, (
                        l["lineupId"], fixture_id, team_id,
                        l["sportmonksPlayerId"], player_id, player_name,
                        l["positionId"], l["typeId"]
                    ))

            # 4. Upsert Events & Handle Withdrawals
            active_event_ids = set()
            for e in events:
                eid = e["eventId"]
                active_event_ids.add(eid)
                team_id = home_team_id if e["teamSportmonksId"] == fix["homeTeamSportmonksId"] else away_team_id

                cur.execute("""
                    insert into football.match_events (
                        sportmonks_event_id, fixture_id, team_id,
                        sportmonks_player_id, sportmonks_related_player_id,
                        type_id, minute, extra_minute, sort_order, rescinded, updated_at
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, false, now())
                    on conflict (sportmonks_event_id) do update set
                        sportmonks_player_id = excluded.sportmonks_player_id,
                        sportmonks_related_player_id = excluded.sportmonks_related_player_id,
                        type_id = excluded.type_id,
                        minute = excluded.minute,
                        extra_minute = excluded.extra_minute,
                        sort_order = excluded.sort_order,
                        rescinded = false,
                        updated_at = now()
                """, (
                    eid, fixture_id, team_id,
                    e["sportmonksPlayerId"], e.get("relatedSportmonksPlayerId"),
                    e["typeId"], e["minute"], e.get("extraMinute"), e["sortOrder"]
                ))

            # Withdrawal Rule: If an event previously recorded for this fixture is missing in the new snapshot,
            # that counts ONLY IF the snapshot still has other events. An empty events list must never withdraw anything!
            if events:
                cur.execute("""
                    select sportmonks_event_id from football.match_events
                    where fixture_id = %s and rescinded = false
                """, (fixture_id,))
                existing_eids = [row[0] for row in cur.fetchall()]
                for ex_id in existing_eids:
                    if ex_id not in active_event_ids:
                        cur.execute("""
                            update football.match_events
                            set rescinded = true, updated_at = now()
                            where sportmonks_event_id = %s
                        """, (ex_id,))

        conn.commit()
        return fixture_id
