#!/usr/bin/env python3
"""
Парсер реальных данных с ESPN API + расчёт прогнозов
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

def get_nba_games_from_api():
    """Получает матчи НБА через ESPN API"""
    games = []
    
    # ESPN API endpoint для счёта матчей
    date_str = datetime.now().strftime('%Y%m%d')
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    
    try:
        logger.info(f"Запрос к ESPN API: {url}")
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        events = data.get('events', [])
        
        logger.info(f"Найдено событий в API: {len(events)}")
        
        for event in events:
            # Извлекаем информацию о матче
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            
            if len(competitors) >= 2:
                # Определяем хозяев и гостей
                home_team = None
                away_team = None
                
                for comp in competitors:
                    if comp.get('homeAway') == 'home':
                        home_team = comp.get('team', {}).get('displayName', 'Unknown')
                    else:
                        away_team = comp.get('team', {}).get('displayName', 'Unknown')
                
                if home_team and away_team:
                    # Время матча (переводим в МСК)
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
                        'time': game_time,
                        'game_id': event.get('id'),
                        'status': competition.get('status', {}).get('type', {}).get('description', '')
                    })
                    
                    logger.info(f"  Найден матч: {home_team} vs {away_team} в {game_time}")
        
    except Exception as e:
        logger.error(f"Ошибка при запросе к ESPN API: {e}")
    
    return games

def get_team_stats_espn_api(team_name):
    """Получает статистику команды через ESPN API"""
    # Очищаем название для URL
    clean_name = team_name.lower().replace(' ', '-').replace('.', '')
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
    
    stats = {'ppg': 110.5, 'opp_ppg': 108.2, 'wins': 41, 'losses': 41}
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        data = response.json()
        
        for team in data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', []):
            team_data = team.get('team', {})
            if team_data.get('displayName', '').lower() == team_name.lower():
                # Нашли команду, можно получить статистику
                team_id = team_data.get('id')
                if team_id:
                    stats_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/stats"
                    stats_response = requests.get(stats_url, headers=HEADERS, timeout=15)
                    stats_data = stats_response.json()
                    
                    # Парсим статистику
                    for stat in stats_data.get('stats', []):
                        if stat.get('name') == 'pointsPerGame':
                            stats['ppg'] = float(stat.get('value', 110.5))
                        elif stat.get('name') == 'opponentPointsPerGame':
                            stats['opp_ppg'] = float(stat.get('value', 108.2))
                        elif stat.get('name') == 'wins':
                            stats['wins'] = int(stat.get('value', 41))
                        elif stat.get('name') == 'losses':
                            stats['losses'] = int(stat.get('value', 41))
                    
                    logger.debug(f"Статистика для {team_name}: PPG={stats['ppg']}, OPP={stats['opp_ppg']}")
                    break
                    
    except Exception as e:
        logger.warning(f"Ошибка получения статистики для {team_name}: {e}")
    
    return stats

def calculate_win_probability(home_stats, away_stats):
    """Рассчитывает вероятность победы на основе статистики"""
    home_ppg = home_stats.get('ppg', 110)
    away_ppg = away_stats.get('ppg', 110)
    home_opp = home_stats.get('opp_ppg', 108)
    away_opp = away_stats.get('opp_ppg', 108)
    
    # Сила атаки и защиты
    home_strength = home_ppg / (home_ppg + home_opp) * 100
    away_strength = away_ppg / (away_ppg + away_opp) * 100
    
    home_advantage = 3  # домашнее поле
    
    home_prob = 50 + (home_strength - away_strength) / 2 + home_advantage
    home_prob = max(35, min(85, home_prob))
    
    return round(home_prob, 1)

def calculate_total_prediction(home_stats, away_stats):
    """Расчёт ожидаемого тотала"""
    home_ppg = home_stats.get('ppg', 110)
    away_ppg = away_stats.get('ppg', 110)
    home_opp = home_stats.get('opp_ppg', 108)
    away_opp = away_stats.get('opp_ppg', 108)
    
    expected_total = (home_ppg + away_opp) / 2 + (away_ppg + home_opp) / 2
    line = round(expected_total / 5) * 5
    verdict = 'БОЛЬШЕ' if expected_total > line else 'МЕНЬШЕ'
    
    return f"Тотал {verdict} {line}.5"

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ (ESPN API)")
    logger.info("=" * 60)
    
    os.makedirs('data', exist_ok=True)
    
    # Получаем матчи из ESPN API
    games = get_nba_games_from_api()
    
    if not games:
        logger.warning("Матчи не найдены!")
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
        logger.info("Сохранён пустой файл matches.json")
        return
    
    today = datetime.now().strftime('%d.%m.%Y')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    
    all_matches = []
    
    for game in games:
        home = game['home']
        away = game['away']
        
        logger.info(f"Обработка матча: {home} vs {away}")
        
        # Получаем статистику команд
        home_stats = get_team_stats_espn_api(home)
        away_stats = get_team_stats_espn_api(away)
        
        # Рассчитываем прогнозы
        prob = calculate_win_probability(home_stats, away_stats)
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
            'away_ppg': away_stats.get('ppg', 0)
        }
        
        all_matches.append(match_data)
        logger.info(f"  ✅ {home} : {prob}% — {away} | {total_prediction}")
    
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
