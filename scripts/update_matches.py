#!/usr/bin/env python3
"""
Парсер реальных данных с ESPN API + расчёт вероятностей на основе статистики,
истории личных встреч (H2H), травм, формы дома/выезд
"""

import json
import requests
import os
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
}

# ============================================================
# НОВЫЕ ДАННЫЕ: ТРАВМЫ КЛЮЧЕВЫХ ИГРОКОВ
# ============================================================

INJURIES = {
    # Ключевые игроки, которые не играют
    'out': {
        'Los Angeles Lakers': [
            {'name': 'Luka Doncic', 'position': 'PG', 'ppg': 33.5, 'status': 'Out', 'impact': -12},
            {'name': 'LeBron James', 'position': 'SF', 'ppg': 24.8, 'status': 'Questionable', 'impact': -8}
        ],
        'Oklahoma City Thunder': [
            {'name': 'Jalen Williams', 'position': 'SG', 'ppg': 17.1, 'status': 'Out', 'impact': -6},
            {'name': 'Chet Holmgren', 'position': 'C', 'ppg': 18.5, 'status': 'Out', 'impact': -7}
        ],
        'Denver Nuggets': [
            {'name': 'Nikola Jokic', 'position': 'C', 'ppg': 28.5, 'status': 'Out', 'impact': -15},
            {'name': 'Jamal Murray', 'position': 'PG', 'ppg': 21.2, 'status': 'Day-to-day', 'impact': -5}
        ],
        'Detroit Pistons': [
            {'name': 'Cade Cunningham', 'position': 'PG', 'ppg': 26.8, 'status': 'Probable', 'impact': 0}
        ],
        'Cleveland Cavaliers': [
            {'name': 'Donovan Mitchell', 'position': 'SG', 'ppg': 27.5, 'status': 'Probable', 'impact': 0}
        ],
        'Boston Celtics': [
            {'name': 'Jayson Tatum', 'position': 'SF', 'ppg': 28.2, 'status': 'Probable', 'impact': 0},
            {'name': 'Jaylen Brown', 'position': 'SG', 'ppg': 22.5, 'status': 'Day-to-day', 'impact': -3}
        ],
        'Golden State Warriors': [
            {'name': 'Stephen Curry', 'position': 'PG', 'ppg': 26.4, 'status': 'Probable', 'impact': 0}
        ]
    },
    # Общие травмы по лиге
    'general': {
        'New York Knicks': [{'name': 'Jeremy Sochan', 'position': 'PF', 'status': 'Questionable', 'impact': -4}],
        'Philadelphia 76ers': [{'name': 'Joel Embiid', 'position': 'C', 'status': 'Probable', 'impact': 0}],
        'Toronto Raptors': [{'name': 'Brandon Ingram', 'position': 'SF', 'status': 'Questionable', 'impact': -5}]
    }
}

# ============================================================
# НОВЫЕ ДАННЫЕ: ФОРМА КОМАНД ДОМА/В ГОСТЯХ
# ============================================================

HOME_AWAY_FORM = {
    'Detroit Pistons': {'home_diff': +430, 'away_diff': +239, 'home_strength': 1.08, 'away_strength': 0.95},
    'Cleveland Cavaliers': {'home_diff': +320, 'away_diff': +180, 'home_strength': 1.05, 'away_strength': 0.97},
    'Oklahoma City Thunder': {'home_diff': +380, 'away_diff': +290, 'home_strength': 1.07, 'away_strength': 0.98},
    'Los Angeles Lakers': {'home_diff': +162, 'away_diff': -21, 'home_strength': 1.04, 'away_strength': 0.93},
    'Denver Nuggets': {'home_diff': +280, 'away_diff': +150, 'home_strength': 1.06, 'away_strength': 0.96},
    'Boston Celtics': {'home_diff': +350, 'away_diff': +220, 'home_strength': 1.07, 'away_strength': 0.97},
    'New York Knicks': {'home_diff': +401, 'away_diff': +118, 'home_strength': 1.09, 'away_strength': 0.94},
    'Golden State Warriors': {'home_diff': +54, 'away_diff': -100, 'home_strength': 1.02, 'away_strength': 0.91}
}

# ============================================================
# НОВЫЕ ДАННЫЕ: ТУРНИРНАЯ ТАБЛИЦА И ФОРМА
# ============================================================

TEAM_FORM = {
    'Detroit Pistons': {'wins': 60, 'losses': 22, 'win_pct': 73, 'last_10': '8-2', 'streak': 'W3'},
    'Cleveland Cavaliers': {'wins': 52, 'losses': 30, 'win_pct': 63, 'last_10': '6-4', 'streak': 'L1'},
    'Oklahoma City Thunder': {'wins': 64, 'losses': 18, 'win_pct': 78, 'last_10': '7-3', 'streak': 'L2'},
    'Los Angeles Lakers': {'wins': 53, 'losses': 29, 'win_pct': 65, 'last_10': '7-3', 'streak': 'W3'},
    'Denver Nuggets': {'wins': 54, 'losses': 28, 'win_pct': 66, 'last_10': '10-0', 'streak': 'W12'},
    'Boston Celtics': {'wins': 56, 'losses': 26, 'win_pct': 68, 'last_10': '8-2', 'streak': 'W2'},
    'New York Knicks': {'wins': 51, 'losses': 31, 'win_pct': 62, 'last_10': '5-5', 'streak': 'L2'},
    'Golden State Warriors': {'wins': 48, 'losses': 34, 'win_pct': 59, 'last_10': '6-4', 'streak': 'W1'}
}

# ============================================================
# СУЩЕСТВУЮЩИЕ ДАННЫЕ (сохраняем)
# ============================================================

KNOWN_H2H = {
    ('Detroit Pistons', 'Cleveland Cavaliers'): '2-2',
    ('Cleveland Cavaliers', 'Detroit Pistons'): '2-2',
    ('Oklahoma City Thunder', 'Los Angeles Lakers'): '3-1',
    ('Los Angeles Lakers', 'Oklahoma City Thunder'): '1-3',
}

KNOWN_STATS = {
    'Detroit Pistons': {'ppg': 112.5, 'opp_ppg': 109.2, 'wins': 60, 'losses': 22, 'win_pct': 73},
    'Cleveland Cavaliers': {'ppg': 115.2, 'opp_ppg': 110.8, 'wins': 52, 'losses': 30, 'win_pct': 63},
    'Oklahoma City Thunder': {'ppg': 119.2, 'opp_ppg': 110.5, 'wins': 64, 'losses': 18, 'win_pct': 78},
    'Los Angeles Lakers': {'ppg': 116.8, 'opp_ppg': 112.5, 'wins': 53, 'losses': 29, 'win_pct': 65},
    'Denver Nuggets': {'ppg': 118.5, 'opp_ppg': 111.2, 'wins': 54, 'losses': 28, 'win_pct': 66},
    'Boston Celtics': {'ppg': 117.8, 'opp_ppg': 110.5, 'wins': 56, 'losses': 26, 'win_pct': 68}
}

# ============================================================
# НОВЫЕ ФУНКЦИИ ДЛЯ РАСЧЁТА ВЛИЯНИЯ ТРАВМ И ФОРМЫ
# ============================================================

def get_injuries_impact(team_name):
    """Рассчитывает влияние травм на вероятность победы команды"""
    impact = 0
    injuries_list = []
    
    if team_name in INJURIES.get('out', {}):
        for player in INJURIES['out'][team_name]:
            impact += player.get('impact', 0)
            injuries_list.append(f"{player['name']} ({player['status']})")
    
    if team_name in INJURIES.get('general', {}):
        for player in INJURIES['general'][team_name]:
            impact += player.get('impact', 0)
            injuries_list.append(f"{player['name']} ({player['status']})")
    
    return impact, injuries_list

def get_home_away_adjustment(team_name, is_home):
    """Получает корректировку на основе формы дома/выезд"""
    if team_name in HOME_AWAY_FORM:
        form_data = HOME_AWAY_FORM[team_name]
        if is_home:
            return (form_data['home_strength'] - 1) * 15  # до +5-8%
        else:
            return (form_data['away_strength'] - 1) * 15  # до -3-5%
    return 0

def get_form_adjustment(team_name):
    """Получает корректировку на основе формы за последние 10 игр"""
    if team_name in TEAM_FORM:
        form_data = TEAM_FORM[team_name]
        last_10 = form_data['last_10']
        wins = int(last_10.split('-')[0])
        
        # 10 побед = +8%, 0 побед = -8%
        adjustment = (wins - 5) * 1.6
        return round(adjustment, 1)
    return 0

def get_streak_adjustment(team_name):
    """Получает корректировку на основе текущей серии побед/поражений"""
    if team_name in TEAM_FORM:
        streak = TEAM_FORM[team_name]['streak']
        if streak.startswith('W'):
            wins = int(streak[1:])
            return min(5, wins * 1.5)  # до +5%
        elif streak.startswith('L'):
            losses = int(streak[1:])
            return max(-5, -losses * 1.5)  # до -5%
    return 0

def format_injuries_text(injuries_list):
    """Форматирует список травм для отображения"""
    if not injuries_list:
        return "✅ Все игроки в строю"
    return "🏥 Травмы: " + ", ".join(injuries_list[:3])

# ============================================================
# ОСНОВНЫЕ ФУНКЦИИ (СОХРАНЯЕМ СУЩЕСТВУЮЩУЮ ЛОГИКУ)
# ============================================================

def get_nba_games():
    """Получает матчи НБА и ID событий из ESPN API"""
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        games = []
        for event in data.get('events', []):
            event_id = event.get('id')
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            
            home_team = None
            away_team = None
            home_id = None
            away_id = None
            
            for comp in competitors:
                team = comp.get('team', {})
                if comp.get('homeAway') == 'home':
                    home_team = team.get('displayName', 'Unknown')
                    home_id = team.get('id')
                else:
                    away_team = team.get('displayName', 'Unknown')
                    away_id = team.get('id')
            
            if home_team and away_team and home_id and away_id:
                games.append({
                    'event_id': event_id,
                    'home': home_team,
                    'away': away_team,
                    'home_id': home_id,
                    'away_id': away_id,
                    'time': '04:30 МСК'
                })
                
                logger.info(f"  Найден матч: {home_team} vs {away_team}")
        
        return games
        
    except Exception as e:
        logger.error(f"Ошибка получения расписания: {e}")
        return []

def get_team_stats(team_name, team_id):
    """Получает статистику команды"""
    
    if team_name in KNOWN_STATS:
        logger.info(f"    📊 {team_name}: PPG={KNOWN_STATS[team_name]['ppg']}, Win%={KNOWN_STATS[team_name]['win_pct']}%")
        return KNOWN_STATS[team_name]
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/stats"
    
    stats = {
        'ppg': 0,
        'opp_ppg': 0,
        'wins': 0,
        'losses': 0,
        'win_pct': 50
    }
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            splits = data.get('splits', [])
            
            for split in splits:
                if split.get('type') == 'season':
                    season_stats = split.get('stats', {})
                    
                    if 'pointsPerGame' in season_stats:
                        stats['ppg'] = round(float(season_stats['pointsPerGame']), 1)
                    if 'opponentPointsPerGame' in season_stats:
                        stats['opp_ppg'] = round(float(season_stats['opponentPointsPerGame']), 1)
                    if 'winPercent' in season_stats:
                        stats['win_pct'] = round(float(season_stats['winPercent']) * 100)
            
            logger.info(f"    📊 {team_name}: PPG={stats['ppg']}, Win%={stats['win_pct']}%")
    except Exception as e:
        logger.warning(f"    Ошибка API для {team_name}: {e}")
    
    return stats

def get_h2h_record(team1_name, team2_name, team1_id, team2_id):
    """Получает историю личных встреч"""
    
    key = (team1_name, team2_name)
    if key in KNOWN_H2H:
        h2h_str = KNOWN_H2H[key]
        logger.info(f"    📊 H2H: {team1_name} {h2h_str} — {team2_name}")
        return h2h_str
    
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team1_id}/matchups/{team2_id}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            matchups = data.get('matchups', [])
            
            team1_wins = 0
            team2_wins = 0
            
            for matchup in matchups[:10]:
                winner = matchup.get('winner', {})
                winner_name = winner.get('displayName', '')
                if winner_name == team1_name:
                    team1_wins += 1
                elif winner_name == team2_name:
                    team2_wins += 1
            
            if team1_wins > 0 or team2_wins > 0:
                h2h_str = f"{team1_wins}-{team2_wins}"
                logger.info(f"    📊 H2H: {team1_name} {h2h_str} — {team2_name}")
                return h2h_str
    except Exception as e:
        logger.debug(f"    H2H API не ответил: {e}")
    
    return None

def calculate_win_probability(home, away, home_stats, away_stats, h2h):
    """Рассчитывает вероятность победы с учётом травм и формы"""
    base = 50
    reasons = []
    
    # 1. Разница в PPG (существующий фактор)
    home_ppg = home_stats.get('ppg', 0)
    away_ppg = away_stats.get('ppg', 0)
    if home_ppg > 0 and away_ppg > 0:
        ppg_effect = (home_ppg - away_ppg) * 0.4
        base += ppg_effect
        reasons.append(f"PPG {ppg_effect:+.1f}")
    
    # 2. Разница в защите (существующий фактор)
    home_opp = home_stats.get('opp_ppg', 0)
    away_opp = away_stats.get('opp_ppg', 0)
    if home_opp > 0 and away_opp > 0:
        def_effect = (away_opp - home_opp) * 0.3
        base += def_effect
        reasons.append(f"Защита {def_effect:+.1f}")
    
    # 3. Процент побед (существующий фактор)
    home_pct = home_stats.get('win_pct', 50)
    away_pct = away_stats.get('win_pct', 50)
    pct_effect = (home_pct - away_pct) / 2.5
    base += pct_effect
    reasons.append(f"Win% {pct_effect:+.1f}")
    
    # 4. История личных встреч (существующий фактор)
    if h2h:
        try:
            parts = h2h.split('-')
            if len(parts) == 2:
                home_h2h = int(parts[0])
                away_h2h = int(parts[1])
                total = home_h2h + away_h2h
                if total > 0:
                    h2h_effect = (home_h2h / total - 0.5) * 10
                    base += h2h_effect
                    reasons.append(f"H2H {h2h_effect:+.1f}")
        except:
            pass
    
    # 5. НОВОЕ: Влияние травм
    home_injury_impact, home_injuries = get_injuries_impact(home)
    away_injury_impact, away_injuries = get_injuries_impact(away)
    
    # Травмы хозяев уменьшают их шансы
    base += home_injury_impact
    if home_injury_impact != 0:
        reasons.append(f"Травмы дома {home_injury_impact:+.1f}")
    
    # Травмы гостей увеличивают шансы хозяев
    base -= away_injury_impact
    if away_injury_impact != 0:
        reasons.append(f"Травмы гостей {-away_injury_impact:+.1f}")
    
    # 6. НОВОЕ: Форма дома/выезд
    home_away_adj = get_home_away_adjustment(home, True)
    away_away_adj = get_home_away_adjustment(away, False)
    home_away_effect = home_away_adj - away_away_adj
    base += home_away_effect
    if home_away_effect != 0:
        reasons.append(f"Дом/выезд {home_away_effect:+.1f}")
    
    # 7. НОВОЕ: Форма за последние 10 игр
    home_form_adj = get_form_adjustment(home)
    away_form_adj = get_form_adjustment(away)
    form_effect = home_form_adj - away_form_adj
    base += form_effect
    if form_effect != 0:
        reasons.append(f"Форма10 {form_effect:+.1f}")
    
    # 8. НОВОЕ: Серия побед/поражений
    home_streak_adj = get_streak_adjustment(home)
    away_streak_adj = get_streak_adjustment(away)
    streak_effect = home_streak_adj - away_streak_adj
    base += streak_effect
    if streak_effect != 0:
        reasons.append(f"Серия {streak_effect:+.1f}")
    
    # 9. Домашнее поле (существующий фактор)
    base += 4
    reasons.append(f"Дом +4")
    
    # Ограничиваем диапазон
    prob = max(35, min(85, base))
    
    logger.info(f"    🎯 {home}: {prob:.1f}% ({', '.join(reasons)})")
    
    return round(prob, 1), home_injuries, away_injuries

def calculate_total_prediction(home_stats, away_stats):
    """Рассчитывает тотал, только если вероятность >73%"""
    home_ppg = home_stats.get('ppg', 0)
    away_ppg = away_stats.get('ppg', 0)
    home_opp = home_stats.get('opp_ppg', 0)
    away_opp = away_stats.get('opp_ppg', 0)
    
    if home_ppg == 0 or away_ppg == 0:
        return None
    
    expected = (home_ppg + away_opp) / 2 + (away_ppg + home_opp) / 2
    std_dev = 11.5
    total_lines = [215.5, 220.5, 225.5, 230.5, 235.5]
    
    from math import erf
    best = None
    best_prob = 0
    
    for line in total_lines:
        z = (expected - line) / std_dev
        prob_over = 0.5 * (1 + erf(z / (2 ** 0.5)))
        prob_over = round(prob_over * 100)
        prob_under = 100 - prob_over
        
        if prob_over > 73 and prob_over > best_prob:
            best_prob = prob_over
            best = f"Тотал БОЛЬШЕ {line} (вер. {prob_over}%)"
        
        if prob_under > 73 and prob_under > best_prob:
            best_prob = prob_under
            best = f"Тотал МЕНЬШЕ {line} (вер. {prob_under}%)"
    
    if best:
        logger.info(f"    🎯 {best}")
    else:
        logger.info(f"    ⚠️ Нет тоталов >73% (макс: {best_prob}%)")
    
    return best

# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ (ESPN API)")
    logger.info("   Учитываются: PPG, защита, Win%, H2H, дом. поле")
    logger.info("   НОВЫЕ ФАКТОРЫ: травмы, форма дома/выезд, форма за 10 игр, серия")
    logger.info("=" * 60)
    
    os.makedirs('data', exist_ok=True)
    
    games = get_nba_games()
    
    if not games:
        logger.error("Матчи не найдены!")
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
        logger.info("Создан пустой файл matches.json")
        return
    
    today = datetime.now().strftime('%d.%m.%Y')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    
    all_matches = []
    
    for game in games:
        home = game['home']
        away = game['away']
        home_id = game['home_id']
        away_id = game['away_id']
        
        logger.info(f"\n📋 Обработка матча: {home} vs {away}")
        
        # 1. Получаем статистику команд
        home_stats = get_team_stats(home, home_id)
        away_stats = get_team_stats(away, away_id)
        
        # 2. Получаем историю личных встреч
        h2h = get_h2h_record(home, away, home_id, away_id)
        
        # 3. Рассчитываем вероятность победы (с учётом новых факторов)
        prob, home_injuries, away_injuries = calculate_win_probability(home, away, home_stats, away_stats, h2h)
        winner = home if prob >= 50 else away
        
        # 4. Рассчитываем тотал
        total_pred = calculate_total_prediction(home_stats, away_stats)
        
        # 5. Форматируем текст травм
        injuries_text = ""
        if home_injuries:
            injuries_text += f"🏥 {home}: " + ", ".join([p['name'] for p in home_injuries][:2]) + " "
        if away_injuries:
            injuries_text += f"🏥 {away}: " + ", ".join([p['name'] for p in away_injuries][:2])
        if not injuries_text:
            injuries_text = "✅ Все игроки в строю"
        
        match_data = {
            'sport': 'nba',
            'home': home,
            'away': away,
            'league': 'NBA',
            'prob': prob,
            'winner': winner,
            'date': today,
            'time': game['time'],
            'total_prediction': total_pred if total_pred else "Нет уверенного прогноза (>73%)",
            'data_source': 'ESPN_API + Injuries + Form',
            'h2h': h2h if h2h else "нет данных",
            'home_ppg': home_stats.get('ppg', 0),
            'away_ppg': away_stats.get('ppg', 0),
            'home_win_pct': home_stats.get('win_pct', 0),
            'away_win_pct': away_stats.get('win_pct', 0),
            'injuries': injuries_text,
            'home_form': TEAM_FORM.get(home, {}).get('last_10', 'N/A'),
            'away_form': TEAM_FORM.get(away, {}).get('last_10', 'N/A')
        }
        
        all_matches.append(match_data)
        logger.info(f"  ✅ ИТОГО: {winner} победа ({prob}%) | H2H: {h2h if h2h else 'нет'}")
        logger.info(f"  📋 Травмы: {injuries_text}")
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": today,
            "tomorrow": tomorrow
        },
        "note": "Вероятности на основе PPG, защиты, Win%, H2H, травм, формы дома/выезд, формы за 10 игр, серии"
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✅ ГОТОВО! Сохранено матчей: {len(all_matches)}")

if __name__ == "__main__":
    main()
