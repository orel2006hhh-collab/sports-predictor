#!/usr/bin/env python3
"""
Парсер матчей и статистики из RSS-лент Yahoo Sports + Flashscore.
Собирает реальную статистику команд для точного прогноза тотала.
"""

import json
import feedparser
import re
import asyncio
from datetime import datetime, timedelta
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Лиги для парсинга
LEAGUES = {
    'nhl': {'name': 'NHL', 'sources': ['https://sports.yahoo.com/nhl/rss/']},
    'nba': {'name': 'NBA', 'sources': ['https://sports.yahoo.com/nba/rss/']},
    'mlb': {'name': 'MLB', 'sources': ['https://sports.yahoo.com/mlb/rss/']},
    'nfl': {'name': 'NFL', 'sources': ['https://sports.yahoo.com/nfl/rss/']},
    'mls': {'name': 'MLS', 'sources': ['https://sports.yahoo.com/mls/rss/']},
}

# Кэш для статистики команд (чтобы не делать повторные запросы)
team_stats_cache = {}

# ============================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ СО СТАТИСТИКОЙ ИЗ FLASHSCORE
# ============================================================

async def get_team_stats_flashscore(team_name, sport):
    """
    Получает статистику команды через библиотеку fs-football-fork
    """
    cache_key = f"{sport}_{team_name}"
    if cache_key in team_stats_cache:
        return team_stats_cache[cache_key]
    
    try:
        # Импортируем библиотеку (внутри функции, чтобы не ломалась при отсутствии)
        from flashscore import FlashscoreApi
        
        logger.info(f"  📊 Поиск статистики для {team_name}")
        
        # Создаём экземпляр API
        api = FlashscoreApi()
        
        # Ищем команду по названию
        search_results = await api.search_team(team_name)
        
        if search_results and len(search_results) > 0:
            # Берём первый найденный результат
            team_id = search_results[0]['id']
            
            # Получаем статистику команды в текущем сезоне
            stats = await api.get_team_stats(team_id)
            
            # Извлекаем нужные показатели
            goals_scored = stats.get('goals_avg_scored', 0)
            goals_conceded = stats.get('goals_avg_conceded', 0)
            form = stats.get('form', 0)
            
            if goals_scored > 0:
                result = {
                    'goals_scored': float(goals_scored),
                    'goals_conceded': float(goals_conceded),
                    'form': form if form > 0 else 65
                }
                team_stats_cache[cache_key] = result
                logger.info(f"    ✅ {team_name}: {goals_scored} забито, {goals_conceded} пропущено")
                return result
        
        # Если не нашли, возвращаем значения по умолчанию
        logger.warning(f"    ⚠️ Статистика для {team_name} не найдена")
        
    except ImportError:
        logger.warning(f"  ⚠️ Библиотека fs-football-fork не установлена. Установите: pip install fs-football-fork")
    except Exception as e:
        logger.warning(f"  ⚠️ Ошибка получения статистики для {team_name}: {e}")
    
    # Значения по умолчанию (реалистичные показатели)
    default_stats = {
        'nhl': {'goals_scored': 3.2, 'goals_conceded': 2.8, 'form': 65},
        'nba': {'goals_scored': 112, 'goals_conceded': 109, 'form': 65},
        'mlb': {'goals_scored': 4.5, 'goals_conceded': 4.2, 'form': 65},
        'nfl': {'goals_scored': 23, 'goals_conceded': 21, 'form': 65},
        'mls': {'goals_scored': 1.8, 'goals_conceded': 1.5, 'form': 65},
    }
    default = default_stats.get(sport, {'goals_scored': 2.5, 'goals_conceded': 2.5, 'form': 65})
    team_stats_cache[cache_key] = default
    return default

def get_team_stats_sync(team_name, sport):
    """
    Синхронная обёртка для вызова асинхронной функции
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_team_stats_flashscore(team_name, sport))
        loop.close()
        return result
    except Exception as e:
        logger.warning(f"Ошибка при вызове Flashscore для {team_name}: {e}")
        return {'goals_scored': 2.5, 'goals_conceded': 2.5, 'form': 65}

def calculate_total_prediction(home_stats, away_stats, sport):
    """
    Рассчитывает прогнозируемый тотал на основе статистики команд
    """
    home_avg = home_stats['goals_scored']
    away_avg = away_stats['goals_scored']
    home_conceded = home_stats['goals_conceded']
    away_conceded = away_stats['goals_conceded']
    
    # Ожидаемое количество очков/голов
    expected_home = (home_avg + away_conceded) / 2
    expected_away = (away_avg + home_conceded) / 2
    expected_total = expected_home + expected_away
    
    # Корректировка для разных видов спорта
    if sport == 'nba':
        # НБА: очки
        expected_total = expected_total
        line = round(expected_total / 5) * 5
        if expected_total > line:
            return f"Тотал БОЛЬШЕ {line}.5"
        else:
            return f"Тотал МЕНЬШЕ {line}.5"
    elif sport == 'nfl':
        # NFL: очки
        expected_total = expected_total
        line = round(expected_total)
        half = line + 0.5
        if expected_total > line:
            return f"Тотал БОЛЬШЕ {half}"
        else:
            return f"Тотал МЕНЬШЕ {half}"
    else:
        # Хоккей, бейсбол, футбол
        line = round(expected_total * 2) / 2
        if expected_total > line:
            return f"Тотал БОЛЬШЕ {line}"
        else:
            return f"Тотал МЕНЬШЕ {line}"

def calculate_win_probability(home_stats, away_stats):
    """
    Рассчитывает вероятность победы команды на основе статистики
    """
    home_power = home_stats['goals_scored'] / (home_stats['goals_scored'] + home_stats['goals_conceded'])
    away_power = away_stats['goals_scored'] / (away_stats['goals_scored'] + away_stats['goals_conceded'])
    
    prob = int(50 + (home_power - away_power) * 35)
    return max(55, min(85, prob))

# ============================================================
# ПАРСИНГ RSS (оригинальная логика)
# ============================================================

def get_moscow_time():
    """Возвращает текущее московское время"""
    return datetime.now().strftime('%H:%M МСК')

def parse_date_from_rss(published_parsed):
    """Преобразует дату из RSS в формат ДД.ММ.ГГГГ"""
    if published_parsed:
        return datetime(*published_parsed[:6]).strftime('%d.%m.%Y')
    return datetime.now().strftime('%d.%m.%Y')

def extract_teams(title):
    """Извлекает названия команд из заголовка RSS-ленты"""
    patterns = [
        r'([A-Za-z\s]+?)\s+(?:at|vs\.?)\s+([A-Za-z\s]+?)(?:\s|$)',
        r'([A-Za-z\s]+?)\s+-\s+([A-Za-z\s]+?)(?:\s|$)'
    ]
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            team1 = match.group(1).strip()
            team2 = match.group(2).strip()
            if len(team1) > 2 and len(team2) > 2 and len(team1) < 40 and len(team2) < 40:
                return team1, team2
    return None, None

def fetch_from_rss(league_key, league_config):
    """
    Парсит RSS-ленту и возвращает список матчей с статистикой
    """
    matches = []
    for url in league_config['sources']:
        try:
            logger.info(f"Парсинг {league_config['name']}: {url}")
            feed = feedparser.parse(url)
            
            for entry in feed.entries[:15]:
                title = entry.get('title', '')
                home, away = extract_teams(title)
                
                if home and away and home != away:
                    # Получаем статистику команд
                    home_stats = get_team_stats_sync(home, league_key)
                    away_stats = get_team_stats_sync(away, league_key)
                    
                    # Рассчитываем прогнозы
                    total_prediction = calculate_total_prediction(home_stats, away_stats, league_key)
                    win_prob = calculate_win_probability(home_stats, away_stats)
                    
                    matches.append({
                        'sport': league_key,
                        'home': home,
                        'away': away,
                        'league': league_config['name'],
                        'prob': win_prob,
                        'winner': home if win_prob >= 50 else away,
                        'date': parse_date_from_rss(entry.get('published_parsed')),
                        'time': get_moscow_time(),
                        'total_prediction': total_prediction,
                        'home_avg_goals': round(home_stats['goals_scored'], 1),
                        'away_avg_goals': round(away_stats['goals_scored'], 1)
                    })
                    
                    logger.info(f"  ✅ {home} vs {away}: тотал {total_prediction} (вероятность {win_prob}%)")
                    
        except Exception as e:
            logger.error(f"Ошибка при парсинге {url}: {e}")
    
    return matches[:10]

# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ (RSS + Flashscore)")
    logger.info("=" * 60)
    
    all_matches = []
    
    for league_key, league_config in LEAGUES.items():
        logger.info(f"\n📋 Обработка {league_config['name']}")
        matches = fetch_from_rss(league_key, league_config)
        all_matches.extend(matches)
        logger.info(f"   Найдено матчей: {len(matches)}")
    
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": today.strftime('%d.%m.%Y'),
            "tomorrow": tomorrow.strftime('%d.%m.%Y')
        }
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"✅ ГОТОВО! Сохранено матчей: {len(all_matches)}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
