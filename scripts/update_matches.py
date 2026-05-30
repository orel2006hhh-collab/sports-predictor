#!/usr/bin/env python3
import json
import os
import requests
from datetime import datetime, timedelta

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

SPORT = "basketball_nba"
REGIONS = "us,uk,eu"
MARKETS = "h2h,totals"
MIN_PROBABILITY = 55

def american_to_prob(odds):
    if odds > 0:
        return 100 / (odds + 100) * 100
    else:
        return abs(odds) / (abs(odds) + 100) * 100

def fetch_upcoming_games():
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": REGIONS, "markets": MARKETS, "oddsFormat": "american"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

def get_bookmakers_list(bookmakers):
    if not bookmakers:
        return "Нет данных"
    names = [bk.get("title", "") for bk in bookmakers[:5] if bk.get("title")]
    return ", ".join(names) if names else "Букмекеры"

def get_total_line(bookmakers):
    for bk in bookmakers:
        for market in bk.get("markets", []):
            if market["key"] == "totals":
                for outcome in market["outcomes"]:
                    if outcome.get("point"):
                        return outcome["point"]
    return 225.5

def update_matches():
    print("Получаем матчи...")
    games = fetch_upcoming_games()
    if not games:
        print("Нет данных")
        return
    
    matches = []
    
    for game in games:
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue
        
        commence = game.get("commence_time")
        if commence:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
            date_str = dt.strftime("%d.%m.%Y")
            time_str = dt.strftime("%H:%M")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "04:30"
        
        bookmakers_list = get_bookmakers_list(game.get("bookmakers", []))
        total_line = get_total_line(game.get("bookmakers", []))
        
        home_odds, away_odds = 2.0, 2.0
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "h2h":
                    for out in market["outcomes"]:
                        if out["name"] == home:
                            home_odds = out["price"]
                        elif out["name"] == away:
                            away_odds = out["price"]
                    break
        
        home_prob = american_to_prob(home_odds)
        away_prob = american_to_prob(away_odds)
        total_prob = home_prob + away_prob
        home_prob = home_prob / total_prob * 100
        away_prob = away_prob / total_prob * 100
        
        prob = round(max(home_prob, away_prob))
        winner = home if home_prob > away_prob else away
        
        if prob < MIN_PROBABILITY:
            continue
        
        match = {
            "date": date_str,
            "time": time_str,
            "home": home,
            "away": away,
            "winner": winner,
            "prob": prob,
            "total_prediction": f"Тотал БОЛЬШЕ {total_line}",
            "bookmakers_list": bookmakers_list,
            "ai_reasoning": f"Прогноз на основе коэффициентов: {winner} ({prob}%)",
            "home_form": "3-2",
            "away_form": "2-3",
            "home_ppg": 115.5,
            "away_ppg": 110.2,
            "home_win_pct": 60,
            "away_win_pct": 40,
            "home_odds": round(1 / (home_prob / 100), 2),
            "away_odds": round(1 / (away_prob / 100), 2)
        }
        matches.append(match)
        print(f"✅ {home} vs {away}: {winner} ({prob}%)")
    
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    print(f"Сохранено {len(matches)} матчей")

def main():
    print("=== ЗАПУСК ОБНОВЛЕНИЯ ===")
    update_matches()
    print("=== ГОТОВО ===")

if __name__ == "__main__":
    main()
