"""Data models for the CricScore rating engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class PlayerRole(Enum):
    BATTER = "batter"
    BOWLER = "bowler"
    BATTING_ALL_ROUNDER = "batting_all_rounder"
    BOWLING_ALL_ROUNDER = "bowling_all_rounder"
    WICKET_KEEPER = "wicket_keeper"


class DismissalType(Enum):
    NOT_OUT = "not_out"
    BOWLED = "bowled"
    CAUGHT = "caught"
    LBW = "lbw"
    RUN_OUT = "run_out"
    STUMPED = "stumped"
    HIT_WICKET = "hit_wicket"
    RETIRED_HURT = "retired_hurt"
    DNB = "did_not_bat"


class FieldingEventType(Enum):
    CATCH = "catch"
    DIRECT_RUN_OUT = "direct_run_out"
    ASSISTED_RUN_OUT = "assisted_run_out"
    STUMPING = "stumping"
    DROPPED_CATCH = "dropped_catch"
    MISFIELD = "misfield"


@dataclass
class BattingEntry:
    """A single batsman's innings."""
    name: str
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    dismissal: DismissalType = DismissalType.NOT_OUT
    batting_position: int = 1  # 1-11
    role: PlayerRole = PlayerRole.BATTER

    @property
    def strike_rate(self) -> float:
        if self.balls == 0:
            return 0.0
        return (self.runs / self.balls) * 100

    @property
    def boundary_runs(self) -> int:
        return (self.fours * 4) + (self.sixes * 6)

    @property
    def boundary_percentage(self) -> float:
        if self.runs == 0:
            return 0.0
        return min((self.boundary_runs / self.runs) * 100, 100.0)

    @property
    def is_duck(self) -> bool:
        return self.runs == 0 and self.dismissal not in (
            DismissalType.NOT_OUT,
            DismissalType.RETIRED_HURT,
            DismissalType.DNB,
        )

    @property
    def is_golden_duck(self) -> bool:
        return self.is_duck and self.balls <= 1

    @property
    def did_bat(self) -> bool:
        return self.dismissal != DismissalType.DNB


@dataclass
class BowlingEntry:
    """A single bowler's spell."""
    name: str
    overs: float = 0.0  # e.g. 3.4 means 3 overs and 4 balls
    maidens: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    wides: int = 0
    no_balls: int = 0
    role: PlayerRole = PlayerRole.BOWLER
    # Runs scored by batsmen dismissed by this bowler (for wicket quality)
    dismissed_batsmen_runs: List[int] = field(default_factory=list)

    @property
    def total_balls(self) -> int:
        """Convert overs to total legal deliveries."""
        full_overs = int(self.overs)
        partial = round((self.overs - full_overs) * 10)
        return full_overs * 6 + partial

    @property
    def economy_rate(self) -> float:
        if self.total_balls == 0:
            return 0.0
        overs_decimal = self.total_balls / 6
        return self.runs_conceded / overs_decimal

    @property
    def did_bowl(self) -> bool:
        return self.total_balls > 0


@dataclass
class FieldingEvent:
    """A single fielding event for a player."""
    player_name: str
    event_type: FieldingEventType


@dataclass
class Innings:
    """One innings of a T20 match."""
    team_name: str
    total_runs: int
    total_wickets: int
    total_overs: float  # e.g. 20.0 or 18.3
    batting: List[BattingEntry] = field(default_factory=list)
    bowling: List[BowlingEntry] = field(default_factory=list)
    fielding_events: List[FieldingEvent] = field(default_factory=list)
    is_chasing: bool = False

    @property
    def run_rate(self) -> float:
        balls = int(self.total_overs) * 6 + round((self.total_overs - int(self.total_overs)) * 10)
        if balls == 0:
            return 0.0
        return (self.total_runs / balls) * 6

    @property
    def match_strike_rate(self) -> float:
        """Average SR across the innings."""
        return self.run_rate * 100 / 6


@dataclass
class Match:
    """A complete T20 match."""
    team1_name: str
    team2_name: str
    first_innings: Innings = field(default_factory=lambda: Innings("", 0, 0, 0.0))
    second_innings: Innings = field(default_factory=lambda: Innings("", 0, 0, 0.0))
    winner: str = ""  # team name or "tie" / "no_result"
    toss_winner: str = ""
    toss_decision: str = ""  # "bat" or "field"
    venue: str = ""

    @property
    def match_economy(self) -> float:
        """Average economy across both innings."""
        total_runs = self.first_innings.total_runs + self.second_innings.total_runs

        def _balls(overs: float) -> int:
            full = int(overs)
            part = round((overs - full) * 10)
            return full * 6 + part

        total_balls = _balls(self.first_innings.total_overs) + _balls(self.second_innings.total_overs)
        if total_balls == 0:
            return 0.0
        total_overs = total_balls / 6
        return total_runs / total_overs

    @property
    def match_run_rate(self) -> float:
        return self.match_economy

    @property
    def required_run_rate(self) -> float:
        """RRR for the chasing team at the start of the chase."""
        target = self.first_innings.total_runs + 1
        return target / 20.0 * 6 / 6  # target per over


@dataclass
class PlayerRating:
    """Final computed rating for a player."""
    name: str
    team: str
    role: PlayerRole
    overall_rating: float = 5.0
    batting_rating: float = 5.0
    bowling_rating: float = 5.0
    fielding_rating: float = 5.0
    # Breakdown details for display
    batting_details: dict = field(default_factory=dict)
    bowling_details: dict = field(default_factory=dict)
    fielding_details: dict = field(default_factory=dict)
    did_bat: bool = False
    did_bowl: bool = False

    @property
    def rating_color(self) -> str:
        r = self.overall_rating
        if r >= 9.0:
            return "exceptional"
        elif r >= 7.5:
            return "great"
        elif r >= 6.5:
            return "good"
        elif r >= 5.5:
            return "average"
        elif r >= 4.5:
            return "below_average"
        else:
            return "poor"
