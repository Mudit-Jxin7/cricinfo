# CricScore - Context-Aware T20 Cricket Player Ratings

A SoFaScore-inspired player rating system (0-10) for T20 cricket matches. Unlike simple stat-based ratings, CricScore analyzes **context, impact, and match situation** to generate meaningful player ratings.

## Key Features

- **Context-aware ratings**: Economy is judged relative to the match, not absolute numbers. An economy of 8 in a 220-run game is treated differently from 8 in a 140-run game.
- **Impact-based**: A finisher who hits 25*(10) to win gets rewarded more than raw stats suggest. Chase pressure, required run rate, and match result are all factored in.
- **Wicket quality**: Dismissing a set batsman who scored 50 is valued more than an early cheap wicket.
- **Role-aware weighting**: Batters, bowlers, all-rounders, and wicket-keepers have different component weights.
- **SoFaScore-style UI**: Color-coded rating circles with expandable breakdowns showing exactly how each rating was calculated.

## Rating Scale

| Rating | Color | Meaning |
|--------|-------|---------|
| 9.0 - 10.0 | Blue | Exceptional / MOTM-level |
| 7.5 - 8.9 | Green | Great performance |
| 6.5 - 7.4 | Light Green | Good, above average |
| 5.5 - 6.4 | Yellow | Average |
| 4.5 - 5.4 | Orange | Below average |
| 0.0 - 4.4 | Red | Poor |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app (database will be created automatically)
python app.py
```

Open http://localhost:5050 in your browser.

The SQLite database (`cricscore.db`) will be created automatically on first run.

## How It Works

1. Enter the match scorecard data for both innings (batting, bowling, fielding events)
2. Click "Calculate Ratings"
3. View color-coded player ratings with detailed breakdowns

### Rating Algorithm

Each player gets three component ratings:

- **Batting**: Runs, strike rate (relative to match), boundary %, anchoring, batting position, chase pressure, duck penalties, match result
  - Strike rate and boundary % only evaluated if player faces at least 4 balls (but still rewarded if excellent)
  - Anchor score is position-aware: openers need 30+ balls, middle order needs 20-25 balls, lower order needs 15+ balls
  - Duck penalties only apply to batsmen (not bowlers) who face at least 6 balls
- **Bowling**: Wickets (1.25+ points per wicket), economy (relative to match), maidens, overs bowled, wicket quality, extras, match result
  - Each wicket gives at least 1.25 points (linear scaling: 1 wicket = 1.25, 2 wickets = 2.50, etc.)
- **Fielding**: Catches (+1.0), direct run outs (+1.5), stumpings (+1.0), dropped catches (-1.5), misfields (-0.5)

These are combined using role-based weights:

| Role | Batting | Bowling | Fielding |
|------|---------|---------|----------|
| Batter | 80% | 5% | 15% |
| Bowler | 5% | 80% | 15% |
| Batting All-Rounder | 55% | 30% | 15% |
| Bowling All-Rounder | 30% | 55% | 15% |
| Wicket-Keeper | 75% | 0% | 25% |

**Special Cases:**
- **Bowlers who face < 6 balls**: Batting weight set to 0, redistributed to bowling and fielding
- **All-rounders**: Keep their role-based weights (no redistribution even if they bat/bowl significantly)
- **Cross-over weights**: If a batter bowls ≥6 balls, weights are 75% batting, 15% bowling, 10% fielding. If a bowler bats ≥6 balls, bowling stays primary: 20% batting, 65% bowling, 15% fielding (so a bowler’s overall rating stays bowling-driven).
- **Did not bat / did not bowl**: Overall is always a weighted average of the components that apply (e.g. if a player didn’t bowl, overall = weighted average of batting + fielding only), never a single component alone.

**MVP Selection:**
- Highest overall rating wins
- Tiebreaker: Higher bowling rating, then higher batting rating

## Features

- **Match Management**: Save matches to database, view match history, player statistics
- **Player Profiles**: Track individual player performance over time with form graphs, **batting average** and **strike rate** for batters, **bowling average**, **bowling strike rate**, and **economy** for bowlers
- **Team Statistics**: View team performance, win/loss records, and team comparisons; **sort teams** by overall, batting, or bowling rating
- **Leaderboards**: Top 10 by batting (min. 75 runs), bowling (min. 3 wickets), and all-round (min. 75 runs and 3 wickets); batsmen table shows **strike rate**, bowlers show **SR** (balls per wicket) and **economy**
- **Player Comparison**: Head-to-head comparison between any two players
- **Default Settings**: Dismissal type defaults to "caught" for faster data entry

## Tech Stack

- Python 3.10+ / Flask
- SQLite database for match and player data persistence
- Vanilla HTML, CSS, JavaScript
- Chart.js for performance visualizations
