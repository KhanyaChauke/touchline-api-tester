-- Run after a simulation: what did the data layer receive?
select f.id, f.sportmonks_fixture_id, f.state_id, f.home_score, f.away_score
from football.fixtures f where f.sportmonks_fixture_id >= 9000000000;

select e.type_id, count(*) n, count(*) filter (where e.rescinded) rescinded
from football.match_events e where e.sportmonks_event_id >= 9000000000 group by 1 order by 2 desc;

-- Fixture score must equal non-rescinded goals; own-goal rows carry the beneficiary team_id (verified).
select f.id, f.home_score, f.away_score,
  count(*) filter (where e.type_id in (14,15,16) and e.team_id = f.home_team_id) as home_from_events,
  count(*) filter (where e.type_id in (14,15,16) and e.team_id = f.away_team_id) as away_from_events
from football.fixtures f join football.match_events e on e.fixture_id = f.id and not coalesce(e.rescinded,false)
where f.sportmonks_fixture_id >= 9000000000 group by f.id;
