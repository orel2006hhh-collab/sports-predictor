#!/usr/bin/env python3
"""
Парсер реальных данных с ESPN + расчёт прогнозов
"""

import json
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
from predict import predict_match, calculate_total

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def get_nba_standings():
    """Получает актуальную турнирную таблицу НБА с ESPN"""
    url = "https://www.espn.com/nba/standings"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        standings = {}
        tables = soup.find_all('table', class_='Table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 5:
                    team_cell = cells[0].find('span', class_='hide-mobile')
                    if team_cell:
                        team_name = team_cell.text.strip()
                        wins = cells[1].text.strip()
                        losses = cells[2].text.strip()
                        win_pct = cells[3].text.strip().replace('%', '')
                        standings[team_name] = {
                            'wins': int(wins),
                            'losses': int(losses),
                            'win_pct': float(win_pct)
                        }
        return standings
    except Exception as e:
        logger.error(f"Ошибка парсинга таблицы: {e}")
        return {}

def get_nba_team_stats(team_name):
    """Получает статистику команды за сезон"""
    url = f"https://www.espn.com/nba/team/stats/_/name/{team_name.lower().replace(' ', '').replace('.', '')}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        stats = {'ppg': 110.5, 'opp_ppg': 108.2, 'form': 50, 'win_pct': 50}
        
        table = soup.find('table', class_='Table')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    stat_name = cells[0].text.strip().lower()
                    if 'points per game' in stat_name or 'ppg' in stat_name:
                        stats['ppg'] = float(cells[1].text.strip())
                    elif 'opponent points per game' in stat_name:
                        stats['opp_ppg'] = float(cells[1].text.strip())
        
        return stats
    except Exception as e:
        logger.warning(f"Ошибка получения статистики для {team_name}: {e}")
        return {'ppg': 110.5, 'opp_ppg': 108.2, 'form': 50, 'win_pct': 50}

def get_h2h_stats(team1, team2):
    """Получает историю личных встреч"""
    url = f"https://www.espn.com/nba/matchup?team1={team1}&team2={team2}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        h2h = {'home_wins': 0, 'away_wins': 0, 'last_meeting': None}
        
        # Ищем блок с историей встреч
        matchup_section = soup.find('div', class_='matchup-stats')
        if matchup_section:
            rows = matchup_section.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    winner = cells[2].text.strip().lower()
                    if 'wins' in winner:
                        if team1.lower() in winner:
                            h2h['home_wins'] += 1
                        elif team2.lower() in winner:
                            h2h['away_wins'] += 1
        
        return h2h
    except Exception as e:
        logger.warning(f"Ошибка получения H2H: {e}")
        return {'home_wins': 2, 'away_wins': 2, 'last_meeting': None}

def get_injuries():
    """Получает список травмированных игроков"""
    url = "https://www.espn.com/nba/injuries"
    injuries = {}
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tables = soup.find_all('table', class_='Table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    player_cell = cells[0].find('a')
                    if player_cell:
                        player_name = player_cell.text.strip()
                        injury = cells[1].text.strip()
                        # Определяем важность травмы
                        if 'out' in injury.lower() or 'season' in injury.lower():
                            injuries[player_name] = {'status': 'OUT', 'description': injury}
        return injuries
    except Exception as e:
        logger.warning(f"Ошибка получения травм: {e}")
        return {}

def get_todays_games(league):
    """Получает расписание матчей на сегодня с ESPN"""
    url = f"https://www.espn.com/{league}/scoreboard"
    games = []
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        event_cards = soup.find_all('section', class_='Card')
        
        for card in event_cards:
            home_team_elem = card.find('div', class_='home-team')
            away_team_elem = card.find('div', class_='away-team')
            time_elem = card.find('div', class_='game-status')
            
            if home_team_elem and away_team_elem:
                home_team = home_team_elem.find('span', class_='short-name').text.strip()
                away_team = away_team_elem.find('span', class_='short-name').text.strip()
                game_time = time_elem.text.strip() if time_elem else '19:00 МСК'
                
                games.append({
                    'home': home_team,
                    'away': away_team,
                    'time': game_time,
                    'league': league.upper()
                })
        
        return games
    except Exception as e:
        logger.error(f"Ошибка получения расписания: {e}")
        return []

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ (ESPN + REAL STATS)")
    logger.info("=" * 60)
    
    all_matches = []
    today = datetime.now().strftime('%d.%m.%Y')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    
    # Получаем турнирную таблицу
    standings = get_nba_standings()
    injuries = get_injuries()
    
    # Получаем расписание на сегодня
    games = get_todays_games('nba')
    
    for game in games:
        home = game['home']
        away = game['away']
        
        logger.info(f"Обработка матча: {home} vs {away}")
        
        # Получаем статистику команд
        home_stats = get_nba_team_stats(home)
        away_stats = get_nba_team_stats(away)
        
        # Добавляем данные из таблицы
        for team_name in standings:
            if team_name.lower() in home.lower():
                home_stats['win_pct'] = standings[team_name]['win_pct']
                home_stats['wins'] = standings[team_name]['wins']
            if team_name.lower() in away.lower():
                away_stats['win_pct'] = standings[team_name]['win_pct']
                away_stats['wins'] = standings[team_name]['wins']
        
        # Получаем историю встреч
        h2h = get_h2h_stats(home, away)
        
        # Рассчитываем прогноз
        prediction = predict_match(
            home_team=home,
            away_team=away,
            league='nba',
            home_stats=home_stats,
            away_stats=away_stats,
            h2h_data=h2h,
            injuries=injuries
        )
        
        total_prediction = calculate_total(home_stats, away_stats)
        
        match_data = {
            'sport': 'nba',
            'home': home,
            'away': away,
            'league': 'NBA',
            'prob': prediction['home_prob'],
            'winner': prediction['winner'],
            'date': today,
            'time': game['time'],
            'total_prediction': total_prediction,
            'data_source': 'ESPN',
            'home_ppg': home_stats.get('ppg', 0),
            'away_ppg': away_stats.get('ppg', 0),
            'h2h': f"{h2h.get('home_wins', 0)}-{h2h.get('away_wins', 0)}"
        }
        
        all_matches.append(match_data)
        logger.info(f"  ✅ {home} {prediction['home_prob']}% — {away}")
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": today,
            "tomorrow": tomorrow
        },
        "stats": {
            "total_matches": len(all_matches),
            "source": "ESPN.com"
        }
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✅ ГОТОВО! Сохранено матчей: {len(all_matches)}")

if __name__ == "__main__":
    main()
