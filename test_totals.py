import os
import requests
import json

API_KEY = os.environ.get("ODDS_API_KEY")
print(f"API_KEY: {'есть' if API_KEY else 'НЕТ!'}")

if not API_KEY:
    print("❌ ODDS_API_KEY не найден")
    exit(1)

url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
params = {
    "apiKey": API_KEY,
    "regions": "us,uk,eu",
    "markets": "totals",  # только тоталы
    "oddsFormat": "american"
}

try:
    resp = requests.get(url, params=params, timeout=15)
    print(f"Статус: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"Найдено матчей: {len(data)}")
        
        for game in data[:3]:
            print(f"\n📋 {game.get('home_team')} vs {game.get('away_team')}")
            
            for bk in game.get("bookmakers", [])[:3]:
                print(f"   Букмекер: {bk.get('title')}")
                for market in bk.get("markets", []):
                    if market["key"] == "totals":
                        for outcome in market["outcomes"]:
                            point = outcome.get("point")
                            name = outcome.get("name")
                            price = outcome.get("price")
                            print(f"      {name} {point}: {price} (амер.)")
    else:
        print(f"Ошибка: {resp.text[:300]}")
        
except Exception as e:
    print(f"Исключение: {e}")
