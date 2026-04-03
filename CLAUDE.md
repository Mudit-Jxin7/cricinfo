# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CricScore is a Flask-based web application that generates SoFaScore-style player ratings (0-10 scale) for T20 cricket matches. The rating system is context-aware, analyzing match situations, impact, and player roles rather than relying solely on raw statistics.

## Development Commands

**Setup:**
```bash
# Create virtual environment (if not exists)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Running the app:**
```bash
python app.py
# App runs on http://localhost:5050
# Database (cricscore.db) is created automatically on first run
```

**Database:**
- SQLite database at `cricscore.db` in project root
- Schema is auto-initialized on import via `database.init_db()`
- Uses `sqlite3.Row` for dict-like access to query results
- Foreign keys enabled with `PRAGMA foreign_keys = ON`

## Architecture

### High-Level Structure

```
app.py                      # Flask routes and request handlers
database.py                 # SQLite queries and database initialization
rating_engine/              # Modular rating calculation system
  ├── calculator.py         # Main rating orchestrator
  ├── models.py             # Data classes (Match, Innings, PlayerRating, etc.)
  ├── context.py            # Match context analysis for relative adjustments
  ├── batting.py            # Batting rating calculation
  ├── bowling.py            # Bowling rating calculation
  └── fielding.py           # Fielding rating calculation
templates/                  # Jinja2 HTML templates
static/                     # CSS, JS, images (if any)
```

### Rating Engine Flow

1. **Input**: `Match` object with two `Innings` (each containing `BattingEntry`, `BowlingEntry`, `FieldingEvent`)
2. **Context Analysis** (`context.py`): Calculates match-level statistics:
   - Match economy (average runs per over across both innings)
   - Required run rate for chase
   - Context factors for relative adjustments (e.g., economy of 8 in a 220-run game vs 140-run game)
3. **Component Ratings** (batting/bowling/fielding modules):
   - Each module calculates a 0-10 rating with detailed breakdown
   - Ratings start from a base (5.0 for batting, 5.4 for bowling) and adjust up/down
   - Context-aware: strike rate and economy judged relative to match conditions
4. **Aggregation** (`calculator.py`):
   - Combines component ratings using role-based weights
   - Weight redistribution for edge cases (e.g., bowler who faces <6 balls)
   - Returns `PlayerRating` objects with overall + component ratings

### Role-Based Weights (calculator.py)

| Role | Batting | Bowling | Fielding |
|------|---------|---------|----------|
| Batter | 80% | 5% | 15% |
| Bowler | 5% | 80% | 15% |
| Batting All-Rounder | 55% | 30% | 15% |
| Bowling All-Rounder | 30% | 55% | 15% |
| Wicket-Keeper | 75% | 0% | 25% |

**Special weight adjustments:**
- Bowler who faces <6 balls: batting weight → 0, redistributed to bowling + fielding
- Batter who bowls ≥6 balls: 75% batting, 15% bowling, 10% fielding
- Bowler who bats ≥6 balls: 20% batting, 65% bowling, 15% fielding (bowling stays primary)
- All-rounders: weights unchanged regardless of activity

### Context-Aware Adjustments

The rating engine makes **relative** rather than **absolute** judgments:
- **Economy**: An economy of 8 in a high-scoring match (match economy 11) is excellent; in a low-scoring match (match economy 6.5) it's poor
- **Strike Rate**: Judged relative to match SR, not fixed thresholds
- **Chase Pressure**: Batsmen facing high required run rates get adjusted ratings based on performance under pressure
- **Wicket Quality**: Dismissing a set batsman who scored 50+ is valued more than an early wicket

Key functions in `context.py`:
- `analyze_match_context(match)`: Returns `MatchContext` with match-level stats
- `get_economy_context_adjustment(economy, ctx)`: Returns adjustment for bowling economy relative to match
- `get_strike_rate_context_adjustment(sr, ctx)`: Returns adjustment for batting SR relative to match
- `get_chase_pressure_factor(entry, ctx, innings_total, innings_wickets)`: Chase pressure multiplier

### Database Schema

**Tables:**
- `events`: Tournament/event names (e.g., "IPL 2024", "World Cup 2026")
- `matches`: Match-level info (teams, scores, winner, venue, MVP, event_id)
- `player_ratings`: Per-player-per-match ratings and stats (denormalized for query performance)

**Key patterns:**
- Event filtering: Many queries accept optional `event_id` parameter
- Player names: Case-insensitive queries via `LOWER(player_name)`
- Aggregations: Use `GROUP BY LOWER(player_name)` to consolidate across matches
- Leaderboards: Minimum qualification thresholds (e.g., 150 runs for batsmen, 7 wickets for bowlers)

### Data Flow (Match Input → Saved Match)

1. User submits form data via `/calculate` (POST with JSON)
2. `_parse_match_data()` converts JSON to `Match` object
3. `calculate_match_ratings()` processes and returns ratings
4. Frontend displays ratings; user clicks "Save Match"
5. `/save_match` stores to database:
   - Insert into `matches` table (determines MVP from highest overall rating)
   - Insert each player into `player_ratings` with component ratings and stats

## Important Domain Logic

### Minimum Ball Thresholds

- **Batting evaluation**: Strike rate and boundary % only evaluated if player faces ≥4 balls
- **Duck penalties**: Only apply to batsmen (not bowlers) who face ≥6 balls
- **Weight redistribution**: Bowler who faces <6 balls gets batting weight set to 0

### Anchor Score (Batting)

Position-aware thresholds for rewarding set innings:
- Openers (positions 1-2): 30+ balls
- Middle order (positions 3-5): 20-25 balls
- Lower order (positions 6+): 15+ balls

### Wicket Value (Bowling)

- Base: 1.25 points per wicket (linear scaling)
- Quality bonus: Dismissing batsmen who scored 30+ runs adds extra points
- Wicket quality is tracked via `dismissed_batsmen_runs` list in `BowlingEntry`

### MVP Selection

- Highest overall rating wins
- Tiebreaker: Higher bowling rating, then higher batting rating
- If winner specified, prioritize winning team's players in ties

### Leaderboard Qualifications

**Per Event:**
- Batsmen: ≥150 runs, ≥4 matches
- Bowlers: ≥7 wickets, ≥4 matches
- All-rounders: (≥50 runs + ≥3 wickets) OR (≥75 runs + ≥2 wickets), ≥4 matches

**IPL All Seasons (across all events with name starting "IPL"):**
- Batsmen: ≥300 runs
- Bowlers: ≥10 wickets
- All-rounders: (≥150 runs + ≥4 wickets) OR (≥100 runs + ≥5 wickets)

### Best Team Selection

**Default (5-1-2-1-3):**
- 5 batsmen (role='batter'), 1 wicket-keeper, 2 batting all-rounders, 1 bowling all-rounder, 3 bowlers

**IPL 2024/2025 (6-1-2-4):**
- 6 batsmen, 1 wicket-keeper, 2 best all-rounders (any type), 4 bowlers

Selection criteria: Average rating in that skill (batting for batsmen, bowling for bowlers, combined avg for all-rounders)

## Common Patterns

### Adding a New Route

```python
@app.route("/your-route")
def your_view():
    # Query database via db.* functions
    data = db.get_something()
    # Render template
    return render_template("your_template.html", data=data)
```

### Database Queries

- Use `get_db()` to get connection
- Always `conn.close()` when done
- Use parameterized queries to prevent SQL injection: `conn.execute(sql, (param1, param2))`
- Return `dict(row)` or `[dict(r) for r in rows]` for dict results

### Modifying Rating Logic

- **Batting**: Edit `rating_engine/batting.py` → `calculate_batting_rating()`
- **Bowling**: Edit `rating_engine/bowling.py` → `calculate_bowling_rating()`
- **Fielding**: Edit `rating_engine/fielding.py` → `calculate_fielding_rating()`
- **Weights**: Edit `ROLE_WEIGHTS` in `rating_engine/calculator.py`
- **Context factors**: Edit `rating_engine/context.py` adjustment functions

### Testing Rating Changes

```bash
# Run app
python app.py

# Navigate to http://localhost:5050
# Fill in match data on index page
# Click "Calculate Ratings" to see results
# Optionally save to database to test persistence
```

## Database Migrations

The database uses manual migrations in `database.init_db()`:
- Tables created with `CREATE TABLE IF NOT EXISTS`
- Columns added with `ALTER TABLE ... ADD COLUMN` wrapped in try/except (ignores if column exists)
- Default event "World Cup 2026" created if events table is empty

When adding new columns:
1. Add column to CREATE TABLE statement
2. Add migration `ALTER TABLE` in try/except block below table creation
3. Update relevant queries to use new column

## IPL-Specific Logic

- Event name matching: Case-insensitive, trimmed, checks `LIKE 'ipl%'`
- IPL 2024/2025 events use special best team composition (6-1-2-4)
- "IPL All Seasons" routes aggregate across all events with name starting "IPL"
- Default event on homepage: "IPL 2024" if exists, else first event

## Template Patterns

- All templates extend `base.html`
- Rating colors: Use `_rating_color(rating)` Jinja global (defined in `app.py`)
- Forms: POST to `/calculate` for rating calculation, `/save_match` to persist
- Event selector: Dropdown in leaderboard, best team, match history, player detail pages
