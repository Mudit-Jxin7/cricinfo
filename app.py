"""CricScore - T20 Cricket Player Rating System.

Flask web application that generates SoFaScore-style player ratings (0-10)
for T20 cricket matches.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for

from rating_engine.models import (
    BattingEntry,
    BowlingEntry,
    DismissalType,
    FieldingEvent,
    FieldingEventType,
    Innings,
    Match,
    PlayerRole,
)
from rating_engine.calculator import calculate_match_ratings
import database as db

app = Flask(__name__)


def _rating_color(rating: float) -> str:
    """Return CSS class name for a rating value."""
    if rating >= 8.0:
        return "exceptional"
    elif rating >= 7.0:
        return "great"
    elif rating >= 6.0:
        return "good"
    elif rating >= 5.0:
        return "average"
    elif rating >= 4.0:
        return "below_average"
    return "poor"


# Make available in Jinja templates
app.jinja_env.globals["_rating_color"] = _rating_color


# ───── Pages ─────

@app.route("/")
def index():
    """Render the match input form."""
    return render_template("index.html")


@app.route("/matches")
def matches_page():
    """Show all saved matches."""
    matches = db.get_all_matches()
    return render_template("matches.html", matches=matches)


@app.route("/match/<int:match_id>")
def match_detail(match_id):
    """Show a saved match with its player ratings."""
    match, players = db.get_match(match_id)
    if not match:
        return "Match not found", 404
    # Split players by team
    team1_players = [p for p in players if p["team"] == match["team1"]]
    team2_players = [p for p in players if p["team"] == match["team2"]]
    return render_template("match_detail.html", match=match,
                           team1_players=team1_players, team2_players=team2_players)


@app.route("/players")
def players_page():
    """Show all players with search and form guide."""
    q = request.args.get("q", "").strip()
    if q:
        players = db.search_players_with_form(q)
    else:
        players = db.get_all_players_with_form()
    return render_template("players.html", players=players, query=q)


@app.route("/player/<name>")
def player_detail(name):
    """Show a player's full rating history."""
    history = db.get_player_history(name)
    if not history:
        return "Player not found", 404

    # Compute averages
    avg_overall = round(sum(h["overall_rating"] for h in history) / len(history), 1)
    avg_bat = round(sum(h["batting_rating"] for h in history) / len(history), 1)
    avg_bowl = round(sum(h["bowling_rating"] for h in history) / len(history), 1)
    best = max(h["overall_rating"] for h in history)
    total_runs = sum(h.get("runs", 0) or 0 for h in history)
    total_wickets = sum(h.get("wickets", 0) or 0 for h in history)
    mvp_count = sum(1 for h in history if h.get("is_mvp"))

    # Batting stats (for batters)
    total_balls = sum(h.get("balls", 0) or 0 for h in history)
    dismissals = sum(
        1 for h in history
        if h.get("did_bat") and (h.get("dismissal") or "").lower() not in ("not_out", "did_not_bat", "")
    )
    batting_avg = round(total_runs / dismissals, 1) if dismissals > 0 else None
    batting_sr = round((total_runs / total_balls) * 100, 1) if total_balls > 0 else None

    # Bowling stats (for bowlers)
    total_runs_conceded = sum(h.get("runs_conceded", 0) or 0 for h in history)
    total_overs_bowled = sum(h.get("overs_bowled", 0) or 0 for h in history)
    full_overs = int(total_overs_bowled)
    part_balls = round((total_overs_bowled - full_overs) * 10)
    total_balls_bowled = full_overs * 6 + part_balls
    bowling_avg = round(total_runs_conceded / total_wickets, 1) if total_wickets > 0 else None
    bowling_sr = round(total_balls_bowled / total_wickets, 1) if total_wickets > 0 else None
    economy = round(total_runs_conceded / (total_balls_bowled / 6), 2) if total_balls_bowled > 0 else None

    stats = {
        "matches": len(history),
        "avg_overall": avg_overall,
        "avg_bat": avg_bat,
        "avg_bowl": avg_bowl,
        "best": best,
        "total_runs": total_runs,
        "total_wickets": total_wickets,
        "mvp_count": mvp_count,
        "batting_avg": batting_avg,
        "batting_sr": batting_sr,
        "bowling_avg": bowling_avg,
        "bowling_sr": bowling_sr,
        "economy": economy,
    }

    awards = db.get_player_awards(name)

    # Form guide (last 5, most recent first)
    form_guide = db.get_player_form(name, 5)

    # Win/Loss impact
    win_ratings = []
    loss_ratings = []
    win_bat = []
    loss_bat = []
    win_bowl = []
    loss_bowl = []
    for h in history:
        team_won = (h.get("winner", "") == h.get("team", ""))
        if team_won:
            win_ratings.append(h["overall_rating"])
            win_bat.append(h["batting_rating"])
            win_bowl.append(h["bowling_rating"])
        else:
            loss_ratings.append(h["overall_rating"])
            loss_bat.append(h["batting_rating"])
            loss_bowl.append(h["bowling_rating"])

    win_loss = {
        "wins": len(win_ratings),
        "losses": len(loss_ratings),
        "avg_win": round(sum(win_ratings) / len(win_ratings), 1) if win_ratings else 0,
        "avg_loss": round(sum(loss_ratings) / len(loss_ratings), 1) if loss_ratings else 0,
        "avg_bat_win": round(sum(win_bat) / len(win_bat), 1) if win_bat else 0,
        "avg_bat_loss": round(sum(loss_bat) / len(loss_bat), 1) if loss_bat else 0,
        "avg_bowl_win": round(sum(win_bowl) / len(win_bowl), 1) if win_bowl else 0,
        "avg_bowl_loss": round(sum(loss_bowl) / len(loss_bowl), 1) if loss_bowl else 0,
    }

    # Trend data for chart (chronological order)
    trend_labels = []
    trend_overall = []
    trend_bat = []
    trend_bowl = []
    for h in history:
        opponent = h["team2"] if h["team"] == h["team1"] else h["team1"]
        trend_labels.append(f"vs {opponent}")
        trend_overall.append(h["overall_rating"])
        trend_bat.append(h["batting_rating"])
        trend_bowl.append(h["bowling_rating"])

    trend_data = {
        "labels": trend_labels,
        "overall": trend_overall,
        "batting": trend_bat,
        "bowling": trend_bowl,
    }

    return render_template("player_detail.html", name=name, history=history,
                           stats=stats, awards=awards, trend_data=trend_data,
                           form_guide=form_guide, win_loss=win_loss)


@app.route("/compare")
def compare_page():
    """Head-to-head player comparison."""
    p1 = request.args.get("p1", "").strip()
    p2 = request.args.get("p2", "").strip()
    comparison = None
    if p1 and p2:
        comparison = db.get_player_comparison(p1, p2)
    all_players = db.get_all_player_names()
    return render_template("compare.html", p1=p1, p2=p2,
                           comparison=comparison, all_players=all_players)


@app.route("/api/players")
def api_players():
    """Return all player names for autocomplete."""
    names = db.get_all_player_names()
    return jsonify(names)


@app.route("/leaderboard")
def leaderboard():
    """Top 10 batsmen, bowlers, and all-rounders."""
    batsmen = db.get_top_batsmen(10)
    bowlers = db.get_top_bowlers(10)
    all_rounders = db.get_top_all_rounders(10)
    return render_template("leaderboard.html",
                           batsmen=batsmen, bowlers=bowlers, all_rounders=all_rounders)


# ───── Teams ─────

@app.route("/teams")
def teams_page():
    """Show all teams with win/loss record and avg rating."""
    sort_by = request.args.get("sort", "overall")
    if sort_by not in ("overall", "batting", "bowling"):
        sort_by = "overall"
    teams = db.get_all_teams()
    key = "avg_rating" if sort_by == "overall" else ("avg_bat" if sort_by == "batting" else "avg_bowl")
    teams.sort(key=lambda t: (t.get(key) or 0), reverse=True)
    return render_template("teams.html", teams=teams, sort_by=sort_by)


@app.route("/team/<name>")
def team_detail(name):
    """Show a team's match history with team avg ratings."""
    summary = db.get_team_summary(name)
    if not summary:
        return "Team not found", 404
    matches = db.get_team_matches(name)
    return render_template("team_detail.html", name=name, summary=summary,
                           matches=matches)


# ───── API Endpoints ─────

@app.route("/calculate", methods=["POST"])
def calculate():
    """Process the form data and calculate ratings."""
    try:
        data = request.get_json()
        match = _parse_match_data(data)
        results = calculate_match_ratings(match)

        team1_players = [_rating_to_dict(pr) for pr in results["team1"]["players"]]
        team2_players = [_rating_to_dict(pr) for pr in results["team2"]["players"]]

        return jsonify({
            "success": True,
            "team1": {"name": results["team1"]["name"], "players": team1_players},
            "team2": {"name": results["team2"]["name"], "players": team2_players},
            "match_info": {
                "team1_name": data.get("team1_name", "Team 1"),
                "team2_name": data.get("team2_name", "Team 2"),
                "team1_score": f"{data['first_innings']['total_runs']}/{data['first_innings']['total_wickets']} ({data['first_innings']['total_overs']} ov)",
                "team2_score": f"{data['second_innings']['total_runs']}/{data['second_innings']['total_wickets']} ({data['second_innings']['total_overs']} ov)",
                "winner": data.get("winner", ""),
                "venue": data.get("venue", ""),
            },
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/save_match", methods=["POST"])
def save_match():
    """Save calculated match ratings to the database."""
    try:
        data = request.get_json()
        match_info = data["match_info"]
        team1_players = data["team1"]["players"]
        team2_players = data["team2"]["players"]
        raw_form = data.get("raw_form", {})

        match_id = db.save_match(match_info, team1_players, team2_players, raw_form)
        return jsonify({"success": True, "match_id": match_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ───── Helpers ─────

def _parse_match_data(data: dict) -> Match:
    """Parse JSON form data into a Match object."""

    def _parse_batting(entries: list) -> list[BattingEntry]:
        result = []
        for i, e in enumerate(entries):
            if not e.get("name", "").strip():
                continue
            result.append(BattingEntry(
                name=e["name"].strip(),
                runs=int(e.get("runs", 0)),
                balls=int(e.get("balls", 0)),
                fours=int(e.get("fours", 0)),
                sixes=int(e.get("sixes", 0)),
                dismissal=DismissalType(e.get("dismissal", "caught")),
                batting_position=i + 1,
                role=PlayerRole(e.get("role", "batter")),
            ))
        return result

    def _parse_bowling(entries: list, batting_entries: list) -> list[BowlingEntry]:
        result = []
        for e in entries:
            if not e.get("name", "").strip():
                continue
            dismissed_runs = []
            if e.get("dismissed_batsmen_runs"):
                try:
                    dismissed_runs = [int(x) for x in str(e["dismissed_batsmen_runs"]).split(",") if x.strip()]
                except (ValueError, AttributeError):
                    dismissed_runs = []
            result.append(BowlingEntry(
                name=e["name"].strip(),
                overs=float(e.get("overs", 0)),
                maidens=int(e.get("maidens", 0)),
                runs_conceded=int(e.get("runs_conceded", 0)),
                wickets=int(e.get("wickets", 0)),
                wides=int(e.get("wides", 0)),
                no_balls=int(e.get("no_balls", 0)),
                role=PlayerRole(e.get("role", "bowler")),
                dismissed_batsmen_runs=dismissed_runs,
            ))
        return result

    def _parse_fielding(entries: list) -> list[FieldingEvent]:
        result = []
        for e in entries:
            if not e.get("player_name", "").strip():
                continue
            result.append(FieldingEvent(
                player_name=e["player_name"].strip(),
                event_type=FieldingEventType(e.get("event_type", "catch")),
            ))
        return result

    fi_data = data["first_innings"]
    si_data = data["second_innings"]
    first_batting = _parse_batting(fi_data.get("batting", []))
    second_batting = _parse_batting(si_data.get("batting", []))
    first_bowling = _parse_bowling(fi_data.get("bowling", []), second_batting)
    second_bowling = _parse_bowling(si_data.get("bowling", []), first_batting)

    first_innings = Innings(
        team_name=data.get("team1_name", "Team 1"),
        total_runs=int(fi_data.get("total_runs", 0)),
        total_wickets=int(fi_data.get("total_wickets", 0)),
        total_overs=float(fi_data.get("total_overs", 20)),
        batting=first_batting, bowling=second_bowling,
        fielding_events=_parse_fielding(fi_data.get("fielding_events", [])),
        is_chasing=False,
    )
    second_innings = Innings(
        team_name=data.get("team2_name", "Team 2"),
        total_runs=int(si_data.get("total_runs", 0)),
        total_wickets=int(si_data.get("total_wickets", 0)),
        total_overs=float(si_data.get("total_overs", 20)),
        batting=second_batting, bowling=first_bowling,
        fielding_events=_parse_fielding(si_data.get("fielding_events", [])),
        is_chasing=True,
    )

    return Match(
        team1_name=data.get("team1_name", "Team 1"),
        team2_name=data.get("team2_name", "Team 2"),
        first_innings=first_innings, second_innings=second_innings,
        winner=data.get("winner", ""), venue=data.get("venue", ""),
    )


def _rating_to_dict(pr) -> dict:
    return {
        "name": pr.name, "team": pr.team, "role": pr.role.value,
        "overall_rating": pr.overall_rating, "batting_rating": pr.batting_rating,
        "bowling_rating": pr.bowling_rating, "fielding_rating": pr.fielding_rating,
        "rating_color": pr.rating_color, "did_bat": pr.did_bat, "did_bowl": pr.did_bowl,
        "batting_details": pr.batting_details, "bowling_details": pr.bowling_details,
        "fielding_details": pr.fielding_details,
    }


if __name__ == "__main__":
    app.run(debug=True, port=5050)
