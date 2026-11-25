"""Plays a generated Match into a sink (printer or Postgres), tick by tick, like the sync would."""
import time
from .constants import *
from .engine import Match, credited_side

def play(match: Match, sink, speed: float = 0.0, sleep=time.sleep):
    sink.create_fixture(match)
    flags = {}  # seq -> currently rescinded?
    pending = list(match.events)
    last = max(match.last_minute, 1) if match.events else 0
    for tick in range(1, last + 1):
        state = FIRST_HALF if tick <= 45 else SECOND_HALF
        for e in [e for e in pending if e.deliver == tick]:
            flags[e.seq] = e.rescinded and e.rescind_at is None
            sink.insert_event(e, rescinded=flags[e.seq]); pending.remove(e)
        for e in match.events:
            if e.duplicate_at == tick and e.seq in flags:
                sink.insert_event(e, rescinded=flags[e.seq], duplicate=True)
            if e.rescind_at is not None and e.seq in flags and not flags[e.seq]:
                if tick >= max(e.rescind_at, e.deliver + 1) or tick == last:
                    flags[e.seq] = True; sink.rescind(e)
        h = sum(1 for e in match.events if e.seq in flags and not flags[e.seq] and credited_side(e) == "home")
        a = sum(1 for e in match.events if e.seq in flags and not flags[e.seq] and credited_side(e) == "away")
        sink.update_fixture(HALF_TIME if tick == 45 else state, h, a, tick)
        if speed: sleep(speed)
    sink.update_fixture(match.state, match.home, match.away, last)
