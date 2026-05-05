#!/usr/bin/env python3
"""
Скрипт для обновления матчей через парсинг RSS-лент.
Запускается ежедневно через GitHub Actions.
"""

import feedparser
import json
import re
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Базовые команды для распознавания в заголовках
NHL_TEAMS = [
    "Panthers", "Bruins", "Maple Leafs", "Canadiens", "Lightning", "Red Wings",
    "Senators", "Sabres", "Hurricanes", "Devils", "Islanders", "Rangers",
    "Flyers", "Penguins", "Capitals", "Blue Jackets", "Blackhawks", "Avalanche",
    "Stars", "Wild", "Predators", "Blues", "Jets", "Ducks", "Flames", "Oilers",
    "Kings", "Sharks", "Canucks", "Golden Knights", "Kraken", "Utah"
]

NBA_TEAMS = [
    "Celtics", "Nets", "Knicks", "76ers", "Raptors", "Bulls", "Cavaliers",
    "Pistons", "Pacers", "Bucks", "Hawks", "Hornets", "Heat", "Magic",
    "Wizards", "Nuggets", "Timberwolves", "Thunder", "Trail Blazers", "Jazz",
    "Warriors", "Clippers", "Lakers", "Suns", "Kings", "Mavericks", "Rockets",
    "Grizzlies", "Pelicans", "Spurs"
]

def parse_date_from_rss(published_str):
    """Преобразует дату из RSS в формат ДД.ММ.ГГГГ"""
    try:
        # feedparser возвращает структурированную дату
        if hasattr(published_str, 'tm_tuple'):
            dt = datetime(*published_str.tm_tuple[:6])
            return dt.strftime('%d.%m.%Y')
    except:
        pass
    return datetime.now().strftime('%d.%m.%Y')

def extract_teams_from_text(text):
    """Извлекает названия команд из текста"""
    text = text.lower()
    found_teams = []
    
    # Сначала проверяем НХЛ
    for team in NHL_TEAMS:
        if team.lower() in text:
            found_teams.append(team)
    
    # Затем НБА
    if len(found_teams) < 2:
        for team in NBA_TEAMS:
            if team.lower() in text:
                found_teams.append(team)
    
    if len(found_teams) >= 2:
        return found_teams[0], found_teams[1]
    return None, None

def get_sample_matches(sport):
    """Возвращает демо-матчи на случай, если RSS не дал результатов"""
    today = datetime.now().strftime('%d.%m.%Y')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    
    if sport == 'nhl':
        return [
            {'sport': 'nhl', 'home': 'Florida Panthers', 'away': 'Boston Bruins', 
             'league': 'НХЛ', 'date': today, 'time': '02:00 МСК', 'prob': 72, 'winner': 'Florida Panthers'},
            {'sport': 'nhl', 'home': 'Edmonton Oilers', 'away': 'Vegas Golden Knights', 
             'league': 'НХЛ', 'date': tomorrow, 'time': '05:00 МСК', 'prob': 68, 'winner': 'Edmonton Oilers'}
        ]
    elif sport == 'nba':
        return [
            {'sport': 'nba', 'home': 'Los Angeles Lakers', 'away': 'Golden State Warriors', 
             'league': 'НБА', 'date': today, 'time': '05:30 МСК', 'prob': 65, 'winner': 'Los Angeles Lakers'},
            {'sport': 'nba', 'home': 'Boston Celtics', 'away': 'Miami Heat', 
             'league': 'НБА', 'date': tomorrow, 'time': '03:00 МСК', 'prob': 70, 'winner': 'Boston Celtics'}
        ]
    return []

def fetch_nhl_from_rss():
    """Получает данные НХЛ из RSS-лент"""
    sources = [
        'https://sports.yahoo.com/nhl/rss/',
        'https://www.nhl.com/rss/news'
    ]
    
    all_items = []
    for url in sources:
        try:
            logger.info(f"  Парсинг НХЛ: {url}")
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                home, away = extract_teams_from_text(title)
                if home and away:
                    all_items.append({
                        'sport': 'nhl',
                        'home': home,
                        'away': away,
                        'league': 'НХЛ',
                        'date': parse_date_from_rss(entry.get('published_parsed', datetime.now())),
                        'time': '19:00 МСК',
                        'title': title[:100],
                        'prob': 68,
                        'winner': home
                    })
        except Exception as e:
            logger.warning(f"  Ошибка при парсинге {url}: {e}")
    
    return all_items[:8]  # Не более 8 матчей

def fetch_nba_from_rss():
    """Получает данные НБА из RSS-лент"""
    sources = [
        'https://sports.yahoo.com/nba/rss/',
        'https://www.espn.com/espn/rss/nba/news'
    ]
    
    all_items = []
    for url in sources:
        try:
            logger.info(f"  Парсинг НБА: {url}")
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = entry.get('title', '')
                home, away = extract_teams_from_text(title)
                if home and away:
                    all_items.append({
                        'sport': 'nba',
                        'home': home,
                        'away': away,
                        'league': 'НБА',
                        'date': parse_date_from_rss(entry.get('published_parsed', datetime.now())),
                        'time': '03:00 МСК',
                        'title': title[:100],
                        'prob': 66,
                        'winner': home
                    })
        except Exception as e:
            logger.warning(f"  Ошибка при парсинге {url}: {e}")
    
    return all_items[:8]

def main():
    """Основная функция"""
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ ИЗ RSS")
    logger.info("=" * 50)
    
    today = datetime.now().strftime('%d.%m.%Y')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    
    # Получаем матчи
    nhl_matches = fetch_nhl_from_rss()
    nba_matches = fetch_nba_from_rss()
    
    # Если RSS не дал результатов — используем демо-матчи
    if not nhl_matches:
        logger.warning("⚠️ RSS для НХЛ не дал результатов. Использую демо-матчи.")
        nhl_matches = get_sample_matches('nhl')
    
    if not nba_matches:
        logger.warning("⚠️ RSS для НБА не дал результатов. Использую демо-матчи.")
        nba_matches = get_sample_matches('nba')
    
    all_matches = nhl_matches + nba_matches
    
    # Формируем итоговый JSON
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": today,
            "tomorrow": tomorrow
        },
        "source": "RSS Feeds (Yahoo Sports, NHL.com, ESPN)"
    }
    
    # Сохраняем файл
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ ГОТОВО! Сохранено матчей: {len(all_matches)}")
    logger.info(f"   - НХЛ: {len(nhl_matches)}")
    logger.info(f"   - НБА: {len(nba_matches)}")

if __name__ == "__main__":
    main()
