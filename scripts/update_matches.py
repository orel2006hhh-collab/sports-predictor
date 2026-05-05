#!/usr/bin/env python3
"""
Парсер матчей из RSS-лент Yahoo Sports + альтернативные источники.
Улучшенное извлечение названий команд для NBA.
"""

import json
import feedparser
import re
import random
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Лиги с несколькими источниками RSS
LEAGUES = {
    'nhl': {
        'name': 'NHL',
        'sources': [
            'https://sports.yahoo.com/nhl/rss/',
            'https://www.nhl.com/rss/news',
            'https://rss.app/feeds/4zJ1uPp3mX7q2L.xml'
        ]
    },
    'nba': {
        'name': 'NBA',
        'sources': [
            'https://sports.yahoo.com/nba/rss/',
            'https://www.espn.com/espn/rss/nba/news',
            'https://www.cbssports.com/nba/rss/'
        ]
    },
    'mlb': {
        'name': 'MLB',
        'sources': [
            'https://sports.yahoo.com/mlb/rss/',
            'https://www.mlb.com/rss',
            'https://www.espn.com/espn/rss/mlb/news'
        ]
    },
    'nfl': {
        'name': 'NFL',
        'sources': [
            'https://sports.yahoo.com/nfl/rss/',
            'https://www.espn.com/espn/rss/nfl/news',
            'https://www.nfl.com/rss'
        ]
    },
    'mls': {
        'name': 'MLS',
        'sources': [
            'https://sports.yahoo.com/mls/rss/',
            'https://www.mlssoccer.com/rss'
        ]
    },
}

# Словарь для исправления названий команд NBA
NBA_TEAM_FIXES = {
    'ers': '76ers',
    'sixers': '76ers',
    'lakers': 'Los Angeles Lakers',
    'celtics': 'Boston Celtics',
    'warriors': 'Golden State Warriors',
    'warriors?': 'Golden State Warriors',
    'heat': 'Miami Heat',
    'bulls': 'Chicago Bulls',
    'mavericks': 'Dallas Mavericks',
    'nuggets': 'Denver Nuggets',
    'suns': 'Phoenix Suns',
    'knicks': 'New York Knicks',
    'bucks': 'Milwaukee Bucks',
    'clippers': 'LA Clippers',
    'trail blazers': 'Portland Trail Blazers',
    'blazers': 'Portland Trail Blazers',
    'kings': 'Sacramento Kings',
    'hawks': 'Atlanta Hawks',
    'hornets': 'Charlotte Hornets',
    'jazz': 'Utah Jazz',
    'rockets': 'Houston Rockets',
    'grizzlies': 'Memphis Grizzlies',
    'pelicans': 'New Orleans Pelicans',
    'spurs': 'San Antonio Spurs',
    'thunder': 'Oklahoma City Thunder',
    'pistons': 'Detroit Pistons',
    'cavaliers': 'Cleveland Cavaliers',
    'magic': 'Orlando Magic',
    'wizards': 'Washington Wizards',
    'pacers': 'Indiana Pacers',
    'raptors': 'Toronto Raptors',
    'timberwolves': 'Minnesota Timberwolves',
    'wolves': 'Minnesota Timberwolves',
}

# Словарь для исправления названий команд NHL
NHL_TEAM_FIXES = {
    'canadiens': 'Montreal Canadiens',
    'sabres': 'Buffalo Sabres',
    'maple leafs': 'Toronto Maple Leafs',
    'leafs': 'Toronto Maple Leafs',
    'lightning': 'Tampa Bay Lightning',
    'penguins': 'Pittsburgh Penguins',
    'bruins': 'Boston Bruins',
    'rangers': 'New York Rangers',
    'islanders': 'New York Islanders',
    'devils': 'New Jersey Devils',
    'flyers': 'Philadelphia Flyers',
    'capitals': 'Washington Capitals',
    'hurricanes': 'Carolina Hurricanes',
    'blue jackets': 'Columbus Blue Jackets',
    'red wings': 'Detroit Red Wings',
    'senators': 'Ottawa Senators',
    'panthers': 'Florida Panthers',
    'blackhawks': 'Chicago Blackhawks',
    'avalanche': 'Colorado Avalanche',
    'stars': 'Dallas Stars',
    'wild': 'Minnesota Wild',
    'predators': 'Nashville Predators',
    'blues': 'St. Louis Blues',
    'jets': 'Winnipeg Jets',
    'ducks': 'Anaheim Ducks',
    'flames': 'Calgary Flames',
    'oilers': 'Edmonton Oilers',
    'kings': 'Los Angeles Kings',
    'sharks': 'San Jose Sharks',
    'canucks': 'Vancouver Canucks',
    'golden knights': 'Vegas Golden Knights',
    'kraken': 'Seattle Kraken',
    'utah': 'Utah Hockey Club',
}

# Кэш для статистики команд
team_stats_cache = {}

# Базовая статистика для разных видов спорта
BASE_STATS = {
    'nhl': {'goals_scored': 3.2, 'goals_conceded': 2.8, 'form': 65},
    'nba': {'goals_scored': 112, 'goals_conceded': 109, 'form': 65},
    'mlb': {'goals_scored': 4.5, 'goals_conceded': 4.2, 'form': 65},
    'nfl': {'goals_scored': 23, 'goals_conceded': 21, 'form': 65},
    'mls': {'goals_scored': 1.8, 'goals_conceded': 1.5, 'form': 65},
}

def fix_team_name(team_name, sport):
    """Исправляет обрезанные названия команд"""
    if not team_name:
        return team_name
    
    name_lower = team_name.lower().strip()
    
    if sport == 'nba':
        for key, full_name in NBA_TEAM_FIXES.items():
            if key in name_lower or name_lower == key:
                return full_name
    elif sport == 'nhl':
        for key, full_name in NHL_TEAM_FIXES.items():
            if key in name_lower or name_lower == key:
                return full_name
    
    return team_name

def get_team_stats(team_name, sport):
    """
    Получает статистику команды (симулированная, но с разбросом между командами)
    """
    cache_key = f"{sport}_{team_name}"
    if cache_key in team_stats_cache:
        return team_stats_cache[cache_key]
    
    base = BASE_STATS.get(sport, {'goals_scored': 2.5, 'goals_conceded': 2.5, 'form': 65})
    
    # Создаём уникальный разброс на основе названия команды
    hash_val = abs(hash(team_name)) % 20
    variation = (hash_val - 10) / 10
    
    stats = {
        'goals_scored': round(base['goals_scored'] + variation * 0.5, 1),
        'goals_conceded': round(base['goals_conceded'] - variation * 0.3, 1),
        'form': 65 + (hash_val - 10)
    }
    
    # Ограничиваем значения для реалистичности
    if sport == 'nhl':
        stats['goals_scored'] = max(2.5, min(4.5, stats['goals_scored']))
        stats['goals_conceded'] = max(2.0, min(4.0, stats['goals_conceded']))
    elif sport == 'nba':
        stats['goals_scored'] = max(105, min(125, stats['goals_scored']))
        stats['goals_conceded'] = max(100, min(120, stats['goals_conceded']))
    elif sport == 'mlb':
        stats['goals_scored'] = max(3.5, min(5.5, stats['goals_scored']))
        stats['goals_conceded'] = max(3.0, min(5.0, stats['goals_conceded']))
    elif sport == 'nfl':
        stats['goals_scored'] = max(18, min(28, stats['goals_scored']))
        stats['goals_conceded'] = max(16, min(26, stats['goals_conceded']))
    elif sport == 'mls':
        stats['goals_scored'] = max(1.2, min(2.5, stats['goals_scored']))
        stats['goals_conceded'] = max(0.8, min(2.2, stats['goals_conceded']))
    
    stats['form'] = max(45, min(85, stats['form']))
    
    team_stats_cache[cache_key] = stats
    logger.debug(f"  📊 {team_name}: забивает {stats['goals_scored']}, пропускает {stats['goals_conceded']}")
    
    return stats

def calculate_total_prediction(home_stats, away_stats, sport):
    """
    Рассчитывает прогнозируемый тотал на основе статистики команд.
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
    Рассчитывает вероятность победы хозяев на основе статистики.
    """
    home_power = home_stats['goals_scored'] / (home_stats['goals_scored'] + home_stats['goals_conceded'])
    away_power = away_stats['goals_scored'] / (away_stats['goals_scored'] + away_stats['goals_conceded'])
    
    prob = int(50 + (home_power - away_power) * 35)
    return max(55, min(85, prob))

def get_moscow_time():
    return datetime.now().strftime('%H:%M МСК')

def parse_date_from_rss(published_parsed):
    if published_parsed:
        return datetime(*published_parsed[:6]).strftime('%d.%m.%Y')
    return datetime.now().strftime('%d.%m.%Y')

def extract_teams(title, sport):
    """Извлекает названия команд из заголовка RSS-ленты с улучшенным парсингом"""
    if not title:
        return None, None
    
    # Очищаем заголовок от лишнего
    title_clean = re.sub(r'\[.*?\]|\(.*?\)|\d+:\d+.*?$', '', title)
    
    # Паттерны для поиска команд
    patterns = [
        # "Team A at Team B" или "Team A vs Team B"
        r'([A-Za-z\s\.]+?)\s+(?:at|vs\.?|beats|beats-|defeats)\s+([A-Za-z\s\.]+?)(?:\s|$|,)',
        # "Team A - Team B"
        r'([A-Za-z\s\.]+?)\s+-\s+([A-Za-z\s\.]+?)(?:\s|$)',
        # "Team A and Team B"
        r'([A-Za-z\s\.]+?)\s+and\s+([A-Za-z\s\.]+?)(?:\s|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title_clean, re.IGNORECASE)
        if match:
            team1 = match.group(1).strip()
            team2 = match.group(2).strip()
            
            # Фильтруем слишком короткие или служебные слова
            if len(team1) > 2 and len(team2) > 2 and team1.lower() not in ['the', 'a', 'an', 'vs', 'at']:
                # Исправляем названия команд
                team1 = fix_team_name(team1, sport)
                team2 = fix_team_name(team2, sport)
                return team1, team2
    
    return None, None

def fetch_from_rss(league_key, league_config):
    """
    Парсит RSS-ленты и возвращает список матчей.
    """
    matches = []
    used_pairs = set()  # Для предотвращения дубликатов
    
    for url in league_config['sources']:
        try:
            logger.info(f"Парсинг {league_config['name']}: {url}")
            feed = feedparser.parse(url)
            
            for entry in feed.entries[:25]:  # Больше записей для поиска
                title = entry.get('title', '')
                home, away = extract_teams(title, league_key)
                
                if home and away and home != away:
                    # Проверяем на дубликаты
                    pair_key = f"{home}|{away}"
                    if pair_key in used_pairs:
                        continue
                    used_pairs.add(pair_key)
                    
                    # Получаем статистику команд
                    home_stats = get_team_stats(home, league_key)
                    away_stats = get_team_stats(away, league_key)
                    
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
                        'home_avg_goals': home_stats['goals_scored'],
                        'away_avg_goals': away_stats['goals_scored'],
                        'home_form': home_stats['form'],
                        'away_form': away_stats['form']
                    })
                    
                    logger.info(f"  ✅ {home} vs {away}: {total_prediction} (вероятность {win_prob}%)")
                    
        except Exception as e:
            logger.error(f"Ошибка при парсинге {url}: {e}")
    
    return matches[:20]  # Увеличили лимит

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ")
    logger.info("   Источник расписания: Yahoo Sports + альтернативные RSS")
    logger.info("=" * 60)
    
    all_matches = []
    
    for league_key, league_config in LEAGUES.items():
        logger.info(f"\n📋 Обработка {league_config['name']}")
        matches = fetch_from_rss(league_key, league_config)
        all_matches.extend(matches)
        logger.info(f"   Найдено уникальных матчей: {len(matches)}")
    
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
