import pytest
from sim.snapshot import build_snapshot_json, SnapshotPlayer, SnapshotEvent
from sim.constants import *

def test_snapshot_id_ranges_and_format():
    fixture_no = 5
    players = [
        SnapshotPlayer(
            sportmonks_player_id=12345,
            name="Test Scorer",
            team_sportmonks_id=9960,
            position_id=ATT,
            is_starter=True,
            side="home"
        )
    ]
    events = [
        SnapshotEvent(
            event_id=EVENT_BASE + 5001,
            type_id=GOAL,
            team_sportmonks_id=9960,
            sportmonks_player_id=12345,
            related_sportmonks_player_id=None,
            minute=45,
            extra_minute=2,
            sort_order=1
        )
    ]

    # Pre-kickoff snapshot
    snap_pre = build_snapshot_json(
        fixture_no=fixture_no,
        season_id=28123,
        league_id=806,
        home_team_id=9960,
        away_team_id=2541,
        kickoff_utc="2026-12-01T13:30:00Z",
        state_id=NOT_STARTED,
        home_score=0,
        away_score=0,
        lineups=players,
        events=[]
    )

    # Fixture ID must be 9000000000 + fixture_no
    assert snap_pre["fixture"]["sportmonksFixtureId"] == 9_000_000_005
    # Scores must be null before kickoff
    assert snap_pre["fixture"]["homeScore"] is None
    assert snap_pre["fixture"]["awayScore"] is None
    # Lineup ID must start with 9100000000
    assert snap_pre["lineups"][0]["lineupId"] >= 9_100_000_000

    # In-play snapshot
    snap_play = build_snapshot_json(
        fixture_no=fixture_no,
        season_id=28123,
        league_id=806,
        home_team_id=9960,
        away_team_id=2541,
        kickoff_utc="2026-12-01T13:30:00Z",
        state_id=FIRST_HALF,
        home_score=1,
        away_score=0,
        lineups=players,
        events=events
    )

    assert snap_play["fixture"]["homeScore"] == 1
    assert snap_play["fixture"]["awayScore"] == 0
    # Stoppage time must be numeric, not a string
    ev = snap_play["events"][0]
    assert ev["minute"] == 45
    assert ev["extraMinute"] == 2
    assert ev["eventId"] >= 9_200_000_000
