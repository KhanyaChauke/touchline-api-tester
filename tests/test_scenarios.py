import pytest
from sim.scenarios import SCENARIO_CATALOG, print_expected_points
from sim.engine import generate, fake_squad

def test_all_18_scenarios_exist():
    expected_18 = [
        "hattrick",
        "var_disallowed",
        "duplicates",
        "penalty_goal",
        "own_goal",
        "early_red",
        "second_yellow",
        "clean_sheet_gk_sub_60",
        "clean_sheet_gk_sub_59",
        "sub_on_46",
        "sub_off_45_plus_3",
        "scorer_corrected",
        "reissued_goal",
        "missing_player",
        "abandoned",
        "captain_inactive",
        "late_lineup",
        "stale_feed"
    ]
    for s in expected_18:
        assert s in SCENARIO_CATALOG, f"Missing scenario: {s}"
        assert SCENARIO_CATALOG[s].expected_points is not None

def test_scenario_generation():
    home = fake_squad("home")
    away = fake_squad("away")

    for scenario_name in SCENARIO_CATALOG.keys():
        match = generate(home, away, seed=7, scenarios=frozenset([scenario_name]))
        assert match is not None
        assert match.events is not None
        assert match.state is not None
