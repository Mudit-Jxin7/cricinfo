"""Batting rating calculator with context-aware adjustments.

Base rating = 5.0 (average T20 performance).
Various factors push the rating up or down.
"""

from __future__ import annotations

from .context import MatchContext, get_strike_rate_context_adjustment, get_chase_pressure_factor
from .models import BattingEntry, DismissalType, PlayerRole


def calculate_batting_rating(
    entry: BattingEntry,
    ctx: MatchContext,
    is_winning_team: bool,
    is_chasing: bool,
) -> tuple[float, dict]:
    """Calculate a batting rating from 0-10 for a single innings.

    Returns:
        (rating, details_dict) where details_dict contains the breakdown.
    """
    if not entry.did_bat:
        return 5.0, {"note": "Did not bat"}

    base = 5.0
    details: dict = {}

    # Bowlers get reduced penalties for batting metrics (SR, boundary %, chase)
    is_bowler = entry.role in (PlayerRole.BOWLER, PlayerRole.BOWLING_ALL_ROUNDER)

    # ── 1. Runs scored component (0 to +3.0) ──
    runs_score = _runs_component(entry.runs)
    details["runs"] = {"value": entry.runs, "score": round(runs_score, 2)}

    # ── 2. Strike rate component (-1.5 to +2.0) ──
    if entry.balls >= 2:  # need at least 2 balls to judge SR
        match_sr = ctx.match_run_rate * 100 / 6 if ctx.match_run_rate > 0 else 130.0
        sr_score = get_strike_rate_context_adjustment(entry.strike_rate, match_sr)
        # Don't penalize for poor SR if balls < 4, but still reward good SR
        if entry.balls < 4 and sr_score < 0:
            sr_score = 0.0
        # Scale down SR impact for shorter innings
        if entry.balls < 5:
            sr_score *= 0.35
        elif entry.balls < 10:
            sr_score *= 0.5
        elif entry.balls < 15:
            sr_score *= 0.75
    else:
        sr_score = 0.0
    # Bowlers get reduced penalty for poor strike rate
    if is_bowler and sr_score < 0:
        sr_score *= 0.5
    details["strike_rate"] = {
        "value": round(entry.strike_rate, 1),
        "score": round(sr_score, 2),
    }

    # ── 3. Boundary percentage component (-0.5 to +1.0) ──
    if entry.balls >= 2 and entry.runs > 0:
        bp = entry.boundary_percentage
        if bp >= 70:
            boundary_score = 1.0
        elif bp >= 60:
            boundary_score = 0.75
        elif bp >= 50:
            boundary_score = 0.5
        elif bp >= 35:
            boundary_score = 0.2
        elif bp >= 20:
            boundary_score = 0.0
        else:
            boundary_score = -0.3
        # Don't penalize for low boundary % if balls < 4, but still reward high %
        if entry.balls < 4 and boundary_score < 0:
            boundary_score = 0.0
        # Short innings discount
        if entry.balls < 5:
            boundary_score *= 0.35
        elif entry.balls < 10:
            boundary_score *= 0.5
    else:
        boundary_score = 0.0
    # Bowlers get reduced penalty for low boundary %
    if is_bowler and boundary_score < 0:
        boundary_score *= 0.5
    details["boundary_pct"] = {
        "value": round(entry.boundary_percentage, 1),
        "score": round(boundary_score, 2),
    }

    # ── 4. Balls faced / anchoring context (-0.5 to +0.5) ──
    # Position-aware anchor scoring: openers need more balls, lower order needs fewer
    anchor_score = 0.0
    
    # Determine minimum balls required based on batting position
    if entry.batting_position <= 2:
        # Openers: need 30+ balls to anchor
        min_balls_anchor = 30
        min_balls_partial = 25
    elif entry.batting_position <= 4:
        # Top-middle order: need 25+ balls
        min_balls_anchor = 25
        min_balls_partial = 20
    elif entry.batting_position <= 6:
        # Middle order: need 20+ balls
        min_balls_anchor = 20
        min_balls_partial = 15
    else:
        # Lower order: need 15+ balls
        min_balls_anchor = 15
        min_balls_partial = 12
    
    if entry.balls >= min_balls_anchor:
        # Long innings - reward if SR is decent, penalize if too slow
        if entry.strike_rate >= 120:
            anchor_score = 0.5  # anchored AND scored fast
        elif entry.strike_rate >= 100:
            anchor_score = 0.2
        else:
            anchor_score = -0.3  # too slow for T20
    elif entry.balls >= min_balls_partial:
        # Partial anchor - reward good SR, penalize poor SR
        if entry.strike_rate >= 130:
            anchor_score = 0.3
        elif entry.strike_rate < 90:
            anchor_score = -0.2
    details["anchor"] = {"balls_faced": entry.balls, "score": round(anchor_score, 2)}

    # ── 5. Batting position modifier ──
    position_score = 0.0
    if entry.batting_position >= 7 and entry.runs >= 15:
        # Lower-order contributions are more valuable per run
        position_score = min(0.5, entry.runs * 0.02)
    elif entry.batting_position >= 5 and entry.runs >= 20:
        position_score = min(0.3, entry.runs * 0.01)
    details["position"] = {
        "position": entry.batting_position,
        "score": round(position_score, 2),
    }

    # ── 6. Not out in chase bonus (+0.0 to +0.5) ──
    notout_score = 0.0
    if is_chasing and entry.dismissal == DismissalType.NOT_OUT and entry.runs > 0:
        if is_winning_team:
            # Finished the chase -- "closer" bonus
            notout_score = 0.5
        else:
            # Remained not out but team lost -- smaller bonus
            notout_score = 0.15
    details["not_out_chase"] = {"score": round(notout_score, 2)}

    # ── 7. Match result (informational only, no score impact) ──
    details["match_result"] = {"won": is_winning_team, "score": 0.0}

    # ── 8. Chase pressure bonus (-0.5 to +1.0) ──
    chase_score = 0.0
    if is_chasing and entry.balls >= 2:
        pressure = get_chase_pressure_factor(ctx.required_run_rate)
        rrr_as_sr = ctx.required_run_rate * 100 / 6 if ctx.required_run_rate > 0 else 130.0
        if entry.strike_rate >= rrr_as_sr:
            # Batsman kept up with or exceeded the RRR
            chase_score = pressure * 1.0  # up to 1.0
        elif entry.strike_rate >= rrr_as_sr * 0.7:
            chase_score = pressure * 0.3
        else:
            # Failed under pressure
            chase_score = -pressure * 0.5
        # Don't penalize for failing under chase pressure if balls < 4
        if entry.balls < 4 and chase_score < 0:
            chase_score = 0.0
        # Scale down for very short innings
        if entry.balls < 5:
            chase_score *= 0.5
    # Bowlers get reduced penalty for failing under chase pressure
    if is_bowler and chase_score < 0:
        chase_score *= 0.5
    details["chase_pressure"] = {"rrr": round(ctx.required_run_rate, 2), "score": round(chase_score, 2)}

    # ── 9. Cameo impact bonus (short explosive innings) ──
    cameo_score = 0.0
    if entry.balls >= 2 and entry.balls <= 10 and entry.strike_rate >= 180:
        # Reward explosive cameos -- a 10(3) with boundaries is impactful
        impact = entry.runs / entry.balls  # runs per ball
        if impact >= 3.0:
            cameo_score = 0.8
        elif impact >= 2.5:
            cameo_score = 0.6
        elif impact >= 2.0:
            cameo_score = 0.4
        elif impact >= 1.5:
            cameo_score = 0.2
        # Extra for sixes in short cameos
        if entry.sixes >= 1 and entry.balls <= 5:
            cameo_score += 0.2
    details["cameo_impact"] = {"score": round(cameo_score, 2)}

    # ── 10. Duck penalty ──
    duck_score = 0.0
    if entry.is_golden_duck:
        duck_score = -2.0
    elif entry.is_duck:
        duck_score = -1.0
    details["duck"] = {"score": round(duck_score, 2)}

    # ── Combine ──
    total = base + runs_score + sr_score + boundary_score + anchor_score + position_score
    total += notout_score + chase_score + cameo_score + duck_score

    # Clamp to 0-10
    total = max(0.0, min(10.0, total))
    total = round(total, 1)

    details["total"] = total
    return total, details


def _runs_component(runs: int) -> float:
    """Map runs scored to a 0 to +3.0 score using piecewise linear interpolation."""
    if runs <= 0:
        return 0.0
    breakpoints = [
        (5, 0.2),
        (10, 0.4),
        (15, 0.7),
        (20, 1.0),
        (30, 1.5),
        (40, 2.0),
        (50, 2.5),
        (75, 2.8),
        (100, 3.0),
    ]
    prev_r, prev_s = 0, 0.0
    for bp_runs, bp_score in breakpoints:
        if runs <= bp_runs:
            frac = (runs - prev_r) / (bp_runs - prev_r)
            return prev_s + frac * (bp_score - prev_s)
        prev_r, prev_s = bp_runs, bp_score
    return 3.0  # 100+
