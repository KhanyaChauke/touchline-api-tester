-- Read-only. Confirms the two event-shape assumptions the simulator makes.
-- 1) Own goals: team_id differs from the scoring player's own team (it is the beneficiary). Expect all rows to differ.
select e.id, e.fixture_id, e.team_id, e.player_name, l.team_id as player_lineup_team, f.home_team_id, f.away_team_id, e.result
from football.match_events e join football.fixtures f on f.id = e.fixture_id
left join football.player_lineups l on l.fixture_id = e.fixture_id and l.sportmonks_player_id = e.sportmonks_player_id
where e.type_id = 15 limit 10;
-- 2) Substitutions: player = coming ON (lineup type 12), related = going OFF (type 11).
select e.player_name as player, e.related_player_name as related, l1.type_id as player_lineup_type, l2.type_id as related_lineup_type
from football.match_events e
left join football.player_lineups l1 on l1.fixture_id = e.fixture_id and l1.sportmonks_player_id = e.sportmonks_player_id
left join football.player_lineups l2 on l2.fixture_id = e.fixture_id and l2.sportmonks_player_id = e.sportmonks_related_player_id
where e.type_id = 18 limit 10;
