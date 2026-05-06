#!/usr/bin/env python3
"""
Парсер для НБА с фиксированным расписанием плей-офф
Правильное московское время
"""

import json
import os
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# ТОЧНОЕ РАСПИСАНИЕ ПЛЕЙ-ОФФ НА 6-14 МАЯ 2026 (МОСКОВСКОЕ ВРЕМЯ)
# ============================================================

SCHEDULE = [
    # 6 мая
    {'date': '06.05.2026', 'time': '00:00 МСК', 'home': 'Detroit Pistons', 'away': 'Cleveland Cavaliers', 'series': 'Game 1'},
    {'date': '06.05.2026', 'time': '01:30 МСК', 'home': 'Oklahoma City Thunder', 'away': 'Los Angeles Lakers', 'series': 'Game 1'},
    # 7 мая
    {'date': '07.05.2026', 'time': '00:00 МСК', 'home': 'New York Knicks', 'away': 'Philadelphia 76ers', 'series': 'Game 1'},
    {'date': '07.05.2026', 'time': '01:30 МСК', 'home': 'San Antonio Spurs', 'away': 'Minnesota Timberwolves', 'series': 'Game 1'},
    # 8 мая
    {'date': '08.05.2026', 'time': '01:30 МСК', 'home': 'Los Angeles Lakers', 'away': 'Oklahoma City Thunder', 'series': 'Game 2'},
    # 9 мая
    {'date': '09.05.2026', 'time': '00:00 МСК', 'home': 'Cleveland Cavaliers', 'away': 'Detroit Pistons', 'series': 'Game 2'},
    {'date': '09.05.2026', 'time': '21:30 МСК', 'home': 'Philadelphia 76ers', 'away': 'New York Knicks', 'series': 'Game 2'},
    # 10 мая
    {'date': '10.05.2026', 'time': '01:30 МСК', 'home': 'Minnesota Timberwolves', 'away': 'San Antonio Spurs', 'series': 'Game 2'},
    # 11 мая
    {'date': '11.05.2026', 'time': '00:00 МСК', 'home': 'Detroit Pistons', 'away': 'Cleveland Cavaliers', 'series': 'Game 3'},
    {'date': '11.05.2026', 'time': '01:30 МСК', 'home': 'Oklahoma City Thunder', 'away': 'Los Angeles Lakers', 'series': 'Game 3'},
    # 12 мая
    {'date': '12.05.2026', 'time': '00:00 МСК', 'home': 'New York Knicks', 'away': 'Philadelphia 76ers', 'series': 'Game 3'},
    {'date': '12.05.2026', 'time': '01:30 МСК', 'home': 'San Antonio Spurs', 'away': 'Minnesota Timberwolves', 'series': 'Game 3'},
]

# ============================================================
# БАЗА ДАННЫХ (оставляем как было)
# ============================================================

TEAM_STATS = {
    'Detroit Pistons': {'ppg': 112.5, 'opp_ppg': 109.2, 'win_pct': 73},
    'Cleveland Cavaliers': {'ppg': 115.2, 'opp_ppg': 110.8, 'win_pct': 63},
    'Oklahoma City Thunder': {'ppg': 119.2, 'opp_ppg': 110.5, 'win_pct': 78},
    'Los Angeles Lakers': {'ppg': 116.8, 'opp_ppg': 112.5, 'win_pct': 65},
    'New York Knicks': {'ppg': 114.5, 'opp_ppg': 111.2, 'win_pct': 68},
    'Philadelphia 76ers': {'ppg': 113.8, 'opp_ppg': 112.1, 'win_pct': 60},
    'San Antonio Spurs': {'ppg': 115.5, 'opp_ppg': 111.8, 'win_pct': 66},
    'Minnesota Timberwolves': {'ppg': 113.2, 'opp_ppg': 110.5, 'win_pct': 64}
}

TEAM_FORM = {
    'Detroit Pistons': {'last_10': '8-2', 'streak': 'W3'},
    'Cleveland Cavaliers': {'last_10': '6-4', 'streak': 'L1'},
    'Oklahoma City Thunder': {'last_10': '7-3', 'streak': 'W1'},
    'Los Angeles Lakers': {'last_10': '7-3', 'streak': 'W3'},
    'New York Knicks': {'last_10': '8-2', 'streak': 'W2'},
    'Philadelphia 76ers': {'last_10': '6-4', 'streak': 'W1'},
    'San Antonio Spurs': {'last_10': '9-1', 'streak': 'W4'},
    'Minnesota Timberwolves': {'last_10': '7-3', 'streak': 'W2'}
}

H2H_DATA = {
    ('Detroit Pistons', 'Cleveland Cavaliers'): '2-2',
    ('Oklahoma City Thunder', 'Los Angeles Lakers'): '3-1',
    ('New York Knicks', 'Philadelphia 76ers'): '2-2',
    ('San Antonio Spurs', 'Minnesota Timberwolves'): '1-1'
}

INJURIES = {
    'Los Angeles Lakers': [
        {'name': 'Luka Doncic', 'status': 'Out', 'impact': -12},
        {'name': 'LeBron James', 'status': 'Questionable', 'impact': -8}
    ],
    'Oklahoma City Thunder': [
        {'name': 'Jalen Williams', 'status': 'Out', 'impact': -6},
        {'name': 'Chet Holmgren', 'status': 'Out', 'impact': -7}
    ],
    'New York Knicks': [{'name': 'Jeremy Sochan', 'status': 'Questionable', 'impact': -4}],
}

# ============================================================
# ФУНКЦИИ
# ============================================================

def get_future_matches():
    """Возвращает матчи, которые ещё не начались (дата >= сегодня)"""
    today = datetime.now()
    games = []
    
    for game in SCHEDULE:
        game_date = datetime.strptime(game['date'], '%d.%m.%Y')
        if game_date >= today:
            games.append(game)
            logger.info(f"  Матч: {game['home']} vs {game['away']} | {game['date']} {game['time']}")
    
    return games

def get_team_stats(team_name):
    return TEAM_STATS.get(team_name, {'ppg': 110, 'opp_ppg': 108, 'win_pct': 50})

def get_h2h(team1, team2):
    return H2H_DATA.get((team1, team2), '0-0')

def get_form(team_name):
    return TEAM_FORM.get(team_name, {'last_10': '5-5', 'streak': 'N/A'})

def get_injuries_impact(team_name):
    impact = 0
    injuries_list = []
    if team_name in INJURIES:
        for player in INJURIES[team_name]:
            impact += player.get('impact', 0)
            injuries_list.append(f"{player['name']} ({player['status']})")
    return impact, injuries_list

def calculate_win_probability(home, away, home_stats, away_stats, h2h, home_injury_impact, away_injury_impact):
    base = 50
    
    home_ppg = home_stats.get('ppg', 0)
    away_ppg = away_stats.get('ppg', 0)
    if home_ppg > 0 and away_ppg > 0:
        ppg_effect = (home_ppg - away_ppg) * 0.4
        base += ppg_effect
    
    home_opp = home_stats.get('opp_ppg', 0)
    away_opp = away_stats.get('opp_ppg', 0)
    if home_opp > 0 and away_opp > 0:
        def_effect = (away_opp - home_opp) * 0.3
        base += def_effect
    
    home_pct = home_stats.get('win_pct', 50)
    away_pct = away_stats.get('win_pct', 50)
    pct_effect = (home_pct - away_pct) / 2.5
    base += pct_effect
    
    if h2h != '0-0':
        parts = h2h.split('-')
        home_h2h = int(parts[0])
        away_h2h = int(parts[1])
        total = home_h2h + away_h2h
        if total > 0:
            h2h_effect = (home_h2h / total - 0.5) * 10
            base += h2h_effect
    
    base += home_injury_impact
    base -= away_injury_impact
    base += 4  # домашнее поле
    
    return max(35, min(85, round(base, 1)))

def calculate_total_prediction(home_stats, away_stats):
    home_ppg = home_stats.get('ppg', 0)
    away_ppg = away_stats.get('ppg', 0)
    home_opp = home_stats.get('opp_ppg', 0)
    away_opp = away_stats.get('opp_ppg', 0)
    
    if home_ppg == 0 or away_ppg == 0:
        return None
    
    expected_total = (home_ppg + away_opp) / 2 + (away_ppg + home_opp) / 2
    std_dev = 11.5
    lines = [210.5, 215.5, 220.5, 225.5, 230.5]
    
    from math import erf
    best = None
    best_prob = 0
    
    for line in lines:
        z = (expected_total - line) / std_dev
        prob_over = 0.5 * (1 + erf(z / (2 ** 0.5)))
        prob_over = round(prob_over * 100)
        prob_under = 100 - prob_over
        
        if prob_over > 73 and prob_over > best_prob:
            best_prob = prob_over
            best = f"Тотал БОЛЬШЕ {line} (вер. {prob_over}%)"
        
        if prob_under > 73 and prob_under > best_prob:
            best_prob = prob_under
            best = f"Тотал МЕНЬШЕ {line} (вер. {prob_under}%)"
    
    return best

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ НБА")
    logger.info("   Расписание плей-офф с правильным московским временем")
    logger.info("=" * 60)
    
    os.makedirs('data', exist_ok=True)
    
    games = get_future_matches()
    
    if not games:
        logger.warning("Матчи не найдены")
        output = {
            "lastUpdated": datetime.now().isoformat(),
            "matches": [],
            "dateInfo": {
                "today": datetime.now().strftime('%d.%m.%Y'),
                "tomorrow": (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
            }
        }
        with open('data/matches.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        return
    
    all_matches = []
    
    for game in games:
        home = game['home']
        away = game['away']
        
        logger.info(f"\n📋 {home} vs {away} | {game['date']} {game['time']}")
        
        home_stats = get_team_stats(home)
        away_stats = get_team_stats(away)
        
        h2h = get_h2h(home, away)
        home_form = get_form(home)
        away_form = get_form(away)
        
        home_injury_impact, home_injuries = get_injuries_impact(home)
        away_injury_impact, away_injuries = get_injuries_impact(away)
        
        prob = calculate_win_probability(home, away, home_stats, away_stats, h2h, home_injury_impact, away_injury_impact)
        winner = home if prob >= 50 else away
        total_pred = calculate_total_prediction(home_stats, away_stats)
        
        injuries_text = ""
        if home_injuries:
            injuries_text += f"🏥 {home}: " + ", ".join(home_injuries[:2])
        if away_injuries:
            injuries_text += f" | 🏥 {away}: " + ", ".join(away_injuries[:2])
        if not injuries_text:
            injuries_text = "✅ Все игроки в строю"
        
        match_data = {
            'sport': 'nba',
            'home': home,
            'away': away,
            'league': 'NBA',
            'prob': prob,
            'winner': winner,
            'date': game['date'],
            'time': game['time'],
            'total_prediction': total_pred if total_pred else "Нет уверенного прогноза (>73%)",
            'data_source': 'NBA_Playoffs_Schedule',
            'h2h': h2h,
            'home_ppg': home_stats.get('ppg', 0),
            'away_ppg': away_stats.get('ppg', 0),
            'home_win_pct': home_stats.get('win_pct', 0),
            'away_win_pct': away_stats.get('win_pct', 0),
            'injuries': injuries_text,
            'home_form': home_form.get('last_10', 'N/A'),
            'away_form': away_form.get('last_10', 'N/A'),
            'home_streak': home_form.get('streak', 'N/A'),
            'away_streak': away_form.get('streak', 'N/A')
        }
        
        all_matches.append(match_data)
        logger.info(f"  ✅ {winner} победа ({prob}%)")
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": datetime.now().strftime('%d.%m.%Y'),
            "tomorrow": (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
        }
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✅ ГОТОВО! Сохранено матчей: {len(all_matches)}")

if __name__ == "__main__":
    main()
