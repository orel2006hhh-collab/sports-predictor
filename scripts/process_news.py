import json
import re
from datetime import datetime

def extract_injuries_from_news(news_items, team_keywords):
    """Извлекает новости о травмах для конкретных команд"""
    injuries = {}
    for team, keywords in team_keywords.items():
        injuries[team] = []
        for item in news_items:
            title = item.get('title', '')
            description = item.get('description', '')
            text = (title + ' ' + description).lower()
            
            # Проверяем, связана ли новость с командой
            if any(keyword.lower() in text for keyword in keywords):
                # Ищем слова о травмах
                if any(word in text for word in ['injury', 'injured', 'out', 'doubtful', 'questionable', 'травм', 'поврежд']):
                    injuries[team].append({
                        'title': title,
                        'link': item.get('link', ''),
                        'pubDate': item.get('pubDate', ''),
                        'summary': description[:200] if description else title
                    })
    return injuries

def main():
    # Ключевые слова для каждой команды
    team_keywords = {
        "Philadelphia Flyers": ["flyers", "philadelphia"],
        "Carolina Hurricanes": ["hurricanes", "carolina"],
        "Авангард": ["авангард", "avangard", "omsk"],
        "Локомотив": ["локомотив", "lokomotiv", "yaroslavl"],
        "Oklahoma City Thunder": ["thunder", "oklahoma"],
        "Los Angeles Lakers": ["lakers", "los angeles", "lebron"]
    }
    
    all_injuries = {}
    
    # Загружаем новости НХЛ
    try:
        with open('data/nhl-news.json', 'r', encoding='utf-8') as f:
            nhl_news = json.load(f)
            items = nhl_news.get('items', []) or nhl_news.get('rss', {}).get('channel', {}).get('item', [])
            injuries = extract_injuries_from_news(items, team_keywords)
            all_injuries.update(injuries)
    except Exception as e:
        print(f"Ошибка загрузки новостей НХЛ: {e}")
    
    # Загружаем новости НБА
    try:
        with open('data/nba-news.json', 'r', encoding='utf-8') as f:
            nba_news = json.load(f)
            items = nba_news.get('items', []) or nba_news.get('rss', {}).get('channel', {}).get('item', [])
            injuries = extract_injuries_from_news(items, team_keywords)
            for team, news in injuries.items():
                if team in all_injuries:
                    all_injuries[team].extend(news)
                else:
                    all_injuries[team] = news
    except Exception as e:
        print(f"Ошибка загрузки новостей НБА: {e}")
    
    # Сохраняем результат
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "injuries": all_injuries
    }
    
    with open('data/injuries.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Новости о травмах обновлены. Найдено {sum(len(v) for v in all_injuries.values())} записей")

if __name__ == "__main__":
    main()
