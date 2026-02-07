"""Context analyzer for match situation metrics.

Provides contextual adjustments so that ratings reflect the match situation,
not just raw numbers. For example, an economy of 8 in a 220-run game is good,
but economy of 8 in a 140-run game is bad.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Match, Innings


@dataclass
class MatchContext:
    """Computed contextual metrics for a match."""

    # Overall match metrics
    match_economy: float = 8.0  # average eco across both innings
    match_run_rate: float = 8.0
    first_innings_rr: float = 8.0
    second_innings_rr: float = 8.0

    # Chase-specific
    target: int = 0  # target for chasing team
    required_run_rate: float = 8.0  # RRR at start of chase
    chase_successful: bool = False

    # Scoring context
    is_high_scoring: bool = False  # combined 350+
    is_low_scoring: bool = False   # combined < 280

    # Team results
    first_batting_team_won: bool = False
    winner: str = ""


def analyze_match_context(match: Match) -> MatchContext:
    """Analyze the match and produce contextual metrics used by rating calculators."""
    ctx = MatchContext()

    fi = match.first_innings
    si = match.second_innings

    # Match economy / run rate
    ctx.match_economy = match.match_economy
    ctx.match_run_rate = match.match_run_rate
    ctx.first_innings_rr = fi.run_rate
    ctx.second_innings_rr = si.run_rate

    # Target and chase
    ctx.target = fi.total_runs + 1
    if fi.total_runs > 0:
        ctx.required_run_rate = ctx.target / 20.0
    else:
        ctx.required_run_rate = 0.0

    # Determine if chase was successful
    ctx.chase_successful = si.total_runs >= ctx.target

    # Scoring context
    combined = fi.total_runs + si.total_runs
    ctx.is_high_scoring = combined >= 350
    ctx.is_low_scoring = combined < 280

    # Winner info
    ctx.winner = match.winner
    ctx.first_batting_team_won = (match.winner == fi.team_name)

    return ctx


def get_chase_pressure_factor(required_rr: float) -> float:
    """Return a multiplier (0.0 to 1.0) indicating how pressured the chase is.

    RRR <= 6  : 0.0  (easy chase, no pressure bonus)
    RRR  7-8  : 0.2
    RRR  9-10 : 0.5
    RRR 11-12 : 0.7
    RRR 12+   : 1.0  (maximum chase pressure)
    """
    if required_rr <= 6:
        return 0.0
    elif required_rr <= 8:
        return 0.1 + (required_rr - 6) * 0.05
    elif required_rr <= 10:
        return 0.2 + (required_rr - 8) * 0.15
    elif required_rr <= 12:
        return 0.5 + (required_rr - 10) * 0.1
    else:
        return min(1.0, 0.7 + (required_rr - 12) * 0.1)


def get_economy_context_adjustment(bowler_economy: float, match_economy: float) -> float:
    """Return an adjustment based on how the bowler's economy compares to the match average.

    A bowler with eco far below the match average gets a positive adjustment;
    a bowler with eco far above gets a negative adjustment.

    Returns a value roughly in [-2.0, +2.5].
    """
    if match_economy == 0:
        return 0.0

    diff = match_economy - bowler_economy  # positive = bowler is better

    if diff >= 5:
        return 2.5
    elif diff >= 3:
        return 2.0
    elif diff >= 2:
        return 1.5
    elif diff >= 1:
        return 1.0
    elif diff >= 0:
        return diff * 0.8  # 0 to 0.8
    elif diff >= -1:
        return diff * 0.5  # -0.5 to 0
    elif diff >= -2:
        return -0.5 + (diff + 1) * 0.5  # -0.5 to -1.0
    elif diff >= -4:
        return -1.0 + (diff + 2) * 0.25  # -1.0 to -1.5
    else:
        return max(-2.0, -1.5 + (diff + 4) * 0.1)


def get_strike_rate_context_adjustment(batsman_sr: float, match_sr: float) -> float:
    """Return an adjustment for batsman SR relative to the match average SR.

    Returns roughly [-1.5, +2.0].
    """
    if match_sr == 0:
        return 0.0

    # Ratio of batsman SR to match SR
    ratio = batsman_sr / match_sr

    if ratio >= 1.6:
        return 2.0
    elif ratio >= 1.4:
        return 1.5
    elif ratio >= 1.2:
        return 1.0
    elif ratio >= 1.0:
        return (ratio - 1.0) * 5.0  # 0.0 to 1.0
    elif ratio >= 0.8:
        return (ratio - 1.0) * 2.5  # -0.5 to 0.0
    elif ratio >= 0.6:
        return -0.5 + (ratio - 0.8) * 2.5  # -1.0 to -0.5
    else:
        return max(-1.5, -1.0 + (ratio - 0.6) * 2.5)
