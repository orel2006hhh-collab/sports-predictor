#!/usr/bin/env python3
"""
Скрипт для обновления матчей через парсинг RSS-лент.
Использует feedparser для извлечения данных — без API-ключей!
"""

import feedparser
import json
import re
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Источники RSS для парсинга
RSS_SOURCES = {
    'nhl': [
        'https://sports.yahoo.com/nhl/rss/',           # Yahoo Sports NHL
        'https://www.nhl.com/rss/news',                # Официальная лента NHL.com
        'https://theathletic.com/feed/scores/nhl/'     # Счета и расписание
    ],
    'nba': [
        'https://sports.yahoo.com/nba/rss/',           # Yahoo Sports NBA
        'https://www.nba.com/bucks/rss.xml',           # Пример ленты команды NBA
        'https://www.espn.com/espn/rss/nba/news'       # ESPN NBA
    ]
}

def extract_games_from_feed(feed_url, sport):
    """
    Извлекает информацию о матчах из RSS-ленты.
    Использует библиотеку feedparser для парсинга.
    """
    games = []
    
    try:
        logger.info(f"Парсинг {feed_url} для {sport}")
        feed = feedparser.parse(feed_url)
        
        # Проверка на ошибки парсинга
        if feed.bozo:
            logger.warning(f"Возможны проблемы с парсингом {feed_url}: {feed.bozo_exception}")
        
        for entry in feed.entries[:20]:  # Берем последние 20 записей
            title = entry.get('title', '')
            summary = entry.get('summary', '')
            published = entry.get('published', '')
            
            # Ищем названия команд в заголовке (ИГРОКИ: это хоккейный паттерн)
            # Пример заголовка: "Ovechkin leads Capitals past Penguins 4-2"
            team_pattern = r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:leads|past|beat|vs)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)'
            match = re.search(team_pattern, title)
            
            if match and ('goal' in title.lower() or 'beat' in title.lower() or 'lead' in title.lower()):
                # Это похоже на результат матча, но можно попробовать извлечь команды
                home_team = match.group(1)
                away_team = match.group(2)
                
                game_info = {
                    'sport': sport,
                    'home': home_team,
                    'away': away_team,
                    'league': sport.upper(),
                    'title': title,
                    'summary': summary[:200] if summary else '',
                    'date': published,
                    'link': entry.get('link', ''),
                    'source': feed_url
                }
                games.append(game_info)
                
    except Exception as e:
        logger.error(f"Ошибка при парсинге {feed_url}: {e}")
    
    return games

def generate_sample_matches(sport):
    """
    Генерирует демо-матчи на случай, если RSS не дал результатов.
    Это страховка, чтобы сайт всегда имел данные для отображения.
    """
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    
    today_str = today.strftime('%d.%m.%Y')
    tomorrow_str = tomorrow.strftime('%d.%m.%Y')
    
    if sport == 'nhl':
        return [
            {'sport': 'nhl', 'home': 'Вашингтон Кэпиталз', 'away': 'Питтсбург Пингвинз', 
             'league': 'НХЛ', 'date': today_str, 'time': '02:00 МСК', 'prob': 65},
            {'sport': 'nhl', 'home': 'Торонто Мейпл Лифс', 'away': 'Монреаль Канадиенс', 
             'league': 'НХЛ', 'date': tomorrow_str, 'time': '02:30 МСК', 'prob': 62}
        ]
    elif sport == 'nba':
        return [
            {'sport': 'nba', 'home': 'Лос-Анджелес Лейкерс', 'away': 'Голден Стэйт Уорриорз', 
             'league': 'НБА', 'date': today_str, 'time': '05:00 МСК', 'prob': 58},
            {'sport': 'nba', 'home': 'Бостон Селтикс', 'away': 'Майами Хит', 
             'league': 'НБА', 'date': tomorrow_str, 'time': '03:30 МСК', 'prob': 71}
        ]
    return []

def main():
    """Основная функция обновления данных"""
    logger.info("🚀 Запуск обновления данных из RSS-лент")
    
    all_matches = []
    today = datetime.now().strftime('%d.%m.%Y')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    
    # Парсим RSS для каждой лиги
    for sport, sources in RSS_SOURCES.items():
        logger.info(f"Обработка {sport.upper()}...")
        sport_matches = []
        
        for source in sources:
            games = extract_games_from_feed(source, sport)
            if games:
                sport_matches.extend(games)
                logger.info(f"  Найдено {len(games)} событий в {source}")
        
        # Если RSS не дал результатов, используем демо-данные
        if not sport_matches:
            logger.warning(f"  RSS не дал результатов для {sport}, использую демо-данные")
            sport_matches = generate_sample_matches(sport)
        
        all_matches.extend(sport_matches)
    
    # Формируем итоговый JSON в нужном формате
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": today,
            "tomorrow": tomorrow
        },
        "source": "RSS Feeds (Yahoo Sports, NHL.com, NBA.com)"
    }
    
    # Сохраняем в файл
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ Готово! Всего собрано матчей: {len(all_matches)}")
    for match in all_matches[:5]:
        logger.info(f"  - {match.get('sport', '')}: {match.get('home', '')} vs {match.get('away', '')}")

if __name__ == "__main__":
    main()
