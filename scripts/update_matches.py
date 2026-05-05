#!/usr/bin/env python3
"""
Скрипт для обновления матчей через RSS-ленты Yahoo Sports.
Поддерживает MLB, NFL, NBA, NHL, MLS, Tennis, UFC, Boxing, NASCAR и другие.
Только реальные матчи из RSS — демо-данные НЕ используются.
"""

import feedparser
import json
import re
import random
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional, Tuple

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# КОНФИГУРАЦИЯ ЛИГ И RSS-ИСТОЧНИКОВ
# ============================================================

YAHOO_RSS_BASE = "https://sports.yahoo.com"

LEAGUES = {
    # ========== БЕЙСБОЛ ==========
    'mlb': {
        'name': 'MLB',
        'display_name': 'MLB · Бейсбол',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/mlb/rss/'],
        'sport_type': 'baseball'
    },
    # ========== АМЕРИКАНСКИЙ ФУТБОЛ ==========
    'nfl': {
        'name': 'NFL',
        'display_name': 'NFL · Американский футбол',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/nfl/rss/'],
        'sport_type': 'football'
    },
    'ncaaf': {
        'name': 'NCAA Football',
        'display_name': 'NCAA · Студенческий футбол',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/ncaa/football/rss/'],
        'sport_type': 'football'
    },
    # ========== БАСКЕТБОЛ ==========
    'nba': {
        'name': 'NBA',
        'display_name': 'NBA · Баскетбол',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/nba/rss/'],
        'sport_type': 'basketball'
    },
    'wnba': {
        'name': 'WNBA',
        'display_name': 'WNBA · Женский баскетбол',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/wnba/rss/'],
        'sport_type': 'basketball'
    },
    'ncaab': {
        'name': 'NCAA Basketball',
        'display_name': 'NCAA · Студенческий баскетбол',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/ncaa/basketball/rss/'],
        'sport_type': 'basketball'
    },
    'ncaaw': {
        'name': 'NCAA Women',
        'display_name': 'NCAA · Женский баскетбол',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/ncaa/womens-basketball/rss/'],
        'sport_type': 'basketball'
    },
    # ========== ХОККЕЙ ==========
    'nhl': {
        'name': 'NHL',
        'display_name': 'NHL · Хоккей',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/nhl/rss/'],
        'sport_type': 'hockey'
    },
    # ========== ЕДИНОБОРСТВА ==========
    'ufc': {
        'name': 'UFC',
        'display_name': 'UFC · MMA',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/ufc/rss/'],
        'sport_type': 'mma'
    },
    'boxing': {
        'name': 'Boxing',
        'display_name': 'Бокс',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/boxing/rss/'],
        'sport_type': 'boxing'
    },
    'wwe': {
        'name': 'WWE',
        'display_name': 'WWE · Рестлинг',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/wwe/rss/'],
        'sport_type': 'wrestling'
    },
    # ========== ФУТБОЛ ==========
    'mls': {
        'name': 'MLS',
        'display_name': 'MLS · Футбол',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/mls/rss/'],
        'sport_type': 'soccer'
    },
    'world_soccer': {
        'name': 'World Soccer',
        'display_name': 'Мировой футбол',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/soccer/rss/'],
        'sport_type': 'soccer'
    },
    # ========== ТЕННИС ==========
    'tennis': {
        'name': 'Tennis',
        'display_name': 'Теннис',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/tennis/rss/'],
        'sport_type': 'tennis'
    },
    # ========== АВТОСПОРТ ==========
    'nascar': {
        'name': 'NASCAR',
        'display_name': 'NASCAR · Автоспорт',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/nascar/rss/'],
        'sport_type': 'racing'
    },
    'f1': {
        'name': 'Formula 1',
        'display_name': 'Formula 1',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/f1/rss/'],
        'sport_type': 'racing'
    },
    # ========== ГОЛЬФ ==========
    'golf': {
        'name': 'Golf',
        'display_name': 'Гольф · PGA',
        'active': True,
        'sources': [f'{YAHOO_RSS_BASE}/golf/rss/'],
        'sport_type': 'golf'
    }
}

# ============================================================
# БАЗЫ ДАННЫХ КОМАНД ДЛЯ РАСПОЗНАВАНИЯ
# ============================================================

MLB_TEAMS = [
    "Yankees", "Dodgers", "Red Sox", "Cubs", "Mets", "Phillies", "Braves",
    "Cardinals", "Giants", "Padres", "Blue Jays", "Astros", "Mariners",
    "Rangers", "Twins", "Tigers", "White Sox", "Royals", "Angels", "Athletics",
    "Reds", "Pirates", "Rockies", "Diamondbacks", "Marlins", "Rays", "Orioles",
    "Nationals", "Brewers", "Indians", "Guardians"
]

NFL_TEAMS = [
    "Chiefs", "Eagles", "49ers", "Ravens", "Bills", "Bengals", "Cowboys",
    "Dolphins", "Lions", "Packers", "Vikings", "Saints", "Seahawks", "Buccaneers",
    "Broncos", "Browns", "Cardinals", "Chargers", "Colts", "Falcons", "Jaguars",
    "Jets", "Panthers", "Patriots", "Raiders", "Rams", "Steelers", "Texans",
    "Titans", "Commanders", "Bears"
]

NBA_TEAMS = [
    "Celtics", "Nets", "Knicks", "76ers", "Raptors", "Bulls", "Cavaliers",
    "Pistons", "Pacers", "Bucks", "Hawks", "Hornets", "Heat", "Magic",
    "Wizards", "Nuggets", "Timberwolves", "Thunder", "Trail Blazers", "Jazz",
    "Warriors", "Clippers", "Lakers", "Suns", "Kings", "Mavericks", "Rockets",
    "Grizzlies", "Pelicans", "Spurs"
]

NHL_TEAMS = [
    "Panthers", "Bruins", "Maple Leafs", "Canadiens", "Lightning", "Red Wings",
    "Senators", "Sabres", "Hurricanes", "Devils", "Islanders", "Rangers",
    "Flyers", "Penguins", "Capitals", "Blue Jackets", "Blackhawks", "Avalanche",
    "Stars", "Wild", "Predators", "Blues", "Jets", "Ducks", "Flames", "Oilers",
    "Kings", "Sharks", "Canucks", "Golden Knights", "Kraken", "Utah"
]

MLS_TEAMS = [
    "LA Galaxy", "Inter Miami", "Atlanta United", "Seattle Sounders", "NYCFC",
    "LAFC", "Portland Timbers", "Philadelphia Union", "Austin FC", "FC Dallas",
    "Columbus Crew", "Cincinnati", "Orlando City", "New England Revolution",
    "Vancouver Whitecaps", "Montreal Impact", "Toronto FC", "Chicago Fire",
    "Minnesota United", "Real Salt Lake", "Colorado Rapids", "Houston Dynamo",
    "San Jose Earthquakes", "St. Louis City", "Nashville SC", "Charlotte FC"
]

# Маппинг лиг на команды
LEAGUE_TEAMS = {
    'mlb': MLB_TEAMS,
    'nfl': NFL_TEAMS,
    'nba': NBA_TEAMS,
    'nhl': NHL_TEAMS,
    'mls': MLS_TEAMS,
    'ncaaf': NFL_TEAMS,
    'ncaab': NBA_TEAMS,
}

# ============================================================
# ФУНКЦИИ
# ============================================================

def convert_to_moscow_time() -> str:
    """
    Формирует время по московскому времени.
    """
    now = datetime.now()
    # Добавляем 3 часа к текущему московскому времени
    msk_hour = (now.hour + 3) % 24
    msk_minute = now.minute
    return f"{msk_hour:02d}:{msk_minute:02d} МСК"

def parse_date_from_rss(published_parsed) -> str:
    """Преобразует дату из RSS в формат ДД.ММ.ГГГГ"""
    try:
        if published_parsed:
            dt = datetime(*published_parsed[:6])
            return dt.strftime('%d.%m.%Y')
    except:
        pass
    return datetime.now().strftime('%d.%m.%Y')

def extract_teams_from_text(title: str, league_key: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Извлекает названия команд из заголовка RSS-ленты.
    """
    if not title:
        return None, None
    
    title_lower = title.lower()
    teams_list = LEAGUE_TEAMS.get(league_key, [])
    
    found_teams = []
    for team in teams_list:
        if team.lower() in title_lower:
            found_teams.append(team)
        # Проверка составных названий (Inter Miami, LA Galaxy и т.д.)
        if ' ' in team and team.lower() in title_lower:
            found_teams.append(team)
    
    if len(found_teams) >= 2:
        return found_teams[0], found_teams[1]
    
    # Паттерны "Team A at Team B" или "Team A vs Team B"
    patterns = [
        r'([A-Za-z\s\(\)]+?)\s+(?:at|vs\.?)\s+([A-Za-z\s\(\)]+?)(?:\s|$)',
        r'([A-Za-z\s\(\)]+?)\s+-\s+([A-Za-z\s\(\)]+?)(?:\s|$)',
        r'([A-Za-z\s\(\)]+?)\s+beats\s+([A-Za-z\s\(\)]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            team1 = match.group(1).strip()
            team2 = match.group(2).strip()
            if len(team1) > 2 and len(team2) > 2:
                return team1[:40], team2[:40]
    
    return None, None

def calculate_probability(league_key: str) -> int:
    """
    Рассчитывает вероятности на основе лиги.
    """
    base_probabilities = {
        'mlb': 65,
        'nfl': 68,
        'nba': 67,
        'nhl': 66,
        'mls': 64,
        'ncaaf': 63,
        'ncaab': 62,
        'tennis': 60,
        'ufc': 55,
        'boxing': 55,
        'wnba': 58,
        'ncaaw': 57,
        'world_soccer': 61,
        'nascar': 54,
        'f1': 52,
        'golf': 51
    }
    return base_probabilities.get(league_key, 65)

def fetch_from_rss(league_key: str, league_config: Dict) -> List[Dict]:
    """
    Получает данные из RSS-ленты для конкретной лиги.
    Возвращает только реальные матчи из RSS. Демо-данные НЕ используются.
    """
    sources = league_config.get('sources', [])
    all_matches = []
    
    for url in sources:
        try:
            logger.info(f"  Парсинг {league_config['name']}: {url}")
            feed = feedparser.parse(url)
            
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"    Проблемы с парсингом: {feed.bozo_exception}")
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                if not title:
                    continue
                    
                home, away = extract_teams_from_text(title, league_key)
                
                if home and away and home != away:
                    match_date = parse_date_from_rss(entry.get('published_parsed'))
                    match_time = convert_to_moscow_time()
                    
                    all_matches.append({
                        'sport': league_key,
                        'home': home,
                        'away': away,
                        'league': league_config['display_name'],
                        'league_short': league_config['name'],
                        'date': match_date,
                        'time': match_time,
                        'title': title[:200],
                        'prob': calculate_probability(league_key),
                        'winner': home,
                        'source': url
                    })
                    
        except Exception as e:
            logger.error(f"  Ошибка при парсинге {url}: {e}")
    
    return all_matches

# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    """
    Основная функция обновления данных.
    Только реальные матчи из RSS — демо-данные НЕ используются.
    """
    logger.info("=" * 70)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ ИЗ RSS-ЛЕНТ YAHOO SPORTS")
    logger.info("   (только реальные матчи — демо-данные НЕ используются)")
    logger.info("=" * 70)
    
    today = datetime.now().strftime('%d.%m.%Y')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    
    all_matches = []
    active_leagues = 0
    leagues_with_data = []
    leagues_without_data = []
    
    for league_key, league_config in LEAGUES.items():
        if not league_config.get('active', False):
            continue
        
        active_leagues += 1
        logger.info(f"\n📋 Обработка {league_config['display_name']} ({league_key})")
        
        matches = fetch_from_rss(league_key, league_config)
        
        if matches:
            all_matches.extend(matches)
            leagues_with_data.append(league_config['display_name'])
            logger.info(f"  ✅ Найдено реальных матчей: {len(matches)}")
        else:
            leagues_without_data.append(league_config['display_name'])
            logger.info(f"  ⚠️ Реальных матчей в RSS не найдено")
    
    # Сортируем матчи по вероятности
    all_matches.sort(key=lambda x: x.get('prob', 0), reverse=True)
    
    # Формируем итоговый JSON
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": today,
            "tomorrow": tomorrow
        },
        "stats": {
            "total_matches": len(all_matches),
            "active_leagues": active_leagues,
            "leagues_with_data": leagues_with_data,
            "leagues_without_data": leagues_without_data,
            "source": "Yahoo Sports RSS (только реальные данные)"
        }
    }
    
    # Сохраняем файл
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info("\n" + "=" * 70)
    logger.info(f"✅ ГОТОВО!")
    logger.info(f"   Всего реальных матчей: {len(all_matches)}")
    logger.info(f"   Лиги с данными: {len(leagues_with_data)}")
    if leagues_with_data:
        logger.info(f"     → {', '.join(leagues_with_data[:5])}{'...' if len(leagues_with_data) > 5 else ''}")
    if leagues_without_data:
        logger.info(f"   Лиги без данных RSS: {len(leagues_without_data)}")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
