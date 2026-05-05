#!/usr/bin/env python3
"""
Парсер реальных данных с ESPN + расчёт прогнозов
"""

import json
import requests
import re
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# ============================================================
# ФУНКЦИИ ДЛЯ РАСЧЁТА ПРОГНОЗОВ
# ============================================================

def calculate_win_probability(home_stats, away_stats):
    """Рассчитывает вероятность победы на основе статистики"""
    home_ppg = home_stats.get('ppg', 110)
    away_ppg = away_stats.get('ppg', 110)
    home_opp = home_stats.get('opp_ppg', 108)
    away_opp = away_stats.get('opp_ppg', 108)
    
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

# ============================================================
# ПАРСИНГ ESPN (НОВАЯ ВЕРСИЯ)
# ============================================================

def get_nba_games():
    """Получает расписание матчей НБА с ESPN"""
    games = []
    
    # Пробуем несколько URL на случай изменения структуры
    urls = [
        "https://www.espn.com/nba/scoreboard",
        "https://www.espn.com/nba/schedule",
        "https://www.espn.com/nba/scoreboard/_/date/20260506"
    ]
    
    for url in urls:
        try:
            logger.info(f"Пробуем URL: {url}")
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем матчи разными способами
            # Способ 1: через классы ESPN
            cards = soup.find_all('div', class_='Scoreboard')
            if not cards:
                cards = soup.find_all('section', class_='Card')
            if not cards:
                cards = soup.find_all('div', {'class': re.compile('event|match|game')})
            
            for card in cards:
                # Ищем названия команд
                teams = card.find_all('span', class_='team-names')
                if not teams:
                    teams = card.find_all('div', class_='team-name')
                if not teams:
                    teams = card.find_all('abbr', {'class': re.compile('team')})
                
                if len(teams) >= 2:
                    home = teams[0].get_text().strip()
                    away = teams[1].get_text().strip()
                    
                    # Ищем время
                    time_elem = card.find('div', class_='game-status')
                    if not time_elem:
                        time_elem = card.find('span', class_='time')
                    game_time = time_elem.get_text().strip() if time_elem else '19:00 МСК'
                    
                    games.append({
                        'home': home,
                        'away': away,
                        'time': game_time
                    })
            
            if games:
                logger.info(f"Найдено {len(games)} матчей на {url}")
                break
                
        except Exception as e:
            logger.warning(f"Ошибка при парсинге {url}: {e}")
    
    return games

def get_team_stats_espn(team_name):
    """Получает статистику команды с ESPN"""
    # Очищаем название для URL
    clean_name = team_name.lower().replace(' ', '-').replace('.', '').replace('é', 'e')
    if ' ' in clean_name:
        clean_name = clean_name.replace(' ', '-')
    
    url = f"https://www.espn.com/nba/team/stats/_/name/{clean_name}"
    
    stats = {'ppg': 110.5, 'opp_ppg': 108.2, 'wins': 41, 'losses': 41}
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем таблицу со статистикой
        tables = soup.find_all('table', class_='Table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    stat_name = cells[0].get_text().strip().lower()
                    stat_value = cells[1].get_text().strip()
                    
                    if 'points per game' in stat_name:
                        try:
                            stats['ppg'] = float(stat_value)
                        except:
                            pass
                    elif 'opponent points per game' in stat_name:
                        try:
                            stats['opp_ppg'] = float(stat_value)
                        except:
                            pass
        
        logger.debug(f"Статистика для {team_name}: PPG={stats['ppg']}, OPP={stats['opp_ppg']}")
        
    except Exception as e:
        logger.warning(f"Ошибка получения статистики для {team_name}: {e}")
    
    return stats

# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ (ESPN + REAL STATS)")
    logger.info("=" * 60)
    
    # Создаём папку data
    os.makedirs('data', exist_ok=True)
    
    # Получаем матчи
    games = get_nba_games()
    logger.info(f"Найдено матчей: {len(games)}")
    
    if not games:
        logger.warning("Матчи не найдены! Проверьте доступность ESPN")
        # Создаём пустой файл, если матчей нет
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
    
    all_matches = []
    today = datetime.now().strftime('%d.%m.%Y')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    
    for game in games:
        home = game['home']
        away = game['away']
        
        logger.info(f"Обработка матча: {home} vs {away}")
        
        # Получаем статистику
        home_stats = get_team_stats_espn(home)
        away_stats = get_team_stats_espn(away)
        
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
            'data_source': 'ESPN',
            'home_ppg': home_stats.get('ppg', 0),
            'away_ppg': away_stats.get('ppg', 0)
        }
        
        all_matches.append(match_data)
        logger.info(f"  ✅ {home} : {prob}% — {away}")
    
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
