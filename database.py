"""SQLite database for persisting matches and player ratings."""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "cricscore.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team1 TEXT NOT NULL,
            team2 TEXT NOT NULL,
            team1_score TEXT NOT NULL,
            team2_score TEXT NOT NULL,
            winner TEXT NOT NULL DEFAULT '',
            venue TEXT NOT NULL DEFAULT '',
            mvp_name TEXT NOT NULL DEFAULT '',
            mvp_rating REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS player_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            team TEXT NOT NULL,
            role TEXT NOT NULL,
            overall_rating REAL NOT NULL,
            batting_rating REAL NOT NULL,
            bowling_rating REAL NOT NULL,
            fielding_rating REAL NOT NULL,
            did_bat INTEGER NOT NULL DEFAULT 0,
            did_bowl INTEGER NOT NULL DEFAULT 0,
            is_mvp INTEGER NOT NULL DEFAULT 0,
            runs INTEGER DEFAULT 0,
            balls INTEGER DEFAULT 0,
            fours INTEGER DEFAULT 0,
            sixes INTEGER DEFAULT 0,
            wickets INTEGER DEFAULT 0,
            overs_bowled REAL DEFAULT 0,
            runs_conceded INTEGER DEFAULT 0,
            economy REAL DEFAULT 0,
            dismissal TEXT DEFAULT '',
            FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_player_name ON player_ratings(player_name);
        CREATE INDEX IF NOT EXISTS idx_match_id ON player_ratings(match_id);
    """)
    # Add columns if they don't exist (migration for existing DBs)
    try:
        conn.execute("ALTER TABLE matches ADD COLUMN mvp_name TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE matches ADD COLUMN mvp_rating REAL NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE player_ratings ADD COLUMN is_mvp INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE player_ratings ADD COLUMN dismissal TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def save_match(match_info: dict, team1_players: list, team2_players: list,
               batting_data: dict) -> int:
    """Save a match and all player ratings. Returns match_id."""
    conn = get_db()
    cur = conn.cursor()

    all_players = team1_players + team2_players

    # Determine MVP (highest overall rating)
    mvp = max(all_players, key=lambda p: p["overall_rating"]) if all_players else None
    mvp_name = mvp["name"] if mvp else ""
    mvp_rating = mvp["overall_rating"] if mvp else 0

    cur.execute("""
        INSERT INTO matches (team1, team2, team1_score, team2_score, winner, venue,
                             mvp_name, mvp_rating, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        match_info["team1_name"],
        match_info["team2_name"],
        match_info["team1_score"],
        match_info["team2_score"],
        match_info.get("winner", ""),
        match_info.get("venue", ""),
        mvp_name,
        mvp_rating,
        datetime.now().isoformat(),
    ))
    match_id = cur.lastrowid

    # Build batting/bowling lookup from raw form data
    bat_lookup = {}
    bowl_lookup = {}
    for innings_key in ["first_innings", "second_innings"]:
        inn = batting_data.get(innings_key, {})
        for b in inn.get("batting", []):
            name = b.get("name", "").strip()
            if name:
                bat_lookup[name] = b
        for b in inn.get("bowling", []):
            name = b.get("name", "").strip()
            if name:
                bowl_lookup[name] = b

    for p in all_players:
        bat = bat_lookup.get(p["name"], {})
        bowl = bowl_lookup.get(p["name"], {})
        overs = float(bowl.get("overs", 0))
        runs_c = int(bowl.get("runs_conceded", 0))
        total_balls_bowled = int(overs) * 6 + round((overs - int(overs)) * 10)
        eco = (runs_c / (total_balls_bowled / 6)) if total_balls_bowled > 0 else 0.0

        cur.execute("""
            INSERT INTO player_ratings
            (match_id, player_name, team, role, overall_rating, batting_rating,
             bowling_rating, fielding_rating, did_bat, did_bowl, is_mvp,
             runs, balls, fours, sixes, wickets, overs_bowled, runs_conceded,
             economy, dismissal)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            match_id,
            p["name"],
            p["team"],
            p["role"],
            p["overall_rating"],
            p["batting_rating"],
            p["bowling_rating"],
            p["fielding_rating"],
            1 if p["did_bat"] else 0,
            1 if p["did_bowl"] else 0,
            1 if p["name"] == mvp_name else 0,
            int(bat.get("runs", 0)),
            int(bat.get("balls", 0)),
            int(bat.get("fours", 0)),
            int(bat.get("sixes", 0)),
            int(bowl.get("wickets", 0)),
            overs,
            runs_c,
            round(eco, 2),
            bat.get("dismissal", ""),
        ))

    conn.commit()
    conn.close()
    return match_id


def get_all_matches():
    """Return all matches, newest first."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM matches ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_match(match_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    if not row:
        conn.close()
        return None, []
    players = conn.execute(
        "SELECT * FROM player_ratings WHERE match_id = ? ORDER BY overall_rating DESC", (match_id,)
    ).fetchall()
    conn.close()
    return dict(row), [dict(p) for p in players]


def get_player_history(player_name: str):
    """Get all ratings for a player across matches."""
    conn = get_db()
    rows = conn.execute("""
        SELECT pr.*, m.team1, m.team2, m.team1_score, m.team2_score,
               m.winner, m.venue, m.created_at, m.mvp_name
        FROM player_ratings pr
        JOIN matches m ON pr.match_id = m.id
        WHERE LOWER(pr.player_name) = LOWER(?)
        ORDER BY m.id ASC
    """, (player_name,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_player_awards(player_name: str):
    """Compute awards/badges for a player based on their history."""
    conn = get_db()
    rows = conn.execute("""
        SELECT pr.*, m.mvp_name
        FROM player_ratings pr
        JOIN matches m ON pr.match_id = m.id
        WHERE LOWER(pr.player_name) = LOWER(?)
    """, (player_name,)).fetchall()
    conn.close()

    awards = []
    mvp_count = 0
    centuries = 0
    fifties = 0
    five_wkt = 0
    three_wkt = 0
    golden_ducks = 0
    high_ratings = 0  # matches with 7+ rating
    sixes_total = 0

    for r in rows:
        r = dict(r)
        if r.get("is_mvp") or (r.get("mvp_name") and r["mvp_name"].lower() == player_name.lower()):
            mvp_count += 1
        runs = r.get("runs", 0) or 0
        balls = r.get("balls", 0) or 0
        wickets = r.get("wickets", 0) or 0
        sixes = r.get("sixes", 0) or 0
        dismissal = r.get("dismissal", "")
        sixes_total += sixes

        if runs >= 100:
            centuries += 1
        elif runs >= 50:
            fifties += 1
        if wickets >= 5:
            five_wkt += 1
        elif wickets >= 3:
            three_wkt += 1
        if runs == 0 and balls > 0 and dismissal and dismissal != "not_out" and dismissal != "did_not_bat":
            golden_ducks += 1
        if r.get("overall_rating", 0) >= 7.0:
            high_ratings += 1

    if mvp_count > 0:
        awards.append({"icon": "star", "label": "MVP Awards", "count": mvp_count,
                        "color": "#ffd700", "desc": "Player of the Match"})
    if centuries > 0:
        awards.append({"icon": "hundred", "label": "Centuries", "count": centuries,
                        "color": "#1976d2", "desc": "100+ runs in an innings"})
    if fifties > 0:
        awards.append({"icon": "fifty", "label": "Half-Centuries", "count": fifties,
                        "color": "#2e7d32", "desc": "50-99 runs in an innings"})
    if five_wkt > 0:
        awards.append({"icon": "fire", "label": "5-Wicket Hauls", "count": five_wkt,
                        "color": "#c62828", "desc": "5+ wickets in a match"})
    if three_wkt > 0:
        awards.append({"icon": "wicket", "label": "3-Wicket Hauls", "count": three_wkt,
                        "color": "#ef6c00", "desc": "3-4 wickets in a match"})
    if sixes_total >= 10:
        awards.append({"icon": "six", "label": "Six Machine", "count": sixes_total,
                        "color": "#7b1fa2", "desc": "Total sixes hit"})
    total_matches = len(rows)
    if total_matches > 0 and high_ratings >= total_matches / 2:
        awards.append({"icon": "consistent", "label": "Mr. Consistent", "count": high_ratings,
                        "color": "#00897b", "desc": "7.0+ rating in more than half of matches"})
    if golden_ducks > 0:
        awards.append({"icon": "duck", "label": "Golden Ducks", "count": golden_ducks,
                        "color": "#795548", "desc": "Out for 0 runs"})

    return awards


def get_all_players():
    """Get list of all unique player names with their match count and avg rating."""
    conn = get_db()
    rows = conn.execute("""
        SELECT player_name,
               COUNT(*) as matches_played,
               ROUND(AVG(overall_rating), 1) as avg_rating,
               ROUND(AVG(batting_rating), 1) as avg_bat,
               ROUND(AVG(bowling_rating), 1) as avg_bowl,
               MAX(role) as role,
               SUM(is_mvp) as mvp_count
        FROM player_ratings
        GROUP BY LOWER(player_name)
        ORDER BY avg_rating DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_players(query: str):
    """Search players by name."""
    conn = get_db()
    rows = conn.execute("""
        SELECT player_name,
               COUNT(*) as matches_played,
               ROUND(AVG(overall_rating), 1) as avg_rating,
               MAX(role) as role,
               SUM(is_mvp) as mvp_count
        FROM player_ratings
        WHERE LOWER(player_name) LIKE LOWER(?)
        GROUP BY LOWER(player_name)
        ORDER BY avg_rating DESC
    """, (f"%{query}%",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_batsmen(limit=10):
    conn = get_db()
    rows = conn.execute("""
        SELECT player_name,
               COUNT(*) as matches,
               ROUND(AVG(batting_rating), 2) as avg_rating,
               SUM(runs) as total_runs,
               SUM(balls) as total_balls,
               SUM(fours) as total_fours,
               SUM(sixes) as total_sixes,
               MAX(overall_rating) as best_rating,
               GROUP_CONCAT(DISTINCT team) as teams
        FROM player_ratings
        WHERE did_bat = 1
        GROUP BY LOWER(player_name)
        HAVING SUM(runs) >= 125
        ORDER BY avg_rating DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    for d in result:
        total_balls = d.get("total_balls") or 0
        total_runs = d.get("total_runs") or 0
        d["strike_rate"] = round((total_runs / total_balls) * 100, 1) if total_balls > 0 else 0
    return result


def get_top_bowlers(limit=10):
    conn = get_db()
    rows = conn.execute("""
        SELECT player_name,
               COUNT(*) as matches,
               ROUND(AVG(bowling_rating), 2) as avg_rating,
               SUM(wickets) as total_wickets,
               SUM(overs_bowled) as total_overs,
               SUM(runs_conceded) as total_runs_conceded,
               MAX(overall_rating) as best_rating,
               GROUP_CONCAT(DISTINCT team) as teams
        FROM player_ratings
        WHERE did_bowl = 1
        GROUP BY LOWER(player_name)
        HAVING SUM(wickets) >= 5
        ORDER BY avg_rating DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    for d in result:
        total_wickets = d.get("total_wickets") or 0
        total_overs = d.get("total_overs") or 0
        full_overs = int(total_overs)
        part = round((total_overs - full_overs) * 10)
        total_balls_bowled = full_overs * 6 + part
        d["strike_rate"] = round(total_balls_bowled / total_wickets, 1) if total_wickets > 0 else 0
        total_runs_conceded = d.get("total_runs_conceded") or 0
        d["economy"] = round(total_runs_conceded / (total_balls_bowled / 6), 2) if total_balls_bowled > 0 else 0
    return result


def get_top_all_rounders(limit=10):
    conn = get_db()
    rows = conn.execute("""
        SELECT player_name,
               COUNT(*) as matches,
               ROUND(AVG(batting_rating), 2) as avg_bat,
               ROUND(AVG(bowling_rating), 2) as avg_bowl,
               ROUND((AVG(batting_rating) + AVG(bowling_rating)) / 2, 2) as avg_combined,
               SUM(runs) as total_runs,
               SUM(wickets) as total_wickets,
               MAX(overall_rating) as best_rating,
               GROUP_CONCAT(DISTINCT team) as teams
        FROM player_ratings
        WHERE did_bat = 1 AND did_bowl = 1
        GROUP BY LOWER(player_name)
        HAVING (SUM(runs) >= 50 AND SUM(wickets) >= 3) OR (SUM(runs) >= 75 AND SUM(wickets) >= 2)
        ORDER BY avg_combined DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_best_team_of_tournament():
    """Best team of tournament: 5 batsmen, 1 wk, 2 bat AR, 1 bowl AR, 3 bowlers."""
    conn = get_db()
    result = {}

    # 5 batsmen (role = batter, min 125 runs)
    rows = conn.execute("""
        SELECT player_name, GROUP_CONCAT(DISTINCT team) as teams,
               COUNT(*) as matches, ROUND(AVG(batting_rating), 2) as avg_rating,
               SUM(runs) as total_runs, SUM(balls) as total_balls,
               MAX(overall_rating) as best_rating
        FROM player_ratings
        WHERE role = 'batter' AND did_bat = 1
        GROUP BY LOWER(player_name)
        HAVING SUM(runs) >= 125
        ORDER BY AVG(batting_rating) DESC
        LIMIT 5
    """).fetchall()
    result["batsmen"] = [dict(r) for r in rows]

    # 1 wicket-keeper (role = wicket_keeper, min 125 runs)
    rows = conn.execute("""
        SELECT player_name, GROUP_CONCAT(DISTINCT team) as teams,
               COUNT(*) as matches, ROUND(AVG(overall_rating), 2) as avg_rating,
               SUM(runs) as total_runs, SUM(wickets) as total_wickets,
               MAX(overall_rating) as best_rating
        FROM player_ratings
        WHERE role = 'wicket_keeper' AND did_bat = 1
        GROUP BY LOWER(player_name)
        HAVING SUM(runs) >= 125
        ORDER BY AVG(overall_rating) DESC
        LIMIT 1
    """).fetchall()
    result["wicket_keeper"] = [dict(r) for r in rows]

    # 2 batting all-rounders: (50 runs & 3 wkts) OR (75 runs & 2 wkts)
    rows = conn.execute("""
        SELECT player_name, GROUP_CONCAT(DISTINCT team) as teams,
               COUNT(*) as matches,
               ROUND(AVG(batting_rating), 2) as avg_bat,
               ROUND(AVG(bowling_rating), 2) as avg_bowl,
               ROUND((AVG(batting_rating) + AVG(bowling_rating)) / 2, 2) as avg_rating,
               SUM(runs) as total_runs, SUM(wickets) as total_wickets,
               MAX(overall_rating) as best_rating
        FROM player_ratings
        WHERE role = 'batting_all_rounder' AND did_bat = 1 AND did_bowl = 1
        GROUP BY LOWER(player_name)
        HAVING (SUM(runs) >= 50 AND SUM(wickets) >= 3) OR (SUM(runs) >= 75 AND SUM(wickets) >= 2)
        ORDER BY (AVG(batting_rating) + AVG(bowling_rating)) / 2 DESC
        LIMIT 2
    """).fetchall()
    result["bat_all_rounders"] = [dict(r) for r in rows]

    # 1 bowling all-rounder: (50 runs & 3 wkts) OR (75 runs & 2 wkts)
    rows = conn.execute("""
        SELECT player_name, GROUP_CONCAT(DISTINCT team) as teams,
               COUNT(*) as matches,
               ROUND(AVG(batting_rating), 2) as avg_bat,
               ROUND(AVG(bowling_rating), 2) as avg_bowl,
               ROUND((AVG(batting_rating) + AVG(bowling_rating)) / 2, 2) as avg_rating,
               SUM(runs) as total_runs, SUM(wickets) as total_wickets,
               MAX(overall_rating) as best_rating
        FROM player_ratings
        WHERE role = 'bowling_all_rounder' AND did_bat = 1 AND did_bowl = 1
        GROUP BY LOWER(player_name)
        HAVING (SUM(runs) >= 50 AND SUM(wickets) >= 3) OR (SUM(runs) >= 75 AND SUM(wickets) >= 2)
        ORDER BY (AVG(batting_rating) + AVG(bowling_rating)) / 2 DESC
        LIMIT 1
    """).fetchall()
    result["bowl_all_rounder"] = [dict(r) for r in rows]

    # 3 bowlers (role = bowler, min 5 wickets)
    rows = conn.execute("""
        SELECT player_name, GROUP_CONCAT(DISTINCT team) as teams,
               COUNT(*) as matches, ROUND(AVG(bowling_rating), 2) as avg_rating,
               SUM(wickets) as total_wickets, SUM(overs_bowled) as total_overs,
               SUM(runs_conceded) as total_runs_conceded,
               MAX(overall_rating) as best_rating
        FROM player_ratings
        WHERE role = 'bowler' AND did_bowl = 1
        GROUP BY LOWER(player_name)
        HAVING SUM(wickets) >= 5
        ORDER BY AVG(bowling_rating) DESC
        LIMIT 3
    """).fetchall()
    result["bowlers"] = [dict(r) for r in rows]

    conn.close()
    return result


def get_player_comparison(name1: str, name2: str):
    """Get aggregated stats for two players for head-to-head comparison."""
    conn = get_db()
    result = {}
    for name in [name1, name2]:
        row = conn.execute("""
            SELECT player_name,
                   COUNT(*) as matches,
                   ROUND(AVG(overall_rating), 2) as avg_overall,
                   ROUND(AVG(batting_rating), 2) as avg_bat,
                   ROUND(AVG(bowling_rating), 2) as avg_bowl,
                   ROUND(AVG(fielding_rating), 2) as avg_field,
                   SUM(runs) as total_runs,
                   SUM(balls) as total_balls,
                   SUM(fours) as total_fours,
                   SUM(sixes) as total_sixes,
                   SUM(wickets) as total_wickets,
                   SUM(overs_bowled) as total_overs,
                   SUM(runs_conceded) as total_runs_conceded,
                   MAX(overall_rating) as best_rating,
                   SUM(is_mvp) as mvp_count,
                   SUM(did_bat) as bat_innings,
                   SUM(did_bowl) as bowl_innings,
                   MAX(role) as role
            FROM player_ratings
            WHERE LOWER(player_name) = LOWER(?)
        """, (name,)).fetchone()
        if row and row["matches"]:
            d = dict(row)
            # Compute derived stats
            total_balls = d["total_balls"] or 0
            total_runs = d["total_runs"] or 0
            total_fours = d["total_fours"] or 0
            total_sixes = d["total_sixes"] or 0
            bat_innings = d["bat_innings"] or 0
            bowl_innings = d["bowl_innings"] or 0
            total_wickets = d["total_wickets"] or 0
            total_overs = d["total_overs"] or 0
            total_runs_conceded = d["total_runs_conceded"] or 0

            d["runs_per_match"] = round(total_runs / bat_innings, 1) if bat_innings > 0 else 0
            d["strike_rate"] = round((total_runs / total_balls) * 100, 1) if total_balls > 0 else 0
            boundary_runs = (total_fours * 4 + total_sixes * 6)
            d["boundary_pct"] = round((boundary_runs / total_runs) * 100, 1) if total_runs > 0 else 0
            d["sixes_per_match"] = round(total_sixes / bat_innings, 1) if bat_innings > 0 else 0
            d["fours_per_match"] = round(total_fours / bat_innings, 1) if bat_innings > 0 else 0
            d["wickets_per_match"] = round(total_wickets / bowl_innings, 1) if bowl_innings > 0 else 0
            total_balls_bowled = int(total_overs) * 6 + round((total_overs - int(total_overs)) * 10)
            d["economy"] = round((total_runs_conceded / (total_balls_bowled / 6)), 2) if total_balls_bowled > 0 else 0
            d["bowling_avg"] = round(total_runs_conceded / total_wickets, 1) if total_wickets > 0 else 0
            d["mvp_rate"] = round((d["mvp_count"] or 0) / d["matches"] * 100, 1) if d["matches"] > 0 else 0

            # Use the actual role assigned during match input
            role = (d.get("role") or "").lower().replace(" ", "_")
            if role == "bowler":
                d["player_type"] = "bowler"
            elif role == "batter":
                d["player_type"] = "batter"
            elif role in ("all_rounder", "batting_all_rounder", "bowling_all_rounder"):
                d["player_type"] = "all_rounder"
            elif role == "wicket_keeper":
                d["player_type"] = "batter"
            else:
                # Fallback: guess from activity
                if bat_innings > 0 and bowl_innings > 0:
                    d["player_type"] = "all_rounder"
                elif bowl_innings > 0:
                    d["player_type"] = "bowler"
                else:
                    d["player_type"] = "batter"

            result[name] = d
        else:
            result[name] = None
    conn.close()
    return result


def get_player_form(player_name: str, limit=5):
    """Get last N match ratings for a player (most recent first)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT pr.overall_rating
        FROM player_ratings pr
        JOIN matches m ON pr.match_id = m.id
        WHERE LOWER(pr.player_name) = LOWER(?)
        ORDER BY m.id DESC
        LIMIT ?
    """, (player_name, limit)).fetchall()
    conn.close()
    return [r["overall_rating"] for r in rows]


def get_all_players_with_form():
    """Get all players with their last 5 form ratings."""
    conn = get_db()
    players = conn.execute("""
        SELECT player_name,
               COUNT(*) as matches_played,
               ROUND(AVG(overall_rating), 1) as avg_rating,
               ROUND(AVG(batting_rating), 1) as avg_bat,
               ROUND(AVG(bowling_rating), 1) as avg_bowl,
               MAX(role) as role,
               SUM(is_mvp) as mvp_count
        FROM player_ratings
        GROUP BY LOWER(player_name)
        ORDER BY avg_rating DESC
    """).fetchall()
    result = []
    for p in players:
        d = dict(p)
        # Get last 5 ratings for form guide
        form = conn.execute("""
            SELECT pr.overall_rating
            FROM player_ratings pr
            JOIN matches m ON pr.match_id = m.id
            WHERE LOWER(pr.player_name) = LOWER(?)
            ORDER BY m.id DESC
            LIMIT 5
        """, (d["player_name"],)).fetchall()
        d["form"] = [r["overall_rating"] for r in form]
        result.append(d)
    conn.close()
    return result


def search_players_with_form(query: str):
    """Search players by name with form guide."""
    conn = get_db()
    players = conn.execute("""
        SELECT player_name,
               COUNT(*) as matches_played,
               ROUND(AVG(overall_rating), 1) as avg_rating,
               MAX(role) as role,
               SUM(is_mvp) as mvp_count
        FROM player_ratings
        WHERE LOWER(player_name) LIKE LOWER(?)
        GROUP BY LOWER(player_name)
        ORDER BY avg_rating DESC
    """, (f"%{query}%",)).fetchall()
    result = []
    for p in players:
        d = dict(p)
        form = conn.execute("""
            SELECT pr.overall_rating
            FROM player_ratings pr
            JOIN matches m ON pr.match_id = m.id
            WHERE LOWER(pr.player_name) = LOWER(?)
            ORDER BY m.id DESC
            LIMIT 5
        """, (d["player_name"],)).fetchall()
        d["form"] = [r["overall_rating"] for r in form]
        result.append(d)
    conn.close()
    return result


def get_all_player_names():
    """Get all unique player names for autocomplete."""
    conn = get_db()
    rows = conn.execute("""
        SELECT DISTINCT player_name FROM player_ratings ORDER BY player_name
    """).fetchall()
    conn.close()
    return [r["player_name"] for r in rows]


# ───── Team Functions ─────

def get_all_teams():
    """Get all unique team names with their win/loss record and avg rating."""
    conn = get_db()
    # Teams appear in both team1 and team2 columns of matches,
    # and in the team column of player_ratings.
    rows = conn.execute("""
        SELECT team,
               COUNT(DISTINCT match_id) as matches,
               ROUND(AVG(overall_rating), 2) as avg_rating,
               ROUND(AVG(batting_rating), 2) as avg_bat,
               ROUND(AVG(bowling_rating), 2) as avg_bowl
        FROM player_ratings
        GROUP BY team
        ORDER BY avg_rating DESC
    """).fetchall()

    teams = []
    for r in rows:
        d = dict(r)
        team_name = d["team"]
        # Count wins
        wins = conn.execute("""
            SELECT COUNT(*) as c FROM matches WHERE winner = ?
        """, (team_name,)).fetchone()["c"]
        # Count total matches (team appeared as team1 or team2)
        total = conn.execute("""
            SELECT COUNT(*) as c FROM matches WHERE team1 = ? OR team2 = ?
        """, (team_name, team_name)).fetchone()["c"]
        d["wins"] = wins
        d["losses"] = total - wins
        d["total_matches"] = total
        teams.append(d)
    conn.close()
    return teams


def get_team_matches(team_name: str):
    """Get all matches for a team with the team's avg rating per match."""
    conn = get_db()

    # All matches this team played in
    matches = conn.execute("""
        SELECT * FROM matches
        WHERE team1 = ? OR team2 = ?
        ORDER BY id DESC
    """, (team_name, team_name)).fetchall()

    result = []
    for m in matches:
        m = dict(m)
        match_id = m["id"]
        opponent = m["team2"] if m["team1"] == team_name else m["team1"]
        won = m["winner"] == team_name

        # Get avg rating of this team's players in this match
        team_stats = conn.execute("""
            SELECT ROUND(AVG(overall_rating), 2) as avg_overall,
                   ROUND(AVG(batting_rating), 2) as avg_bat,
                   ROUND(AVG(bowling_rating), 2) as avg_bowl,
                   ROUND(AVG(fielding_rating), 2) as avg_field,
                   COUNT(*) as player_count,
                   SUM(runs) as total_runs,
                   SUM(wickets) as total_wickets
            FROM player_ratings
            WHERE match_id = ? AND team = ?
        """, (match_id, team_name)).fetchone()

        # Get opponent avg rating
        opp_stats = conn.execute("""
            SELECT ROUND(AVG(overall_rating), 2) as avg_overall
            FROM player_ratings
            WHERE match_id = ? AND team = ?
        """, (match_id, opponent)).fetchone()

        result.append({
            "match_id": match_id,
            "opponent": opponent,
            "won": won,
            "team_score": m["team1_score"] if m["team1"] == team_name else m["team2_score"],
            "opp_score": m["team2_score"] if m["team1"] == team_name else m["team1_score"],
            "venue": m["venue"],
            "date": m["created_at"][:10],
            "mvp_name": m["mvp_name"],
            "team_avg_overall": team_stats["avg_overall"] if team_stats else 0,
            "team_avg_bat": team_stats["avg_bat"] if team_stats else 0,
            "team_avg_bowl": team_stats["avg_bowl"] if team_stats else 0,
            "team_avg_field": team_stats["avg_field"] if team_stats else 0,
            "team_runs": team_stats["total_runs"] if team_stats else 0,
            "team_wickets": team_stats["total_wickets"] if team_stats else 0,
            "player_count": team_stats["player_count"] if team_stats else 0,
            "opp_avg_overall": opp_stats["avg_overall"] if opp_stats else 0,
        })

    conn.close()
    return result


def get_team_summary(team_name: str):
    """Get aggregate summary stats for a team across all matches."""
    conn = get_db()

    stats = conn.execute("""
        SELECT ROUND(AVG(overall_rating), 2) as avg_overall,
               ROUND(AVG(batting_rating), 2) as avg_bat,
               ROUND(AVG(bowling_rating), 2) as avg_bowl,
               ROUND(AVG(fielding_rating), 2) as avg_field,
               MAX(overall_rating) as best_player_rating
        FROM player_ratings
        WHERE team = ?
    """, (team_name,)).fetchone()

    total_matches = conn.execute("""
        SELECT COUNT(*) as c FROM matches WHERE team1 = ? OR team2 = ?
    """, (team_name, team_name)).fetchone()["c"]

    wins = conn.execute("""
        SELECT COUNT(*) as c FROM matches WHERE winner = ?
    """, (team_name,)).fetchone()["c"]

    conn.close()

    if not stats or not stats["avg_overall"]:
        return None

    return {
        "avg_overall": stats["avg_overall"],
        "avg_bat": stats["avg_bat"],
        "avg_bowl": stats["avg_bowl"],
        "avg_field": stats["avg_field"],
        "best_player_rating": stats["best_player_rating"],
        "total_matches": total_matches,
        "wins": wins,
        "losses": total_matches - wins,
        "win_pct": round(wins / total_matches * 100, 1) if total_matches > 0 else 0,
    }


# Initialize DB on import
init_db()
