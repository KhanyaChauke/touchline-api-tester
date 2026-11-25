"""Postgres access. Writes only rows whose sportmonks_* ids are >= SIM_BASE."""
from datetime import datetime, timezone
from urllib.parse import urlparse
from .constants import *
from .engine import Player

def connect(url):
    import psycopg
    return psycopg.connect(url, autocommit=True)

def host_of(url): return urlparse(url).hostname

def fetch_squads(conn, replay_fixture_id=None):
    """Teams, competition, season and lineups of a real fixture. Default: latest finished one with full lineups."""
    with conn.cursor() as c:
        if replay_fixture_id is None:
            c.execute("""select f.id from football.fixtures f where f.state_id = 5 and f.sportmonks_fixture_id < %s
                         and (select count(*) from football.player_lineups l where l.fixture_id = f.id) >= 22
                         order by f.starting_at desc nulls last limit 1""", (SIM_BASE,))
            row = c.fetchone()
            if not row: raise SystemExit("No finished fixture with lineups found; pass --replay-fixture or use --offline")
            replay_fixture_id = row[0]
        c.execute("select competition_id, season_id, home_team_id, away_team_id from football.fixtures where id = %s", (replay_fixture_id,))
        comp, season, home_t, away_t = c.fetchone()
        c.execute("""select l.team_id, l.sportmonks_player_id, coalesce(l.player_name, p.display_name, p.common_name, 'Unknown'),
                            coalesce(l.position_id, p.position_id, 26), l.type_id, l.jersey_number
                     from football.player_lineups l left join football.players p on p.sportmonks_player_id = l.sportmonks_player_id
                     where l.fixture_id = %s and l.sportmonks_player_id is not null order by l.type_id, l.id""", (replay_fixture_id,))
        squads = {"home": [], "away": []}
        for team, pid, name, pos, typ, _ in c.fetchall():
            side = "home" if team == home_t else "away"
            squads[side].append(Player(pid, name, pos if pos in (GK, DEF, MID, ATT) else MID, typ == STARTER, side))
    ctx = dict(competition_id=comp, season_id=season, team_ids={"home": home_t, "away": away_t}, replayed=replay_fixture_id)
    return ctx, squads["home"], squads["away"]

class PgSink:
    def __init__(self, conn, ctx, fixture_no):
        self.c, self.ctx, self.no = conn, ctx, fixture_no
        self.sm_fixture = SIM_BASE + fixture_no
        self.fixture_pk = None

    def create_fixture(self, match):
        with self.c.cursor() as c:
            c.execute("""insert into football.fixtures (sportmonks_fixture_id, competition_id, season_id, state_id, home_team_id,
                           away_team_id, home_score, away_score, starting_at, length)
                         values (%s,%s,%s,%s,%s,%s,0,0,%s,90)
                         on conflict (sportmonks_fixture_id) do update set state_id=excluded.state_id, home_score=0, away_score=0,
                           starting_at=excluded.starting_at, updated_at=now() returning id""",
                      (self.sm_fixture, self.ctx["competition_id"], self.ctx["season_id"], NOT_STARTED,
                       self.ctx["team_ids"]["home"], self.ctx["team_ids"]["away"], datetime.now(timezone.utc)))
            self.fixture_pk = c.fetchone()[0]
            c.execute("delete from football.match_events where fixture_id=%s and sportmonks_event_id >= %s", (self.fixture_pk, SIM_BASE))
            c.execute("delete from football.player_lineups where fixture_id=%s and sportmonks_lineup_id >= %s", (self.fixture_pk, SIM_BASE))
            for side in ("home", "away"):
                for i, p in enumerate(match.squads[side], 1):
                    c.execute("""insert into football.player_lineups (sportmonks_lineup_id, fixture_id, team_id, sportmonks_player_id,
                                   player_name, jersey_number, position_id, type_id) values (%s,%s,%s,%s,%s,%s,%s,%s)""",
                              (SIM_BASE + self.no * 100 + (0 if side == "home" else 50) + i, self.fixture_pk,
                               self.ctx["team_ids"][side], p.pid, p.name, i, p.pos, STARTER if p.starter else BENCH))

    def _eid(self, e): return SIM_BASE + self.no * 1000 + e.seq

    def insert_event(self, e, rescinded=False, duplicate=False):
        with self.c.cursor() as c:
            c.execute("""insert into football.match_events (sportmonks_event_id, fixture_id, team_id, sportmonks_player_id,
                           sportmonks_related_player_id, player_name, related_player_name, type_id, minute, extra_minute,
                           result, addition, sort_order, rescinded, on_bench)
                         values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                         on conflict (sportmonks_event_id) do update set result=excluded.result, rescinded=excluded.rescinded, updated_at=now()""",
                      (self._eid(e), self.fixture_pk, self.ctx["team_ids"][e.side], e.player.pid if e.player else None,
                       e.related.pid if e.related else None, e.player_name, e.related.name if e.related else None,
                       e.type_id, e.minute, e.extra_minute, e.result, e.addition, e.seq, rescinded, e.on_bench))

    def rescind(self, e):
        with self.c.cursor() as c:
            c.execute("update football.match_events set rescinded=true, updated_at=now() where sportmonks_event_id=%s", (self._eid(e),))

    def update_fixture(self, state, h, a, minute):
        with self.c.cursor() as c:
            c.execute("update football.fixtures set state_id=%s, home_score=%s, away_score=%s, updated_at=now() where id=%s",
                      (state, h, a, self.fixture_pk))

def cleanup(conn, write):
    tables = [("football.match_events", "sportmonks_event_id"), ("football.player_lineups", "sportmonks_lineup_id"),
              ("football.player_match_stats", "sportmonks_stat_id"), ("football.fixtures", "sportmonks_fixture_id")]
    out = {}
    with conn.cursor() as c:
        for t, col in tables:
            c.execute(f"select count(*) from {t} where {col} >= %s", (SIM_BASE,)); out[t] = c.fetchone()[0]
            if write: c.execute(f"delete from {t} where {col} >= %s", (SIM_BASE,))
    return out
