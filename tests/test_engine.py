from sim.constants import *
from sim.engine import SCENARIOS, generate, live_score, credited_side
from sim.cli import fake_squad
from sim.runner import play

H, A = fake_squad("home"), fake_squad("away")
gen = lambda seed=1, sc=(): generate(H, A, seed, set(sc))

def test_deterministic():
    a, b = gen(5), gen(5)
    assert [(e.minute, e.type_id, e.player_name) for e in a.events] == [(e.minute, e.type_id, e.player_name) for e in b.events]

def test_score_matches_events_for_every_scenario_and_seed():
    for seed in range(40):
        for sc in [()] + [(s,) for s in SCENARIOS]:
            m = gen(seed, sc)
            assert live_score(m.events) == (m.home, m.away), (seed, sc)

def test_running_result_is_consistent():
    m = gen(3)
    goals = [e for e in m.events if credited_side(e)]
    if goals: assert goals[-1].result == f"{m.home}-{m.away}"

def test_postponed_and_abandoned():
    p = gen(1, ["postponed"]); assert p.state == POSTPONED and not p.events
    a = gen(1, ["abandoned"]); assert a.state == ABANDONED and all(e.minute <= 60 for e in a.events)

def test_var_disallowed_is_rescinded_and_not_counted():
    m = gen(2, ["var_disallowed"])
    g = next(e for e in m.events if e.rescind_at); assert g.rescinded and any(e.type_id == VAR for e in m.events)

def test_hattrick_same_player_three_goals():
    m = gen(4, ["hattrick"])
    from collections import Counter
    assert max(Counter(e.player.pid for e in m.events if e.type_id == GOAL and e.player).values()) >= 3

def test_clean_sheet_with_gk_sub():
    for seed in range(20):
        m = gen(seed, ["clean_sheet_gk_sub"]); assert m.away == 0
        assert any(e.type_id == SUBSTITUTION and e.side == "home" and e.related.pos == GK for e in m.events)

def test_missing_player_and_bench_card():
    m = gen(1, ["missing_player", "bench_card"])
    assert any(e.type_id in GOAL_TYPES and e.player is None for e in m.events) and any(e.on_bench for e in m.events)

def test_late_and_duplicates_flagged():
    m = gen(1, ["late_events", "duplicates"])
    assert any(e.deliver > e.minute for e in m.events) and any(e.duplicate_at for e in m.events)

class Rec:
    def __init__(s): s.ins, s.res, s.fx = [], [], []
    def create_fixture(s, m): pass
    def insert_event(s, e, rescinded=False, duplicate=False): s.ins.append((e.seq, duplicate, rescinded))
    def rescind(s, e): s.res.append(e.seq)
    def update_fixture(s, st, h, a, minute): s.fx.append((st, h, a))

def test_runner_replays_to_final_score_and_handles_quirks():
    for seed in range(15):
        m = gen(seed, ["var_disallowed", "late_events", "duplicates"]); r = Rec()
        play(m, r)
        assert r.fx[-1] == (m.state, m.home, m.away)
        assert {s for s, _, _ in r.ins} == {e.seq for e in m.events}          # everything delivered
        assert len(r.res) == 1                                                  # VAR goal rescinded exactly once
        assert not any(rescinded for s, d, rescinded in r.ins if s in r.res)    # inserted live, rescinded later
