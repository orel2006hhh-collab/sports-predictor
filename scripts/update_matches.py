#!/usr/bin/env python3
import json
import os
import requests
from datetime import datetime, timedelta

# Ключ API из секретов GitHub
API_KEY = os.environ.get("ODDS_API_KEY")
SPORT = "basketball_nba"  # для NBA
REGIONS = "us"
MARKETS = "h2h"  # только исход матча (победа)
ODDS_FORMAT = "american"

def fetch_games():
    """Получить предстоящие матчи из The Odds API"""
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT,
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка API: {response.status_code}")
            return []
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

def american_to_prob(american_odds):
    """Конвертировать американский коэффициент в вероятность (%)"""
    if american_odds > 0:
        return 100 / (american_odds + 100) * 100
    else:
        return abs(american_odds) / (abs(american_odds) + 100) * 100

def main():
    print("NBA прогнозы: обновление...")
    games = fetch_games()
    if not games:
        print("Нет данных")
        return

    matches = []
    for game in games:
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue

        # Определяем коэффициенты на победу
        home_odds = None
        away_odds = None
        for bookmaker in game.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market["key"] == "h2h":
                    for outcome in market["outcomes"]:
                        if outcome["name"] == home:
                            home_odds = outcome["price"]
                        elif outcome["name"] == away:
                            away_odds = outcome["price"]
                    break
            if home_odds and away_odds:
                break

        if not home_odds or not away_odds:
            continue

        home_prob = american_to_prob(home_odds)
        away_prob = american_to_prob(away_odds)
        # Нормируем, чтобы сумма была 100%
        total = home_prob + away_prob
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100

        # Фаворит
        if home_prob > away_prob:
            winner = home
            winner_prob = round(home_prob)
        else:
            winner = away
            winner_prob = round(away_prob)

        # Дата и время матча (московское время +3)
        commence = game.get("commence_time")
        if commence:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
            date_str = dt.strftime("%d.%m.%Y")
            time_str = dt.strftime("%H:%M")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "00:00"

        matches.append({
            "date": date_str,
            "time": time_str,
            "home": home,
            "away": away,
            "winner": winner,
            "probability": winner_prob,
            "source": "The Odds API"
        })

    # Сохраняем в data/matches.json
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "last_updated": datetime.now().isoformat()}, f, indent=2, ensure_ascii=False)

    print(f"Сохранено {len(matches)} матчей")

if __name__ == "__main__":
    main()
