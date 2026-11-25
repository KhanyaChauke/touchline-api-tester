"""Pure match generator: no database, deterministic for a given seed."""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from .constants import *

SCENARIOS = {
    "postponed": "fixture state 10, no events",
    "abandoned": "match stops at 60', state 15",
    "var_disallowed": "goal delivered, then rescinded 3 minutes later (+ VAR event)",
    "hattrick": "one attacker scores three",
    "clean_sheet_gk_sub": "home keeps a clean sheet but its GK is substituted at 70'",
    "early_red": "home defender sent off at 12'",
    "missing_player": "one goal arrives with no player id (name only)",
    "duplicates": "some events are delivered twice with the same id",
    "late_events": "some events arrive out of order, several minutes late",
    "bench_card": "an unused substitute is booked (on_bench = true)",
    "own_goal": "a defender scores an own goal",
}

@dataclass
class Player:
    pid: int
    name: str
    pos: int
    starter: bool
    side: str  # 'home' | 'away'

@dataclass
class Event:
    seq: int
    side: str                        # team_id side on the row (for own goals: the team that benefits)
    type_id: int
    minute: int
    extra_minute: int | None = None
    player: Player | None = None
    related: Player | None = None
    player_name: str | None = None
    result: str | None = None
    addition: str | None = None
    rescinded: bool = False
    on_bench: bool = False
    deliver: int = 0                 # match minute at which the sync "sees" it
    rescind_at: int | None = None    # minute at which a later update flips rescinded
    duplicate_at: int | None = None  # minute at which the same event is re-delivered

@dataclass
class Match:
    events: list[Event]
    home: int
    away: int
    state: int
    last_minute: int
    squads: dict = field(default_factory=dict)

def ordinal(n): return f"{n}{'th' if 10 <= n % 100 <= 20 else {1:'st',2:'nd',3:'rd'}.get(n % 10,'th')}"
def other(side): return "away" if side == "home" else "home"

def credited_side(e: Event) -> str | None:
    # Verified on TouchLineDB: an own-goal row's team_id is the team that BENEFITS, so every goal type credits e.side.
    return e.side if e.type_id in (*GOAL_TYPES, OWN_GOAL) else None

def live_score(events) -> tuple[int, int]:
    h = a = 0
    for e in events:
        s = credited_side(e)
        if s and not e.rescinded:
            h, a = (h + 1, a) if s == "home" else (h, a + 1)
    return h, a

def generate(home: list[Player], away: list[Player], seed: int = 1, scenarios=frozenset()) -> Match:
    unknown = set(scenarios) - set(SCENARIOS)
    if unknown: raise ValueError(f"unknown scenarios: {sorted(unknown)}")
    rng = random.Random(seed)
    squads = {"home": home, "away": away}
    if "postponed" in scenarios: return Match([], 0, 0, POSTPONED, 0, squads)
    end = 60 if "abandoned" in scenarios else 90
    on = {s: [p for p in squads[s] if p.starter] for s in squads}
    bench = {s: [p for p in squads[s] if not p.starter] for s in squads}
    booked, gone, subbed_off = set(), set(), set()
    events: list[Event] = []

    def add(side, type_id, minute, extra=None, **kw):
        e = Event(len(events) + 1, side, type_id, minute, extra, deliver=minute, **kw)
        events.append(e); return e

    def outfield(side): return [p for p in on[side] if p.pos != GK and p.pid not in gone]
    def pick(ps, w=None): return rng.choices(ps, weights=[w.get(p.pos, 1) for p in ps] if w else None)[0]

    def goal(side, minute, extra, kind=None, scorer=None):
        """Records a goal credited to `side`. Result/addition are recomputed after sorting."""
        kind = kind or (PENALTY if rng.random() < 0.08 else GOAL)
        if kind == OWN_GOAL:
            pool = [x for x in on[other(side)] if x.pos in (DEF, GK) and x.pid not in gone] or on[other(side)]
            p = pick(pool)
            return add(side, OWN_GOAL, minute, extra, player=p, player_name=p.name)  # row team = beneficiary, player = opponent
        p = scorer or pick(outfield(side), {DEF: 1, MID: 3, ATT: 6})
        a = None
        if kind == GOAL and rng.random() < 0.73:
            a = pick([x for x in outfield(side) if x.pid != p.pid], {DEF: 1, MID: 4, ATT: 3})
        return add(side, kind, minute, extra, player=p, related=a, player_name=p.name)

    subs = {}
    for s in squads:
        for m in sorted(rng.sample(range(46, 82), 3)): subs[(s, m)] = True
    if "clean_sheet_gk_sub" in scenarios: subs[("home", 70)] = "gk"
    clean = "clean_sheet_gk_sub" in scenarios

    timeline = [(m, None) for m in range(1, 46)] + [(45, x) for x in (1, 2)] + \
               [(m, None) for m in range(46, end + 1)] + ([(90, x) for x in (1, 2, 3)] if end == 90 else [])
    for minute, extra in timeline:
        for side in ("home", "away"):
            if rng.random() < 0.016 and not (clean and side == "away"):
                goal(side, minute, extra, kind=OWN_GOAL if rng.random() < 0.03 else None)
            if rng.random() < 0.012 and outfield(side):
                p = pick(outfield(side))
                if p.pid in booked:
                    add(side, YELLOW_RED, minute, extra, player=p, player_name=p.name); gone.add(p.pid)
                else:
                    add(side, YELLOW, minute, extra, player=p, player_name=p.name); booked.add(p.pid)
            if rng.random() < 0.0008 and len(outfield(side)) > 8:
                p = pick(outfield(side)); add(side, RED, minute, extra, player=p, player_name=p.name); gone.add(p.pid)
            if rng.random() < 0.002 and outfield(side):
                p = pick(outfield(side), {MID: 2, ATT: 3, DEF: 1})
                add(side, MISSED_PENALTY, minute, extra, player=p, player_name=p.name)
            sub = subs.get((side, minute)) if extra is None else None
            if sub:
                off = next((p for p in on[side] if p.pos == GK), None) if sub == "gk" else \
                      (pick(outfield(side)) if outfield(side) else None)
                cands = [b for b in bench[side] if sub != "gk" or b.pos == GK] or bench[side]
                if off and cands:
                    inn = next((b for b in cands if b.pos == off.pos), cands[0])
                    bench[side].remove(inn); on[side].remove(off); on[side].append(inn); subbed_off.add(off.pid)
                    n = sum(1 for e in events if e.type_id == SUBSTITUTION and e.side == side) + 1
                    add(side, SUBSTITUTION, minute, extra, player=inn, related=off, player_name=inn.name,
                        addition=f"{ordinal(n)} Substitution")

    # ---- scripted scenarios ---------------------------------------------------------------
    # scripted events happen at fixed minutes, so only use starters who were never substituted off
    for s_ in squads: on[s_] = [p for p in squads[s_] if p.starter and p.pid not in subbed_off and p.pid not in gone]
    if "hattrick" in scenarios:
        s = rng.choice(["home", "away"])
        st = pick([p for p in squads[s] if p.pos == ATT and p.starter] or on[s])
        for m in (21, 52, 78): goal(s, m, None, kind=GOAL, scorer=st)
    if "own_goal" in scenarios: goal(rng.choice(["home", "away"]), 33, None, kind=OWN_GOAL)
    if "early_red" in scenarios:
        d = next(p for p in squads["home"] if p.pos == DEF and p.starter)
        add("home", RED, 12, None, player=d, player_name=d.name)
    if "bench_card" in scenarios and bench["home"]:
        b = bench["home"][-1]; add("home", YELLOW, min(88, end), None, player=b, player_name=b.name, on_bench=True)
    if "missing_player" in scenarios:
        g = next((e for e in events if e.type_id in GOAL_TYPES), None) or goal("home", 40, None, kind=GOAL)
        g.player = None; g.related = None
    if "var_disallowed" in scenarios:
        g = goal(rng.choice(["home", "away"]), 64, None, kind=GOAL)
        g.rescind_at = 67; g.rescinded = True
        add(g.side, VAR, 65, None, addition="1st Var")

    # ---- order, then recompute running score / goal counter ------------------------------
    events.sort(key=lambda e: (e.minute, e.extra_minute or 0, e.seq))
    h = a = n = 0
    for i, e in enumerate(events, 1):
        e.seq = i
        s = credited_side(e)
        if s:
            n += 1
            if not e.rescinded: h, a = (h + 1, a) if s == "home" else (h, a + 1)
            e.result = f"{h}-{a}"; e.addition = f"{ordinal(n)} Goal"

    # ---- delivery quirks -----------------------------------------------------------------
    if "late_events" in scenarios:
        for e in rng.sample(events, max(1, len(events) // 6)): e.deliver = min(end, e.minute + rng.randint(4, 15))
    if "duplicates" in scenarios:
        for e in rng.sample(events, max(1, len(events) // 8)): e.duplicate_at = min(end, e.deliver + 1)
    h, a = live_score(events)
    return Match(events, h, a, ABANDONED if "abandoned" in scenarios else FULL_TIME, end, squads)
