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

# Run the app
python app.py
```

Open http://localhost:5050 in your browser.

## How It Works

1. Enter the match scorecard data for both innings (batting, bowling, fielding events)
2. Click "Calculate Ratings"
3. View color-coded player ratings with detailed breakdowns

### Rating Algorithm

Each player gets three component ratings:

- **Batting**: Runs, strike rate (relative to match), boundary %, anchoring, batting position, chase pressure, duck penalties, match result
- **Bowling**: Wickets, economy (relative to match), dot ball %, maidens, overs bowled, wicket quality, extras, match result
- **Fielding**: Catches (+1.0), direct run outs (+1.5), stumpings (+1.0), dropped catches (-1.5), misfields (-0.5)

These are combined using role-based weights:

| Role | Batting | Bowling | Fielding |
|------|---------|---------|----------|
| Batter | 80% | 5% | 15% |
| Bowler | 15% | 70% | 15% |
| All-Rounder | 45% | 40% | 15% |
| Wicket-Keeper | 65% | 5% | 30% |

## Tech Stack

- Python 3.10+ / Flask
- Vanilla HTML, CSS, JavaScript
- No database required (stateless computation)
