#!/usr/bin/env python3
"""
Парсер матчей и статистики из RSS-лент Yahoo Sports + Flashscore.
Подтягивает реальную статистику команд для точных прогнозов.
"""

import json
import feedparser
import re
import asyncio
import aiohttp
from datetime import datetime, timedelta
import logging

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

# Кэш для статистики команд
team_stats_cache = {}

# ============================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ СО СТАТИСТИКОЙ ИЗ FLASHSCORE
# ============================================================

async def get_team_stats_flashscore(team_name, sport, session):
    """
    Получает реальную статистику команды через библиотеку fs-football-fork [citation:1].
    """
    cache_key = f"{sport}_{team_name}"
    if cache_key in team_stats_cache:
        return team_stats_cache[cache_key]
    
    try:
        # Импортируем библиотеку
        from flashscore import FlashscoreApi
        
        logger.info(f"  📊 Поиск статистики для {team_name} на Flashscore")
        
        # Создаём экземпляр API
        api = FlashscoreApi(session=session)
        
        # Ищем команду по названию
        # Библиотека позволяет искать данные асинхронно [citation:1]
        search_results = await api.search_team(team_name)
        
        if search_results and len(search_results) > 0:
            team_id = search_results[0]['id']
            logger.info(f"    Найдена команда {team_name} с ID {team_id}")
            
            # Получаем исторические матчи команды
            matches = await api.get_team_matches(team_id)
            
            if matches and len(matches) > 0:
                total_scored = 0
                total_conceded = 0
                match_count = 0
                wins = 0
                
                # Анализируем последние 20 матчей [citation:1]
                for match in matches[:20]:
                    if hasattr(match, 'home_team_score') and hasattr(match, 'away_team_score'):
                        if match.home_team_name == team_name:
                            scored = match.home_team_score or 0
                            conceded = match.away_team_score or 0
                        else:
                            scored = match.away_team_score or 0
                            conceded = match.home_team_score or 0
                        
                        total_scored += scored
                        total_conceded += conceded
                        match_count += 1
                        if scored > conceded:
                            wins += 1
                
                if match_count > 0:
                    avg_scored = total_scored / match_count
                    avg_conceded = total_conceded / match_count
                    win_rate = wins / match_count
                    
                    stats = {
                        'goals_scored': round(avg_scored, 1),
                        'goals_conceded': round(avg_conceded, 1),
                        'form': round(win_rate * 100),
                        'matches_analyzed': match_count
                    }
                    
                    team_stats_cache[cache_key] = stats
                    logger.info(f"    ✅ {team_name}: забивает {avg_scored:.1f}, пропускает {avg_conceded:.1f} (на основе {match_count} матчей)")
                    return stats
        
        logger.warning(f"    ⚠️ Статистика для {team_name} не найдена на Flashscore")
        
    except ImportError:
        logger.warning(f"  ⚠️ Библиотека fs-football-fork не установлена.")
        logger.info("     Установите: pip install fs-football-fork")
    except Exception as e:
        logger.warning(f"  ⚠️ Ошибка получения статистики для {team_name}: {e}")
    
    # Если не нашли, возвращаем None
    return None

def calculate_total_prediction(home_stats, away_stats, sport):
    """
    Рассчитывает прогнозируемый тотал на основе реальной статистики.
    """
    if home_stats is None or away_stats is None:
        # Если статистики нет — используем логику по умолчанию
        return None
    
    home_avg = home_stats['goals_scored']
    away_avg = away_stats['goals_scored']
    home_conceded = home_stats['goals_conceded']
    away_conceded = away_stats['goals_conceded']
    
    # Ожидаемое количество
    expected_home = (home_avg + away_conceded) / 2
    expected_away = (away_avg + home_conceded) / 2
    expected_total = expected_home + expected_away
    
    # Корректировка для разных видов спорта
    if sport == 'nba':
        line = round(expected_total / 5) * 5
        if expected_total > line:
            return f"Тотал БОЛЬШЕ {line}.5"
        else:
            return f"Тотал МЕНЬШЕ {line}.5"
    elif sport == 'nfl':
        line = round(expected_total)
        half = line + 0.5
        if expected_total > line:
            return f"Тотал БОЛЬШЕ {half}"
        else:
            return f"Тотал МЕНЬШЕ {half}"
    else:
        line = round(expected_total * 2) / 2
        if expected_total > line:
            return f"Тотал БОЛЬШЕ {line}"
        else:
            return f"Тотал МЕНЬШЕ {line}"

def calculate_win_probability(home_stats, away_stats):
    """
    Рассчитывает вероятность победы на основе реальной статистики.
    """
    if home_stats is None or away_stats is None:
        # Если статистики нет — возвращаем нейтральное значение
        return 65
    
    home_power = home_stats['goals_scored'] / (home_stats['goals_scored'] + home_stats['goals_conceded'])
    away_power = away_stats['goals_scored'] / (away_stats['goals_scored'] + away_stats['goals_conceded'])
    
    prob = int(50 + (home_power - away_power) * 35)
    return max(55, min(85, prob))

def get_default_stats(sport):
    """Возвращает значения по умолчанию для статистики"""
    defaults = {
        'nhl': {'goals_scored': 3.2, 'goals_conceded': 2.8, 'form': 65},
        'nba': {'goals_scored': 112, 'goals_conceded': 109, 'form': 65},
        'mlb': {'goals_scored': 4.5, 'goals_conceded': 4.2, 'form': 65},
        'nfl': {'goals_scored': 23, 'goals_conceded': 21, 'form': 65},
        'mls': {'goals_scored': 1.8, 'goals_conceded': 1.5, 'form': 65},
    }
    return defaults.get(sport, {'goals_scored': 2.5, 'goals_conceded': 2.5, 'form': 65})

# ============================================================
# ПАРСИНГ RSS (точная копия вашей рабочей логики)
# ============================================================

def get_moscow_time():
    return datetime.now().strftime('%H:%M МСК')

def parse_date_from_rss(published_parsed):
    if published_parsed:
        return datetime(*published_parsed[:6]).strftime('%d.%m.%Y')
    return datetime.now().strftime('%d.%m.%Y')

def extract_teams(title):
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

async def fetch_from_rss_async(league_key, league_config, session):
    """
    Асинхронно парсит RSS-ленту и возвращает список матчей.
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
                    # Получаем реальную статистику из Flashscore
                    home_stats = await get_team_stats_flashscore(home, league_key, session)
                    away_stats = await get_team_stats_flashscore(away, league_key, session)
                    
                    # Если статистика не найдена — используем значения по умолчанию
                    if home_stats is None:
                        home_stats = get_default_stats(league_key)
                    if away_stats is None:
                        away_stats = get_default_stats(league_key)
                    
                    # Рассчитываем прогнозы
                    total_prediction = calculate_total_prediction(home_stats, away_stats, league_key)
                    win_prob = calculate_win_probability(home_stats, away_stats)
                    
                    # Если тотал не рассчитался — используем логику по умолчанию
                    if total_prediction is None:
                        total_prediction = 'Тотал БОЛЬШЕ 5.5' if win_prob > 65 else 'Тотал МЕНЬШЕ 5.5'
                    
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
                        'home_avg_goals': home_stats['goals_scored'],
                        'away_avg_goals': away_stats['goals_scored'],
                        'data_source': 'flashscore' if home_stats.get('matches_analyzed') else 'default'
                    })
                    
                    logger.info(f"  ✅ {home} vs {away}: {total_prediction} (вероятность {win_prob}%)")
                    
                    # Небольшая задержка, чтобы не перегружать Flashscore
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"Ошибка при парсинге {url}: {e}")
    
    return matches[:10]

def fetch_from_rss(league_key, league_config):
    """
    Синхронная обёртка для асинхронной функции.
    """
    async def run_async():
        async with aiohttp.ClientSession() as session:
            return await fetch_from_rss_async(league_key, league_config, session)
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_async())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Ошибка при асинхронном вызове: {e}")
        return []

# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ")
    logger.info("   Источник расписания: Yahoo Sports RSS")
    logger.info("   Источник статистики: Flashscore.com")
    logger.info("=" * 60)
    
    all_matches = []
    
    for league_key, league_config in LEAGUES.items():
        logger.info(f"\n📋 Обработка {league_config['name']}")
        matches = fetch_from_rss(league_key, league_config)
        all_matches.extend(matches)
        logger.info(f"   Найдено матчей: {len(matches)}")
    
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    
    # Подсчитываем статистику по источникам данных
    flashscore_count = sum(1 for m in all_matches if m.get('data_source') == 'flashscore')
    default_count = len(all_matches) - flashscore_count
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": today.strftime('%d.%m.%Y'),
            "tomorrow": tomorrow.strftime('%d.%m.%Y')
        },
        "dataStats": {
            "flashscore_data": flashscore_count,
            "default_data": default_count,
            "total": len(all_matches)
        }
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"✅ ГОТОВО! Сохранено матчей: {len(all_matches)}")
    logger.info(f"   📊 Из них с реальной статистикой Flashscore: {flashscore_count}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
