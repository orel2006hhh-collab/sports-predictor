import os
import requests

API_KEY = os.environ.get("ODDS_API_KEY")
url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
params = {
    "apiKey": API_KEY,
    "regions": "us",
    "markets": "h2h",
    "oddsFormat": "american"
}

resp = requests.get(url, params=params)
print(f"Статус: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"Найдено матчей: {len(data)}")
    for game in data[:3]:
        print(f"  - {game.get('home_team')} vs {game.get('away_team')}")
else:
    print(f"Ошибка: {resp.text}")
