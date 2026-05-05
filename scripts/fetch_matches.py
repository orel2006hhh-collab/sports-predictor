import requests
import json
from datetime import datetime, timedelta

def fetch_nhl_matches():
    """Получение матчей НХЛ через CORS-прокси"""
    try:
        # Используем corsfix для обхода CORS [citation:1]
        proxy_url = "https://corsfix.com/"
        espn_url = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"
        response = requests.get(proxy_url + espn_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            matches = []
            for event in data.get('events', []):
                matches.append({
                    'sport': 'nhl',
                    'home': event['competitions'][0]['competitors'][0]['team']['displayName'],
                    'away': event['competitions'][0]['competitors'][1]['team']['displayName'],
                    'date': event['date'],
                    'series': event.get('name', 'НХЛ · Плей-офф')
                })
            return matches
    except Exception as e:
        print(f"Ошибка загрузки НХЛ: {e}")
    return []

def fetch_nba_matches():
    """Получение матчей НБА через CORS-прокси"""
    try:
        proxy_url = "https://corsfix.com/"
        espn_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        response = requests.get(proxy_url + espn_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            matches = []
            for event in data.get('events', []):
                matches.append({
                    'sport': 'nba',
                    'home': event['competitions'][0]['competitors'][0]['team']['displayName'],
                    'away': event['competitions'][0]['competitors'][1]['team']['displayName'],
                    'date': event['date'],
                    'series': 'НБА · Плей-офф'
                })
            return matches
    except Exception as e:
        print(f"Ошибка загрузки НБА: {e}")
    return []

def main():
    print("🚀 Начинаю обновление данных о матчах...")
    
    all_matches = []
    all_matches.extend(fetch_nhl_matches())
    all_matches.extend(fetch_nba_matches())
    
    # Добавляем КХЛ, МХЛ, ВХЛ — пока из локального источника
    # В будущем можно добавить парсинг с сайтов лиг
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Обновлено! Найдено матчей: {len(all_matches)}")

if __name__ == "__main__":
    main()
