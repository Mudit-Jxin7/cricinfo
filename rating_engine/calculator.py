"""Main rating calculator that combines batting, bowling, and fielding ratings.

Weights are determined by the player's role:
- Batter:       80% batting + 5% bowling + 15% fielding
- Bowler:       15% batting + 70% bowling + 15% fielding
- All-rounder:  45% batting + 40% bowling + 15% fielding
- Wicket-keeper: 65% batting + 5% bowling + 30% fielding
"""

from __future__ import annotations

from typing import List

from .batting import calculate_batting_rating
from .bowling import calculate_bowling_rating
from .context import MatchContext, analyze_match_context
from .fielding import calculate_fielding_rating
from .models import (
    BattingEntry,
    BowlingEntry,
    DismissalType,
    FieldingEvent,
    Innings,
    Match,
    PlayerRating,
    PlayerRole,
)

# Role-based weights: (batting_weight, bowling_weight, fielding_weight)
ROLE_WEIGHTS = {
    PlayerRole.BATTER: (0.80, 0.05, 0.15),
    PlayerRole.BOWLER: (0.05, 0.80, 0.15),
    PlayerRole.BATTING_ALL_ROUNDER: (0.55, 0.30, 0.15),
    PlayerRole.BOWLING_ALL_ROUNDER: (0.30, 0.55, 0.15),
    PlayerRole.WICKET_KEEPER: (0.75, 0.00, 0.25),
}


def calculate_match_ratings(match: Match) -> dict:
    """Calculate ratings for all players in a match.

    Returns:
        {
            "team1": {"name": str, "players": [PlayerRating, ...]},
            "team2": {"name": str, "players": [PlayerRating, ...]},
        }
    """
    ctx = analyze_match_context(match)

    fi = match.first_innings
    si = match.second_innings

    team1_won = match.winner == fi.team_name
    team2_won = match.winner == si.team_name

    # Process first innings (batting team = team1, bowling/fielding = team2)
    team1_ratings = _rate_innings_players(
        batting_innings=fi,
        bowling_innings=si,  # team2 bowled in first innings
        fielding_events=fi.fielding_events,  # fielding events during first innings (by team2 fielders)
        ctx=ctx,
        is_batting_team_winning=team1_won,
        is_bowling_team_winning=team2_won,
        is_chasing=False,
        team_name=fi.team_name,
        bowling_team_name=si.team_name,
    )

    # Process second innings (batting team = team2, bowling/fielding = team1)
    team2_ratings = _rate_innings_players(
        batting_innings=si,
        bowling_innings=fi,  # team1 bowled in second innings
        fielding_events=si.fielding_events,  # fielding events during second innings (by team1 fielders)
        ctx=ctx,
        is_batting_team_winning=team2_won,
        is_bowling_team_winning=team1_won,
        is_chasing=True,
        team_name=si.team_name,
        bowling_team_name=fi.team_name,
    )

    # Merge batting and bowling ratings for each player
    # Team 1 batted in innings 1, bowled in innings 2
    team1_final = _merge_team_ratings(
        team_name=fi.team_name,
        batting_ratings=team1_ratings["batters"],
        bowling_ratings=team2_ratings["bowlers"],  # team1's bowling happened in innings 2
        fielding_ratings=team2_ratings["fielders"],  # team1's fielding happened in innings 2
    )

    # Team 2 batted in innings 2, bowled in innings 1
    team2_final = _merge_team_ratings(
        team_name=si.team_name,
        batting_ratings=team2_ratings["batters"],
        bowling_ratings=team1_ratings["bowlers"],  # team2's bowling happened in innings 1
        fielding_ratings=team1_ratings["fielders"],  # team2's fielding happened in innings 1
    )

    return {
        "team1": {"name": fi.team_name, "players": team1_final},
        "team2": {"name": si.team_name, "players": team2_final},
        "context": ctx,
    }


def _rate_innings_players(
    batting_innings: Innings,
    bowling_innings: Innings,
    fielding_events: List[FieldingEvent],
    ctx: MatchContext,
    is_batting_team_winning: bool,
    is_bowling_team_winning: bool,
    is_chasing: bool,
    team_name: str,
    bowling_team_name: str,
) -> dict:
    """Rate all players involved in one innings.

    Returns dict with 'batters', 'bowlers', 'fielders' lists of
    (name, role, rating, details).
    """
    batters = []
    for entry in batting_innings.batting:
        rating, details = calculate_batting_rating(
            entry, ctx, is_batting_team_winning, is_chasing
        )
        batters.append({
            "name": entry.name,
            "role": entry.role,
            "rating": rating,
            "details": details,
            "did_bat": entry.did_bat,
            "balls": entry.balls,
        })

    # Bowling entries come from the bowling_innings
    # (the opposing team bowled during this innings)
    bowlers = []
    for entry in bowling_innings.bowling:
        rating, details = calculate_bowling_rating(
            entry, ctx, is_bowling_team_winning
        )
        bowlers.append({
            "name": entry.name,
            "role": entry.role,
            "rating": rating,
            "details": details,
            "did_bowl": entry.did_bowl,
            "total_balls": entry.total_balls,
        })

    # Fielding ratings for the bowling/fielding team
    fielder_names = set()
    for event in fielding_events:
        fielder_names.add(event.player_name)
    # Also add all bowlers as potential fielders
    for entry in bowling_innings.bowling:
        fielder_names.add(entry.name)
    # And all batters from the bowling team
    for entry in bowling_innings.batting:
        fielder_names.add(entry.name)

    fielders = {}
    for name in fielder_names:
        rating, details = calculate_fielding_rating(name, fielding_events)
        fielders[name] = {"rating": rating, "details": details}

    return {"batters": batters, "bowlers": bowlers, "fielders": fielders}


def _merge_team_ratings(
    team_name: str,
    batting_ratings: list,
    bowling_ratings: list,
    fielding_ratings: dict,
) -> List[PlayerRating]:
    """Merge batting, bowling, and fielding ratings into final player ratings."""

    # Build lookup maps
    batting_map = {r["name"]: r for r in batting_ratings}
    bowling_map = {r["name"]: r for r in bowling_ratings}

    # Collect all unique player names
    all_names = set()
    for r in batting_ratings:
        all_names.add(r["name"])
    for r in bowling_ratings:
        all_names.add(r["name"])

    results: List[PlayerRating] = []

    for name in all_names:
        bat_info = batting_map.get(name)
        bowl_info = bowling_map.get(name)
        field_info = fielding_ratings.get(name)

        # Determine role from whichever entry has it
        if bat_info:
            role = bat_info["role"]
        elif bowl_info:
            role = bowl_info["role"]
        else:
            role = PlayerRole.BATTER

        did_bat = bat_info["did_bat"] if bat_info else False
        did_bowl = bowl_info["did_bowl"] if bowl_info else False

        bat_rating = bat_info["rating"] if bat_info else 5.0
        bowl_rating = bowl_info["rating"] if bowl_info else 5.0
        field_rating = field_info["rating"] if field_info else 5.0

        bat_details = bat_info["details"] if bat_info else {}
        bowl_details = bowl_info["details"] if bowl_info else {}
        field_details = field_info["details"] if field_info else {}

        # Get balls information for weight redistribution check
        bat_balls = bat_info.get("balls", 0) if bat_info else 0
        bowl_balls = bowl_info.get("total_balls", 0) if bowl_info else 0

        # When a batter bowls 6+ balls or a bowler bats 6+ balls, give some weight to the
        # other skill, but keep the primary role dominant (so a bowler's overall stays
        # bowling-driven and a batter's overall stays batting-driven).
        # Don't change weights for all-rounders (they already have balanced weights).
        is_all_rounder = role in (PlayerRole.BATTING_ALL_ROUNDER, PlayerRole.BOWLING_ALL_ROUNDER)
        is_bowler_role = role in (PlayerRole.BOWLER, PlayerRole.BOWLING_ALL_ROUNDER)
        if not is_all_rounder:
            if did_bat and bowl_balls >= 6 and not is_bowler_role:
                # Batter also bowled at least 6 balls: batting stays primary
                bat_w, bowl_w, field_w = 0.75, 0.15, 0.1
            elif did_bowl and bat_balls >= 6 and is_bowler_role:
                # Bowler also batted at least 6 balls: bowling stays primary (overall reflects bowling)
                bat_w, bowl_w, field_w = 0.20, 0.65, 0.15
            else:
                bat_w, bowl_w, field_w = ROLE_WEIGHTS.get(
                    role, ROLE_WEIGHTS[PlayerRole.BATTER]
                )
        else:
            # Get weights based on role
            bat_w, bowl_w, field_w = ROLE_WEIGHTS.get(
                role, ROLE_WEIGHTS[PlayerRole.BATTER]
            )

        # If bowler batted less than 6 balls, set batting weight to 0
        if is_bowler_role and did_bat and bat_balls < 6:
            # Bowler faced less than 6 balls - batting weight should be 0
            # Redistribute batting weight proportionally to bowling and fielding
            total_w = bowl_w + field_w
            if total_w > 0:
                # Redistribute bat_w proportionally to bowling and fielding
                bowl_w = bowl_w + (bat_w * bowl_w / total_w)
                field_w = field_w + (bat_w * field_w / total_w)
            bat_w = 0.0

        # Overall = weighted average of components that apply. Never use a single
        # component (e.g. field_rating) alone when the player batted or bowled.
        if not did_bat and not did_bowl:
            # Only fielding applies (e.g. fielder who didn't bat or bowl)
            overall = field_rating
        elif not did_bat:
            # Did not bat: use bowling + fielding only (redistribute batting weight)
            total_w = bowl_w + field_w
            if total_w > 0:
                overall = (bowl_rating * bowl_w + field_rating * field_w) / total_w
            else:
                overall = 5.0
        elif not did_bowl:
            # Did not bowl: use batting + fielding only (redistribute bowling weight).
            # Formula: weighted avg of bat and field so overall reflects both, not just fielding.
            total_w = bat_w + field_w
            if total_w > 0:
                overall = (bat_rating * bat_w + field_rating * field_w) / total_w
            else:
                overall = 5.0
        else:
            overall = bat_rating * bat_w + bowl_rating * bowl_w + field_rating * field_w

        overall = max(0.0, min(10.0, round(overall, 1)))

        results.append(PlayerRating(
            name=name,
            team=team_name,
            role=role,
            overall_rating=overall,
            batting_rating=bat_rating,
            bowling_rating=bowl_rating,
            fielding_rating=field_rating,
            batting_details=bat_details,
            bowling_details=bowl_details,
            fielding_details=field_details,
            did_bat=did_bat,
            did_bowl=did_bowl,
        ))

    # Sort by batting order (batters first), then bowlers
    batting_order = {r["name"]: i for i, r in enumerate(batting_ratings)}
    bowling_order = {r["name"]: i for i, r in enumerate(bowling_ratings)}

    def sort_key(pr: PlayerRating) -> tuple:
        bat_idx = batting_order.get(pr.name, 999)
        bowl_idx = bowling_order.get(pr.name, 999)
        return (bat_idx, bowl_idx)

    results.sort(key=sort_key)
    return results
