"""Ids as stored by Touchline sync (Sports Monks conventions), verified against TouchLineDB."""
SIM_BASE = 9_000_000_000  # every simulated sportmonks_* id is >= this, so cleanup is exact

# match_events.type_id
GOAL, OWN_GOAL, PENALTY, MISSED_PENALTY = 14, 15, 16, 17
SUBSTITUTION, YELLOW, RED, YELLOW_RED, VAR = 18, 19, 20, 21, 10

# fixtures.state_id
NOT_STARTED, FIRST_HALF, HALF_TIME, FULL_TIME = 1, 2, 3, 5
POSTPONED, ABANDONED, SECOND_HALF = 10, 15, 22  # 2/3/22 are standard Sports Monks, not yet seen in your data

# player_lineups.type_id / position_id
STARTER, BENCH = 11, 12
GK, DEF, MID, ATT = 24, 25, 26, 27

GOAL_TYPES = (GOAL, PENALTY)
