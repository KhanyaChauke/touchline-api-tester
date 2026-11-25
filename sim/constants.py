"""Ids and constants as defined by Touchline sync (Sportmonks conventions) and touchline-sim rules."""

# ID Base ranges
FIXTURE_BASE = 9_000_000_000
LINEUP_BASE  = 9_100_000_000
EVENT_BASE   = 9_200_000_000

# Legacy compatibility
SIM_BASE = FIXTURE_BASE

# Fixture States (from touchline-api core states matrix)
NOT_STARTED = 1
FIRST_HALF  = 2
HALF_TIME   = 3
BREAK       = 4
SECOND_HALF = 22
FULL_TIME   = 5
POSTPONED   = 10
ABANDONED   = 15
INTERRUPTED = 18

# Event Types
GOAL            = 14
OWN_GOAL        = 15
PENALTY         = 16
MISSED_PENALTY  = 17
SUBSTITUTION    = 18
YELLOW          = 19
RED             = 20
YELLOW_RED      = 21
VAR             = 10

GOAL_TYPES = (GOAL, PENALTY)

# Lineup Types
STARTER = 11
BENCH   = 12

# Positions
GK  = 24
DEF = 25
MID = 26
ATT = 27
