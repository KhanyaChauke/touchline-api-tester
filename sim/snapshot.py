"""
Snapshot generation for match simulator.
Produces full, immutable-at-tick JSON snapshots per fixture following the exact Sportmonks v3 / Touchline sync schema.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from .constants import *

@dataclass
class SnapshotPlayer:
    sportmonks_player_id: int
    name: str
    team_sportmonks_id: int
    position_id: int
    is_starter: bool
    side: str  # "home" or "away"

@dataclass
class SnapshotEvent:
    event_id: int
    type_id: int
    team_sportmonks_id: int
    sportmonks_player_id: Optional[int]
    related_sportmonks_player_id: Optional[int]
    minute: int
    extra_minute: Optional[int]
    sort_order: int
    rescinded: bool = False
    result: Optional[str] = None
    on_bench: bool = False

@dataclass
class MatchState:
    fixture_id: int
    season_id: int
    league_id: int
    home_team_id: int
    away_team_id: int
    kickoff_utc: str
    state_id: int
    home_score: Optional[int]
    away_score: Optional[int]
    observed_at_utc: str
    lineups: List[SnapshotPlayer] = field(default_factory=list)
    events: List[SnapshotEvent] = field(default_factory=list)

def build_snapshot_json(
    fixture_no: int,
    season_id: int,
    league_id: int,
    home_team_id: int,
    away_team_id: int,
    kickoff_utc: str,
    state_id: int,
    home_score: Optional[int],
    away_score: Optional[int],
    lineups: List[SnapshotPlayer],
    events: List[SnapshotEvent],
    observed_at_utc: Optional[str] = None,
    include_lineups: bool = True
) -> Dict[str, Any]:
    """
    Build a full JSON snapshot conforming to Touchline sync requirements.
    Scores must be null before kickoff (state_id == NOT_STARTED).
    """
    sportmonks_fixture_id = FIXTURE_BASE + fixture_no
    
    # Null scores before kickoff
    if state_id == NOT_STARTED:
        h_score = None
        a_score = None
    else:
        h_score = home_score if home_score is not None else 0
        a_score = away_score if away_score is not None else 0

    obs_time = observed_at_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lineups_data = []
    if include_lineups:
        for idx, p in enumerate(lineups, 1):
            lineup_id = LINEUP_BASE + fixture_no * 1000 + idx
            lineups_data.append({
                "lineupId": lineup_id,
                "sportmonksPlayerId": p.sportmonks_player_id,
                "teamSportmonksId": p.team_sportmonks_id,
                "typeId": STARTER if p.is_starter else BENCH,
                "positionId": p.position_id
            })

    events_data = []
    for e in events:
        # A withdrawn event left out of the list should not appear here
        if e.rescinded:
            continue
        events_data.append({
            "eventId": e.event_id,
            "typeId": e.type_id,
            "teamSportmonksId": e.team_sportmonks_id,
            "sportmonksPlayerId": e.sportmonks_player_id,
            "relatedSportmonksPlayerId": e.related_sportmonks_player_id,
            "minute": int(e.minute),
            "extraMinute": int(e.extra_minute) if e.extra_minute is not None else None,
            "sortOrder": int(e.sort_order)
        })

    return {
        "fixture": {
            "sportmonksFixtureId": sportmonks_fixture_id,
            "sportmonksSeasonId": season_id,
            "sportmonksLeagueId": league_id,
            "homeTeamSportmonksId": home_team_id,
            "awayTeamSportmonksId": away_team_id,
            "kickoffUtc": kickoff_utc,
            "stateId": state_id,
            "homeScore": h_score,
            "awayScore": a_score,
            "observedAtUtc": obs_time
        },
        "lineups": lineups_data,
        "events": events_data
    }
