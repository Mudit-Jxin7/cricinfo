"""Bowling rating calculator with context-aware adjustments.

Base rating = 5.0 (average T20 performance).
Economy is judged relative to the match, not absolute.
Wicket quality (dismissing set batsmen) matters.
"""

from __future__ import annotations

from .context import MatchContext, get_economy_context_adjustment
from .models import BowlingEntry


def calculate_bowling_rating(
    entry: BowlingEntry,
    ctx: MatchContext,
    is_winning_team: bool,
) -> tuple[float, dict]:
    """Calculate a bowling rating from 0-10 for a single spell.

    Returns:
        (rating, details_dict) with a breakdown.
    """
    if not entry.did_bowl:
        return 5.0, {"note": "Did not bowl"}

    base = 5.0
    details: dict = {}

    # ── 1. Wickets component (0 to +3.0) ──
    wicket_score = _wickets_component(entry.wickets)
    details["wickets"] = {"value": entry.wickets, "score": round(wicket_score, 2)}

    # ── 2. Economy rate component (-2.0 to +2.5) ──
    eco_score = get_economy_context_adjustment(entry.economy_rate, ctx.match_economy)
    # Scale down for bowlers who bowled very few balls
    overs_bowled = entry.total_balls / 6
    if overs_bowled < 2:
        eco_score *= 0.5
    elif overs_bowled < 3:
        eco_score *= 0.75
    details["economy"] = {
        "value": round(entry.economy_rate, 2),
        "match_economy": round(ctx.match_economy, 2),
        "score": round(eco_score, 2),
    }

    # ── 3. Maidens (+0.0 to +1.5 per maiden) ──
    maiden_score = min(entry.maidens * 1.5, 3.0)  # cap at 3.0
    details["maidens"] = {"value": entry.maidens, "score": round(maiden_score, 2)}

    # ── 4. Overs bowled modifier ──
    # Bowling full quota (4 overs) shows trust; no penalty for short spells
    quota_score = 0.0
    if overs_bowled >= 4.0:
        quota_score = 0.1  # completed full quota
    elif overs_bowled >= 3.0:
        quota_score = 0.05
    details["overs_bowled"] = {
        "value": round(overs_bowled, 1),
        "score": round(quota_score, 2),
    }

    # ── 5. Wicket quality (+0.0 to +1.0) ──
    wq_score = 0.0
    if entry.dismissed_batsmen_runs:
        for runs in entry.dismissed_batsmen_runs:
            if runs >= 50:
                wq_score += 0.4  # dismissed a half-centurion
            elif runs >= 30:
                wq_score += 0.3  # dismissed a set batsman
            elif runs >= 15:
                wq_score += 0.15
            else:
                wq_score += 0.05  # early wicket, lower value but still useful
        wq_score = min(wq_score, 1.0)
    details["wicket_quality"] = {
        "dismissed_runs": entry.dismissed_batsmen_runs,
        "score": round(wq_score, 2),
    }

    # ── 6. Match result (informational only, no score impact) ──
    details["match_result"] = {"won": is_winning_team, "score": 0.0}

    # ── 7. Extras penalty: -0.05 per wide, -0.2 per no ball ──
    extras_score = -(entry.wides * 0.05 + entry.no_balls * 0.2)
    details["extras"] = {
        "wides": entry.wides,
        "no_balls": entry.no_balls,
        "score": round(extras_score, 2),
    }

    # ── Combine ──
    total = base + wicket_score + eco_score + maiden_score
    total += quota_score + wq_score + extras_score

    total = max(0.0, min(10.0, total))
    total = round(total, 1)

    details["total"] = total
    return total, details


def _wickets_component(wickets: int) -> float:
    """Map wickets to a 0 to +3.0 score."""
    mapping = {0: 0.0, 1: 1.0, 2: 1.8, 3: 2.5, 4: 2.8, 5: 3.0}
    if wickets in mapping:
        return mapping[wickets]
    return 3.0  # 5+ wickets all get max
