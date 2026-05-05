#!/usr/bin/env python3
"""
Парсер реальных данных с ESPN API + расчёт прогнозов на основе реальной статистики
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
# ПОЛУЧЕНИЕ РАСПИСАНИЯ ИЗ ESPN API
# ============================================================

def get_nba_games_from_api():
    """Получает матчи НБА через ESPN API"""
    games = []
    
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    
    try:
        logger.info(f"Запрос к ESPN API: {url}")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        events = data.get('events', [])
        
        logger.info(f"Найдено событий в API: {len(events)}")
        
        for event in events:
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) >= 2:
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
                    event_date = event.get('date', '')
                    try:
                        dt = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                        msk_time = dt + timedelta(hours=3)
                        game_time = msk_time.strftime('%H:%M МСК')
                    except:
                        game_time = '19:00 МСК'
                    
                    games.append({
                        'home': home_team,
                        'away': away_team,
                        'home_id': home_id,
                        'away_id': away_id,
                        'time': game_time,
                        'game_id': event.get('id')
                    })
                    
                    logger.info(f"  Найден матч: {home_team} (ID:{home_id}) vs {away_team} (ID:{away_id})")
        
    except Exception as e:
        logger.error(f"Ошибка при запросе к ESPN API: {e}")
    
    return games

# ============================================================
# ПОЛУЧЕНИЕ РЕАЛЬНОЙ СТАТИСТИКИ КОМАНД ИЗ ESPN API
# ============================================================

def get_team_stats(team_name, team_id):
    """Получает реальную статистику команды через ESPN API по ID"""
    
    stats = {
        'ppg': 0,           # очки за игру
        'opp_ppg': 0,       # пропущенные очки за игру
        'wins': 0,          # победы
        'losses': 0,        # поражения
        'win_pct': 0,       # процент побед
        'last_10': 0,       # форма (последние 10 матчей)
        'streak': ''        # текущая серия
    }
    
    # Получаем статистику команды через ESPN API
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/stats"
    
    try:
        logger.debug(f"Запрос статистики для {team_name} (ID:{team_id})")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Парсим Splits для сезона
        splits = data.get('splits', [])
        for split in splits:
            if split.get('type') == 'season':
                season_stats = split.get('stats', {})
                
                # Очки за игру (PPG)
                if 'pointsPerGame' in season_stats:
                    stats['ppg'] = round(float(season_stats['pointsPerGame']), 1)
                elif 'avgPoints' in season_stats:
                    stats['ppg'] = round(float(season_stats['avgPoints']), 1)
                
                # Пропущенные очки за игру (OPP PPG)
                if 'opponentPointsPerGame' in season_stats:
                    stats['opp_ppg'] = round(float(season_stats['opponentPointsPerGame']), 1)
                elif 'avgOpponentPoints' in season_stats:
                    stats['opp_ppg'] = round(float(season_stats['avgOpponentPoints']), 1)
                
                # Победы и поражения
                if 'wins' in season_stats:
                    stats['wins'] = int(season_stats['wins'])
                if 'losses' in season_stats:
                    stats['losses'] = int(season_stats['losses'])
                
                # Процент побед
                if 'winPercent' in season_stats:
                    stats['win_pct'] = round(float(season_stats['winPercent']) * 100)
                elif stats['wins'] > 0 or stats['losses'] > 0:
                    stats['win_pct'] = round(stats['wins'] / (stats['wins'] + stats['losses']) * 100)
                
                # Форма за последние 10 игр
                if 'lastTenWinPercent' in season_stats:
                    stats['last_10'] = round(float(season_stats['lastTenWinPercent']) * 100)
                
                # Текущая серия
                if 'streak' in season_stats:
                    streak_data = season_stats['streak']
                    stats['streak'] = f"{streak_data.get('streakType', '')}{streak_data.get('streakLength', 0)}"
        
        logger.info(f"  📊 {team_name}: PPG={stats['ppg']}, OPP PPG={stats['opp_ppg']}, Wins={stats['wins']}, Win%={stats['win_pct']}%")
        
    except Exception as e:
        logger.warning(f"Ошибка получения статистики для {team_name}: {e}")
    
    # Если данные не получены, пробуем альтернативный API
    if stats['ppg'] == 0:
        try:
            alt_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
            alt_response = requests.get(alt_url, headers=HEADERS, timeout=15)
            alt_data = alt_response.json()
            
            for team in alt_data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', []):
                team_info = team.get('team', {})
                if str(team_info.get('id')) == str(team_id):
                    record = team_info.get('record', {})
                    stats['wins'] = record.get('summary', '0-0').split('-')[0]
                    stats['losses'] = record.get('summary', '0-0').split('-')[1]
                    stats['win_pct'] = record.get('winPercent', 0)
                    break
        except:
            pass
    
    return stats

# ============================================================
# ПОЛУЧЕНИЕ ИСТОРИИ ЛИЧНЫХ ВСТРЕЧ (H2H)
# ============================================================

def get_h2h_stats(team1_id, team2_id, team1_name, team2_name):
    """Получает историю личных встреч через ESPN API"""
    h2h = {
        'team1_wins': 0,
        'team2_wins': 0,
        'total_games': 0,
        'last_5': []
    }
    
    # ESPN API для истории встреч
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team1_id}/matchups/{team2_id}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            matchups = data.get('matchups', [])
            
            for matchup in matchups[:10]:  # последние 10 встреч
                home_score = matchup.get('homeScore', 0)
                away_score = matchup.get('awayScore', 0)
                winner = matchup.get('winner', {})
                winner_name = winner.get('displayName', '')
                
                if winner_name == team1_name:
                    h2h['team1_wins'] += 1
                elif winner_name == team2_name:
                    h2h['team2_wins'] += 1
                h2h['total_games'] += 1
                
                h2h['last_5'].append({
                    'date': matchup.get('date', ''),
                    'home': matchup.get('homeTeam', {}).get('displayName', ''),
                    'away': matchup.get('awayTeam', {}).get('displayName', ''),
                    'score': f"{home_score}-{away_score}",
                    'winner': winner_name
                })
            
            logger.info(f"  📊 H2H {team1_name} vs {team2_name}: {h2h['team1_wins']}-{h2h['team2_wins']}")
    except Exception as e:
        logger.debug(f"Ошибка получения H2H: {e}")
    
    return h2h

# ============================================================
# РАСЧЁТ ПРОГНОЗОВ
# ============================================================

def calculate_win_probability(home_name, away_name, home_stats, away_stats, h2h_stats):
    """
    Рассчитывает вероятность победы на основе:
    - Реальной статистики команд (PPG, OPP PPG)
    - Формы (последние 10 игр)
    - Истории личных встреч (H2H)
    - Домашнего поля
    """
    base_prob = 50
    
    # 1. Фактор атаки и защиты (основной)
    home_offense = home_stats.get('ppg', 0)
    home_defense = home_stats.get('opp_ppg', 0)
    away_offense = away_stats.get('ppg', 0)
    away_defense = away_stats.get('opp_ppg', 0)
    
    if home_offense > 0 and away_offense > 0:
        # Сила атаки хозяев (на сколько они набирают больше среднего)
        league_avg = 110  # среднее по лиге
        home_off_factor = (home_offense - league_avg) * 0.5
        away_def_factor = (league_avg - away_defense) * 0.3
        off_advantage = home_off_factor + away_def_factor
        
        # Сила атаки гостей
        away_off_factor = (away_offense - league_avg) * 0.5
        home_def_factor = (league_avg - home_defense) * 0.3
        def_advantage = (home_def_factor - away_def_factor) * 0.5
        
        base_prob += off_advantage + def_advantage
    
    # 2. Фактор формы (последние 10 игр)
    home_form = home_stats.get('last_10', 50)
    away_form = away_stats.get('last_10', 50)
    form_advantage = (home_form - away_form) / 10  # максимум ±5%
    base_prob += form_advantage
    
    # 3. Фактор общей статистики (процент побед в сезоне)
    home_win_pct = home_stats.get('win_pct', 50)
    away_win_pct = away_stats.get('win_pct', 50)
    win_pct_advantage = (home_win_pct - away_win_pct) / 10  # максимум ±5%
    base_prob += win_pct_advantage
    
    # 4. История личных встреч (H2H)
    if h2h_stats and h2h_stats.get('total_games', 0) > 0:
        home_h2h_wins = h2h_stats.get('team1_wins', 0)
        away_h2h_wins = h2h_stats.get('team2_wins', 0)
        total = home_h2h_wins + away_h2h_wins
        if total > 0:
            h2h_advantage = (home_h2h_wins / total - 0.5) * 10  # максимум ±5%
            base_prob += h2h_advantage
    
    # 5. Фактор домашнего поля (+3%)
    base_prob += 3
    
    # Ограничиваем диапазон
    home_prob = max(35, min(85, base_prob))
    away_prob = 100 - home_prob
    
    return round(home_prob, 1)

def calculate_total_prediction(home_stats, away_stats):
    """Расчёт ожидаемого тотала на основе реальной статистики"""
    home_ppg = home_stats.get('ppg', 0)
    away_ppg = away_stats.get('ppg', 0)
    home_opp = home_stats.get('opp_ppg', 0)
    away_opp = away_stats.get('opp_ppg', 0)
    
    if home_ppg == 0 or away_ppg == 0:
        # Если нет данных, используем средние значения
        home_ppg = 110
        away_ppg = 110
        home_opp = 108
        away_opp = 108
    
    # Ожидаемое количество очков
    expected_home = (home_ppg + away_opp) / 2
    expected_away = (away_ppg + home_opp) / 2
    expected_total = expected_home + expected_away
    
    # Линия тотала (округляем до 0.5)
    line = round(expected_total * 2) / 2
    verdict = 'БОЛЬШЕ' if expected_total >= line else 'МЕНЬШЕ'
    
    return f"Тотал {verdict} {line}"

# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ (ESPN API)")
    logger.info("   С реальной статистикой PPG, OPP PPG, формой и H2H")
    logger.info("=" * 60)
    
    os.makedirs('data', exist_ok=True)
    
    # 1. Получаем матчи
    games = get_nba_games_from_api()
    
    if not games:
        logger.error("Матчи не найдены!")
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
        
        # 2. Получаем статистику команд
        home_stats = get_team_stats(home, home_id)
        away_stats = get_team_stats(away, away_id)
        
        # 3. Получаем историю личных встреч
        h2h_stats = get_h2h_stats(home_id, away_id, home, away)
        
        # 4. Рассчитываем прогнозы
        prob = calculate_win_probability(home, away, home_stats, away_stats, h2h_stats)
        winner = home if prob >= 50 else away
        total_prediction = calculate_total_prediction(home_stats, away_stats)
        
        match_data = {
            'sport': 'nba',
            'home': home,
            'away': away,
            'league': 'NBA',
            'prob': prob,
            'winner': winner,
            'date': today,
            'time': game['time'],
            'total_prediction': total_prediction,
            'data_source': 'ESPN_API',
            'home_ppg': home_stats.get('ppg', 0),
            'away_ppg': away_stats.get('ppg', 0),
            'home_win_pct': home_stats.get('win_pct', 0),
            'away_win_pct': away_stats.get('win_pct', 0),
            'home_form': home_stats.get('last_10', 0),
            'away_form': away_stats.get('last_10', 0),
            'h2h': f"{h2h_stats.get('team1_wins', 0)}-{h2h_stats.get('team2_wins', 0)}"
        }
        
        all_matches.append(match_data)
        logger.info(f"  ✅ Прогноз: {winner} победа ({prob}%)")
        logger.info(f"     Тотал: {total_prediction}")
        logger.info(f"     Статистика: {home} PPG={home_stats.get('ppg',0)}, Win%={home_stats.get('win_pct',0)}% | {away} PPG={away_stats.get('ppg',0)}, Win%={away_stats.get('win_pct',0)}%")
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": today,
            "tomorrow": tomorrow
        }
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✅ ГОТОВО! Сохранено матчей: {len(all_matches)}")

if __name__ == "__main__":
    main()
