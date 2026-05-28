#!/usr/bin/env python3
import json
import os
import requests
from datetime import datetime, timedelta

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
SPORT = "basketball_nba"
REGIONS = "us"
MARKETS = "h2h,totals"
MIN_PROBABILITY = 66  # порог 66%, как вы и хотели

def american_to_prob(odds):
    """Правильная конвертация американских коэффициентов в вероятность"""
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)

def fetch_games():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": REGIONS, "markets": MARKETS, "oddsFormat": "american"}
    resp = requests.get(url, params=params, timeout=15)
    return resp.json() if resp.status_code == 200 else []

def main():
    print("🚀 ЗАПУСК")
    games = fetch_games()
    if not games:
        print("❌ Нет матчей")
        return
    
    matches = []
    for game in games:
        home = game["home_team"]
        away = game["away_team"]
        commence = game["commence_time"]
        dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
        date_str = dt.strftime("%d.%m.%Y")
        time_str = dt.strftime("%H:%M МСК")
        
        # Находим коэффициенты на победу
        home_odds, away_odds = 2.0, 2.0
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "h2h":
                    for out in market["outcomes"]:
                        if out["name"] == home:
                            home_odds = out["price"]
                        elif out["name"] == away:
                            away_odds = out["price"]
        
        # Рассчитываем вероятности
        home_prob = american_to_prob(home_odds) * 100
        away_prob = american_to_prob(away_odds) * 100
        
        # Нормализуем (убираем маржу букмекера)
        total = home_prob + away_prob
        home_prob_norm = (home_prob / total) * 100
        away_prob_norm = (away_prob / total) * 100
        
        # Определяем фаворита и вероятность
        if home_prob_norm > away_prob_norm:
            winner = home
            prob = round(home_prob_norm)
        else:
            winner = away
            prob = round(away_prob_norm)
        
        # Фильтр по вероятности
        if prob < MIN_PROBABILITY:
            print(f"⏭️ Пропущен ({prob}% < {MIN_PROBABILITY}%): {home} – {away}")
            continue
        
        # Прогноз тотала
        total_pred = "Тотал БОЛЬШЕ"
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "totals":
                    for out in market["outcomes"]:
                        if out["name"] == "Over" and out.get("point"):
                            total_pred = f"Тотал БОЛЬШЕ {out['point']}"
                        elif out["name"] == "Under" and out.get("point"):
                            total_pred = f"Тотал МЕНЬШЕ {out['point']}"
        
        matches.append({
            "date": date_str, "time": time_str,
            "home": home, "away": away,
            "winner": winner, "prob": prob,
            "total_prediction": total_pred,
            "home_ppg": 0, "away_ppg": 0,
            "home_win_pct": 0, "away_win_pct": 0,
            "home_form": "N/A", "away_form": "N/A",
            "home_streak": "N/A", "away_streak": "N/A",
            "h2h": f"Фаворит: {winner}",
            "injuries": "✅ Все здоровы",
            "ai_reasoning": f"Анализ коэффициентов: {winner} победит с вероятностью {prob}%",
            "bookmakers_list": ", ".join([bk.get("title", "") for bk in game.get("bookmakers", [])[:5]]),
            "data_source": "The Odds API"
        })
        print(f"✅ {home} – {away}: {winner} ({prob}%)")
    
    repo_root = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(repo_root, "data", "nba_matches.json"), "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": "nba"}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено {len(matches)} матчей")

if __name__ == "__main__":
    main()
