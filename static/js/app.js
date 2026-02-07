/**
 * CricScore - Dynamic form handling and results rendering.
 */

// ===== Constants =====
const DISMISSAL_OPTIONS = [
    { value: 'not_out', label: 'Not Out' },
    { value: 'bowled', label: 'Bowled' },
    { value: 'caught', label: 'Caught' },
    { value: 'lbw', label: 'LBW' },
    { value: 'run_out', label: 'Run Out' },
    { value: 'stumped', label: 'Stumped' },
    { value: 'hit_wicket', label: 'Hit Wicket' },
    { value: 'retired_hurt', label: 'Retired Hurt' },
    { value: 'did_not_bat', label: 'Did Not Bat' },
];

const ROLE_OPTIONS = [
    { value: 'batter', label: 'Batter' },
    { value: 'bowler', label: 'Bowler' },
    { value: 'batting_all_rounder', label: 'Bat AR' },
    { value: 'bowling_all_rounder', label: 'Bowl AR' },
    { value: 'wicket_keeper', label: 'WK' },
];

const FIELDING_EVENT_OPTIONS = [
    { value: 'catch', label: 'Catch' },
    { value: 'direct_run_out', label: 'Direct Run Out' },
    { value: 'assisted_run_out', label: 'Assisted Run Out' },
    { value: 'stumping', label: 'Stumping' },
    { value: 'dropped_catch', label: 'Dropped Catch' },
    { value: 'misfield', label: 'Misfield' },
];

const ROLE_LABELS = {
    'batter': 'Batter',
    'bowler': 'Bowler',
    'batting_all_rounder': 'Batting All-Rounder',
    'bowling_all_rounder': 'Bowling All-Rounder',
    'wicket_keeper': 'Wicket-Keeper',
};

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
    // Add initial rows
    for (let i = 0; i < 6; i++) addBattingRow('fi_batting_table');
    for (let i = 0; i < 6; i++) addBattingRow('si_batting_table');
    for (let i = 0; i < 4; i++) addBowlingRow('fi_bowling_table');
    for (let i = 0; i < 4; i++) addBowlingRow('si_bowling_table');

    // Team name listeners
    const team1Input = document.getElementById('team1_name');
    const team2Input = document.getElementById('team2_name');
    team1Input.addEventListener('input', updateTeamLabels);
    team2Input.addEventListener('input', updateTeamLabels);

    // Form submit
    document.getElementById('matchForm').addEventListener('submit', handleSubmit);
});

function updateTeamLabels() {
    const t1 = document.getElementById('team1_name').value || 'Team 1';
    const t2 = document.getElementById('team2_name').value || 'Team 2';

    document.getElementById('innings1_team_label').textContent = t1;
    document.getElementById('innings2_team_label').textContent = t2;
    document.getElementById('fi_bowling_hint').textContent = `(${t2} bowlers)`;
    document.getElementById('fi_fielding_hint').textContent = `(${t2} fielders)`;
    document.getElementById('si_bowling_hint').textContent = `(${t1} bowlers)`;
    document.getElementById('si_fielding_hint').textContent = `(${t1} fielders)`;

    // Update winner dropdown
    const winnerSelect = document.getElementById('winner');
    const currentVal = winnerSelect.value;
    winnerSelect.innerHTML = `
        <option value="">-- Select --</option>
        <option value="${t1}" ${currentVal === t1 ? 'selected' : ''}>${t1}</option>
        <option value="${t2}" ${currentVal === t2 ? 'selected' : ''}>${t2}</option>
        <option value="tie">Tie</option>
    `;
}

// ===== Row Builders =====
function createSelectHTML(options, name, defaultVal) {
    let html = '';
    for (const opt of options) {
        const selected = opt.value === defaultVal ? ' selected' : '';
        html += `<option value="${opt.value}"${selected}>${opt.label}</option>`;
    }
    return `<select name="${name}">${html}</select>`;
}

function addBattingRow(tableId) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    const rowNum = tbody.rows.length + 1;

    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td>${rowNum}</td>
        <td><input type="text" class="name-input" placeholder="Player name"></td>
        <td>${createSelectHTML(ROLE_OPTIONS, 'role', 'batter')}</td>
        <td><input type="number" min="0" value="0"></td>
        <td><input type="number" min="0" value="0"></td>
        <td><input type="number" min="0" value="0"></td>
        <td><input type="number" min="0" value="0"></td>
        <td>${createSelectHTML(DISMISSAL_OPTIONS, 'dismissal', 'not_out')}</td>
        <td><button type="button" class="btn btn-remove" onclick="removeRow(this)" title="Remove">&times;</button></td>
    `;
    tbody.appendChild(tr);
    renumberRows(tableId);
}

function addBowlingRow(tableId) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="name-input" placeholder="Bowler name"></td>
        <td>${createSelectHTML(ROLE_OPTIONS, 'role', 'bowler')}</td>
        <td><input type="number" min="0" step="0.1" value="0"></td>
        <td><input type="number" min="0" value="0"></td>
        <td><input type="number" min="0" value="0"></td>
        <td><input type="number" min="0" value="0"></td>
        <td><input type="number" min="0" value="0"></td>
        <td><input type="number" min="0" value="0"></td>
        <td><input type="text" class="dismissed-runs-input" placeholder="e.g. 12,45"></td>
        <td><button type="button" class="btn btn-remove" onclick="removeRow(this)" title="Remove">&times;</button></td>
    `;
    tbody.appendChild(tr);
}

function addFieldingRow(tableId) {
    const tbody = document.querySelector(`#${tableId} tbody`);
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td><input type="text" class="name-input" placeholder="Fielder name"></td>
        <td>${createSelectHTML(FIELDING_EVENT_OPTIONS, 'event_type', 'catch')}</td>
        <td><button type="button" class="btn btn-remove" onclick="removeRow(this)" title="Remove">&times;</button></td>
    `;
    tbody.appendChild(tr);
}

function removeRow(btn) {
    const tr = btn.closest('tr');
    const table = tr.closest('table');
    tr.remove();
    renumberRows(table.id);
}

function renumberRows(tableId) {
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);
    rows.forEach((row, i) => {
        const firstCell = row.cells[0];
        if (firstCell && !firstCell.querySelector('input')) {
            firstCell.textContent = i + 1;
        }
    });
}

// ===== Form Data Collection =====
function collectBatting(tableId) {
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);
    const entries = [];
    rows.forEach(row => {
        const cells = row.cells;
        const name = cells[1].querySelector('input').value.trim();
        if (!name) return;
        entries.push({
            name: name,
            role: cells[2].querySelector('select').value,
            runs: parseInt(cells[3].querySelector('input').value) || 0,
            balls: parseInt(cells[4].querySelector('input').value) || 0,
            fours: parseInt(cells[5].querySelector('input').value) || 0,
            sixes: parseInt(cells[6].querySelector('input').value) || 0,
            dismissal: cells[7].querySelector('select').value,
        });
    });
    return entries;
}

function collectBowling(tableId) {
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);
    const entries = [];
    rows.forEach(row => {
        const cells = row.cells;
        const name = cells[0].querySelector('input').value.trim();
        if (!name) return;
        entries.push({
            name: name,
            role: cells[1].querySelector('select').value,
            overs: parseFloat(cells[2].querySelector('input').value) || 0,
            maidens: parseInt(cells[3].querySelector('input').value) || 0,
            runs_conceded: parseInt(cells[4].querySelector('input').value) || 0,
            wickets: parseInt(cells[5].querySelector('input').value) || 0,
            wides: parseInt(cells[6].querySelector('input').value) || 0,
            no_balls: parseInt(cells[7].querySelector('input').value) || 0,
            dismissed_batsmen_runs: cells[8].querySelector('input').value.trim(),
        });
    });
    return entries;
}

function collectFielding(tableId) {
    const rows = document.querySelectorAll(`#${tableId} tbody tr`);
    const entries = [];
    rows.forEach(row => {
        const cells = row.cells;
        const name = cells[0].querySelector('input').value.trim();
        if (!name) return;
        entries.push({
            player_name: name,
            event_type: cells[1].querySelector('select').value,
        });
    });
    return entries;
}

// ===== Submit Handler =====
async function handleSubmit(e) {
    e.preventDefault();

    const data = {
        team1_name: document.getElementById('team1_name').value.trim() || 'Team 1',
        team2_name: document.getElementById('team2_name').value.trim() || 'Team 2',
        winner: document.getElementById('winner').value,
        venue: document.getElementById('venue').value.trim(),
        first_innings: {
            total_runs: parseInt(document.querySelector('[name="fi_total_runs"]').value) || 0,
            total_wickets: parseInt(document.querySelector('[name="fi_total_wickets"]').value) || 0,
            total_overs: parseFloat(document.querySelector('[name="fi_total_overs"]').value) || 20,
            batting: collectBatting('fi_batting_table'),
            bowling: collectBowling('fi_bowling_table'),
            fielding_events: collectFielding('fi_fielding_table'),
        },
        second_innings: {
            total_runs: parseInt(document.querySelector('[name="si_total_runs"]').value) || 0,
            total_wickets: parseInt(document.querySelector('[name="si_total_wickets"]').value) || 0,
            total_overs: parseFloat(document.querySelector('[name="si_total_overs"]').value) || 20,
            batting: collectBatting('si_batting_table'),
            bowling: collectBowling('si_bowling_table'),
            fielding_events: collectFielding('si_fielding_table'),
        },
    };

    // Show loading
    showLoading(true);

    try {
        const resp = await fetch('/calculate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        const result = await resp.json();

        if (!result.success) {
            showError(result.error || 'Failed to calculate ratings.');
            return;
        }

        // Store raw form data and result for saving later
        window._lastResult = result;
        window._lastFormData = data;
        renderResults(result, data.winner);
    } catch (err) {
        showError('Network error: ' + err.message);
    } finally {
        showLoading(false);
    }
}

// ===== Loading & Error =====
function showLoading(show) {
    let overlay = document.querySelector('.loading-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.innerHTML = '<div class="spinner"></div>';
        document.body.appendChild(overlay);
    }
    overlay.classList.toggle('active', show);
}

function showError(msg) {
    const section = document.getElementById('resultsSection');
    section.style.display = 'block';
    section.innerHTML = `<div class="error-message">${msg}</div>`;
    section.scrollIntoView({ behavior: 'smooth' });
}

// ===== Results Rendering =====
function renderResults(result, winnerName) {
    const section = document.getElementById('resultsSection');
    section.style.display = 'block';

    const t1 = result.team1;
    const t2 = result.team2;
    const mi = result.match_info;

    const t1Winner = winnerName === t1.name;
    const t2Winner = winnerName === t2.name;

    // Find MVP (highest overall rating across both teams)
    const allPlayers = [...t1.players, ...t2.players];
    let mvp = null;
    for (const p of allPlayers) {
        if (!mvp || p.overall_rating > mvp.overall_rating) mvp = p;
    }

    let html = `
        <div class="results-header">
            <h2>Match Ratings</h2>
            <div class="match-score-summary">
                <div class="team-score-card ${t1Winner ? 'winner' : ''}">
                    <div class="team-name">${escHTML(t1.name)}</div>
                    <div class="team-score">${escHTML(mi.team1_score)}</div>
                </div>
                <div class="score-vs">vs</div>
                <div class="team-score-card ${t2Winner ? 'winner' : ''}">
                    <div class="team-name">${escHTML(t2.name)}</div>
                    <div class="team-score">${escHTML(mi.team2_score)}</div>
                </div>
            </div>
        </div>
    `;

    if (mvp) {
        html += `
            <div class="mvp-banner">
                <span class="mvp-star">&#9733;</span>
                <span class="mvp-text">Player of the Match</span>
                <span class="mvp-name">${escHTML(mvp.name)}</span>
                <span class="mvp-rating">${mvp.overall_rating.toFixed(1)}</span>
            </div>
        `;
    }

    html += renderTeamRatings(t1, t1Winner, mvp ? mvp.name : '');
    html += renderTeamRatings(t2, t2Winner, mvp ? mvp.name : '');

    html += `
        <div class="results-actions">
            <button class="btn btn-secondary" onclick="window.scrollTo({top:0,behavior:'smooth'})">Back to Top</button>
            <button class="btn btn-save" id="saveMatchBtn" onclick="saveMatch()">Save Match</button>
            <button class="btn btn-primary" onclick="location.reload()">New Match</button>
        </div>
        <div class="save-status" id="saveStatus"></div>
    `;

    section.innerHTML = html;
    section.scrollIntoView({ behavior: 'smooth' });
}

function renderTeamRatings(team, isWinner, mvpName) {
    let html = `
        <div class="team-ratings">
            <div class="team-ratings-header">
                <h3>${escHTML(team.name)}</h3>
                ${isWinner ? '<span class="winner-badge">Winner</span>' : ''}
            </div>
            <div class="player-cards">
    `;

    for (const p of team.players) {
        const cardId = `card_${p.name.replace(/\s+/g, '_')}_${team.name.replace(/\s+/g, '_')}`;
        const isMVP = mvpName && p.name === mvpName;
        html += `
            <div class="player-card ${isMVP ? 'mvp-card' : ''}" onclick="toggleBreakdown('${cardId}')">
                ${isMVP ? '<div class="mvp-card-badge">MVP</div>' : ''}
                <div class="rating-circle ${p.rating_color}">
                    ${p.overall_rating.toFixed(1)}
                </div>
                <div class="player-info">
                    <div class="player-name">${escHTML(p.name)}</div>
                    <div class="player-role">${ROLE_LABELS[p.role] || p.role}</div>
                </div>
                <div class="component-ratings">
                    ${p.did_bat ? `
                    <div class="component-rating">
                        <div class="component-label">BAT</div>
                        <div class="component-value">${p.batting_rating.toFixed(1)}</div>
                    </div>` : ''}
                    ${p.did_bowl ? `
                    <div class="component-rating">
                        <div class="component-label">BOWL</div>
                        <div class="component-value">${p.bowling_rating.toFixed(1)}</div>
                    </div>` : ''}
                    <div class="component-rating">
                        <div class="component-label">FIELD</div>
                        <div class="component-value">${p.fielding_rating.toFixed(1)}</div>
                    </div>
                </div>
            </div>
            <div class="rating-breakdown" id="${cardId}">
                ${renderBreakdown(p)}
            </div>
        `;
    }

    html += '</div></div>';
    return html;
}

function renderBreakdown(player) {
    let html = '<div class="breakdown-grid">';

    // Batting breakdown
    if (player.did_bat && player.batting_details && !player.batting_details.note) {
        html += '<div class="breakdown-section"><h4>Batting</h4>';
        const bd = player.batting_details;
        if (bd.runs) html += breakdownRow('Runs', bd.runs.value, bd.runs.score);
        if (bd.strike_rate) html += breakdownRow('Strike Rate', bd.strike_rate.value, bd.strike_rate.score);
        if (bd.boundary_pct) html += breakdownRow('Boundary %', bd.boundary_pct.value + '%', bd.boundary_pct.score);
        if (bd.anchor) html += breakdownRow('Anchor', bd.anchor.balls_faced + ' balls', bd.anchor.score);
        if (bd.position) html += breakdownRow('Position', '#' + bd.position.position, bd.position.score);
        if (bd.not_out_chase) html += breakdownRow('Not Out Chase', '', bd.not_out_chase.score);
        if (bd.match_result) html += breakdownRow('Match Result', bd.match_result.won ? 'Won' : 'Lost', bd.match_result.score);
        if (bd.chase_pressure) html += breakdownRow('Chase Pressure', 'RRR ' + bd.chase_pressure.rrr, bd.chase_pressure.score);
        if (bd.cameo_impact && bd.cameo_impact.score !== 0) html += breakdownRow('Cameo Impact', '', bd.cameo_impact.score);
        if (bd.duck && bd.duck.score !== 0) html += breakdownRow('Duck', '', bd.duck.score);
        html += '</div>';
    }

    // Bowling breakdown
    if (player.did_bowl && player.bowling_details && !player.bowling_details.note) {
        html += '<div class="breakdown-section"><h4>Bowling</h4>';
        const bw = player.bowling_details;
        if (bw.wickets) html += breakdownRow('Wickets', bw.wickets.value, bw.wickets.score);
        if (bw.economy) html += breakdownRow('Economy', bw.economy.value + ' (match: ' + bw.economy.match_economy + ')', bw.economy.score);
        if (bw.maidens) html += breakdownRow('Maidens', bw.maidens.value, bw.maidens.score);
        if (bw.overs_bowled) html += breakdownRow('Overs', bw.overs_bowled.value, bw.overs_bowled.score);
        if (bw.wicket_quality) html += breakdownRow('Wicket Quality', '', bw.wicket_quality.score);
        if (bw.match_result) html += breakdownRow('Match Result', bw.match_result.won ? 'Won' : 'Lost', bw.match_result.score);
        if (bw.extras && bw.extras.score !== 0) html += breakdownRow('Extras', bw.extras.wides + 'wd ' + bw.extras.no_balls + 'nb', bw.extras.score);
        html += '</div>';
    }

    // Fielding breakdown
    if (player.fielding_details && player.fielding_details.has_events) {
        html += '<div class="breakdown-section"><h4>Fielding</h4>';
        const fd = player.fielding_details;
        if (fd.events) {
            for (const ev of fd.events) {
                html += breakdownRow(ev.type.replace(/_/g, ' '), '', ev.points);
            }
        }
        html += '</div>';
    }

    html += '</div>';
    return html;
}

function breakdownRow(label, value, score) {
    const scoreNum = parseFloat(score);
    let cls = 'neutral';
    if (scoreNum > 0) cls = 'positive';
    else if (scoreNum < 0) cls = 'negative';

    const sign = scoreNum > 0 ? '+' : '';
    const valueStr = value ? `${value} ` : '';

    return `
        <div class="breakdown-item">
            <span class="label">${label} ${valueStr}</span>
            <span class="value ${cls}">${sign}${scoreNum.toFixed(2)}</span>
        </div>
    `;
}

function toggleBreakdown(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.toggle('expanded');
    }
}

function escHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ===== Save Match to DB =====
async function saveMatch() {
    const btn = document.getElementById('saveMatchBtn');
    const statusEl = document.getElementById('saveStatus');

    if (!window._lastResult || !window._lastFormData) {
        statusEl.className = 'save-status error';
        statusEl.textContent = 'No match data to save.';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
        const payload = {
            match_info: {
                team1_name: window._lastResult.match_info.team1_name || window._lastResult.team1.name,
                team2_name: window._lastResult.match_info.team2_name || window._lastResult.team2.name,
                team1_score: window._lastResult.match_info.team1_score,
                team2_score: window._lastResult.match_info.team2_score,
                winner: window._lastResult.match_info.winner || '',
                venue: window._lastResult.match_info.venue || '',
            },
            team1: window._lastResult.team1,
            team2: window._lastResult.team2,
            raw_form: window._lastFormData,
        };

        const resp = await fetch('/save_match', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const result = await resp.json();

        if (result.success) {
            statusEl.className = 'save-status success';
            statusEl.textContent = 'Match saved! View it in Matches.';
            btn.textContent = 'Saved';
        } else {
            throw new Error(result.error || 'Failed to save');
        }
    } catch (err) {
        statusEl.className = 'save-status error';
        statusEl.textContent = 'Error: ' + err.message;
        btn.disabled = false;
        btn.textContent = 'Save Match';
    }
}

