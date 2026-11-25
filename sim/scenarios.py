"""
Definitions and expectations for all 18 test scenarios in touchline-sim.
Adheres to Touchline 2026/27 Fantasy Rulebook v1.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .constants import *

@dataclass
class ScenarioInfo:
    name: str
    description: str
    expected_points_summary: str
    key_player_role: str
    expected_points: int
    rule_breakdown: str

SCENARIO_CATALOG: Dict[str, ScenarioInfo] = {
    "hattrick": ScenarioInfo(
        name="hattrick",
        description="One player scores 3 goals in a full match (no hat-trick bonus)",
        expected_points_summary="Scorer: 2 (full match) + 9 (3x goal) = 11 pts",
        key_player_role="Scorer",
        expected_points=11,
        rule_breakdown="2 appearance (90m) + 3*3 goal = 11"
    ),
    "var_disallowed": ScenarioInfo(
        name="var_disallowed",
        description="Goal scored then disallowed by VAR 3 minutes later (event withdrawn)",
        expected_points_summary="Scorer: 2 (full match) + 0 (withdrawn goal) = 2 pts",
        key_player_role="Scorer",
        expected_points=2,
        rule_breakdown="2 appearance (90m) + 0 goal = 2"
    ),
    "duplicates": ScenarioInfo(
        name="duplicates",
        description="Same event ID delivered twice in snapshot; must be idempotent",
        expected_points_summary="Scorer: 2 (full match) + 3 (single goal counted once) = 5 pts",
        key_player_role="Scorer",
        expected_points=5,
        rule_breakdown="2 appearance (90m) + 3 (single goal) = 5"
    ),
    "penalty_goal": ScenarioInfo(
        name="penalty_goal",
        description="Penalty goal (type 16), full match",
        expected_points_summary="Taker: 2 (full match) + 3 (penalty goal) = 5 pts",
        key_player_role="Penalty Taker",
        expected_points=5,
        rule_breakdown="2 appearance (90m) + 3 goal = 5"
    ),
    "own_goal": ScenarioInfo(
        name="own_goal",
        description="Own goal (type 15) scored by defender, full match",
        expected_points_summary="Defender: 2 (full match) - 2 (own goal) = 0 pts",
        key_player_role="Defender",
        expected_points=0,
        rule_breakdown="2 appearance (90m) - 2 own goal = 0"
    ),
    "early_red": ScenarioInfo(
        name="early_red",
        description="Starter sent off at 30' (straight red)",
        expected_points_summary="Carded Player: 0 (played 30m < 45m) - 2 (red card) = -2 pts",
        key_player_role="Carded Player",
        expected_points=-2,
        rule_breakdown="0 appearance (under 45m) - 2 red card = -2"
    ),
    "second_yellow": ScenarioInfo(
        name="second_yellow",
        description="Second yellow card (type 21) at 70'",
        expected_points_summary="Carded Player: 1 (played 70m >= 45m) - 2 (second yellow net) = -1 pt",
        key_player_role="Carded Player",
        expected_points=-1,
        rule_breakdown="1 appearance (70m >= 45m) - 2 second yellow total = -1"
    ),
    "clean_sheet_gk_sub_60": ScenarioInfo(
        name="clean_sheet_gk_sub_60",
        description="GK subbed off at 60' and team concedes 0 goals throughout",
        expected_points_summary="Starting GK: 1 (appearance >= 45m) + 2 (clean sheet >= 60m) = 3 pts",
        key_player_role="Starting GK",
        expected_points=3,
        rule_breakdown="1 appearance (60m) + 2 clean sheet (>=60m) = 3"
    ),
    "clean_sheet_gk_sub_59": ScenarioInfo(
        name="clean_sheet_gk_sub_59",
        description="GK subbed off at 59' and team concedes 0 goals throughout",
        expected_points_summary="Starting GK: 1 (appearance >= 45m) + 0 (no clean sheet, played 59m < 60m) = 1 pt",
        key_player_role="Starting GK",
        expected_points=1,
        rule_breakdown="1 appearance (59m) + 0 clean sheet (<60m) = 1"
    ),
    "sub_on_46": ScenarioInfo(
        name="sub_on_46",
        description="Substitute brought on at 46' (plays 90 - 46 + 1 = 45m)",
        expected_points_summary="Sub Player: 1 (appearance 45m) = 1 pt",
        key_player_role="Substitute",
        expected_points=1,
        rule_breakdown="1 appearance (90 - 46 + 1 = 45m) = 1"
    ),
    "sub_off_45_plus_3": ScenarioInfo(
        name="sub_off_45_plus_3",
        description="Starter subbed off at 45+3' (stoppage time counts as 45m)",
        expected_points_summary="Subbed Player: 1 (appearance exactly 45m) = 1 pt",
        key_player_role="Subbed Starter",
        expected_points=1,
        rule_breakdown="1 appearance (45+3 counts as 45m) = 1"
    ),
    "scorer_corrected": ScenarioInfo(
        name="scorer_corrected",
        description="Event reattributed to a new player under the same eventId",
        expected_points_summary="Old Scorer: 2 pts (appearance only); New Scorer: 5 pts (appearance + goal)",
        key_player_role="New Scorer",
        expected_points=5,
        rule_breakdown="Goal moves cleanly without double-counting"
    ),
    "reissued_goal": ScenarioInfo(
        name="reissued_goal",
        description="Provider reissues goal under new eventId and drops old one",
        expected_points_summary="Match score remains 3 goals; Scorer: 11 pts (no double counting)",
        key_player_role="Scorer",
        expected_points=11,
        rule_breakdown="Old event dropped, new event added; exactly 3 goals scored"
    ),
    "missing_player": ScenarioInfo(
        name="missing_player",
        description="Goal scored with sportmonksPlayerId = null",
        expected_points_summary="Counts on scoreboard and breaks opponent clean sheet; 0 goal points awarded",
        key_player_role="Opponent GK",
        expected_points=2,
        rule_breakdown="Opponent GK gets 2 (full match) and 0 for clean sheet"
    ),
    "abandoned": ScenarioInfo(
        name="abandoned",
        description="Match abandoned at 60' (state 15); remains under review and not scored automatically",
        expected_points_summary="State 15; Gameweek cannot auto-finalise until resolution",
        key_player_role="Match Status",
        expected_points=0,
        rule_breakdown="Under review (state 15)"
    ),
    "captain_inactive": ScenarioInfo(
        name="captain_inactive",
        description="Captain plays 0 minutes across gameweek; Vice gets captain multiplier (x3)",
        expected_points_summary="Vice Captain receives x3 multiplier; Captain receives 0",
        key_player_role="Vice Captain",
        expected_points=15,
        rule_breakdown="Vice: 5 base * 3 = 15 pts"
    ),
    "late_lineup": ScenarioInfo(
        name="late_lineup",
        description="No lineup data available at kickoff; detail opens with lineups: pending",
        expected_points_summary="API returns 200 with lineups pending flag until lineups arrive",
        key_player_role="Lineup Status",
        expected_points=0,
        rule_breakdown="Resilient to missing early lineup"
    ),
    "stale_feed": ScenarioInfo(
        name="stale_feed",
        description="Feed stops updating for 5+ minutes during live play; API sets stale: true",
        expected_points_summary="API reports stale: true while preserving last known score",
        key_player_role="Stale Indicator",
        expected_points=0,
        rule_breakdown="stale == true in API response"
    )
}

def print_expected_points(scenario_name: str) -> None:
    """Print the expected points per player at the start of the scenario run."""
    info = SCENARIO_CATALOG.get(scenario_name)
    if not info:
        print(f"=== Scenario: {scenario_name} ===")
        return

    print("=" * 65)
    print(f"SCENARIO: {info.name.upper()}")
    print(f"Description: {info.description}")
    print(f"Key Player:  {info.key_player_role}")
    print(f"Expected:    {info.expected_points_summary}")
    print(f"Calculation: {info.rule_breakdown}")
    print("=" * 65)
