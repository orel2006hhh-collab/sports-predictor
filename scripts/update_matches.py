#!/usr/bin/env python3
"""
NBA прогнозы + реальная статистика из NBA API
"""

import json
import os
import requests
from datetime import datetime, timedelta
from nba_api.stats.endpoints import leaguegamefinder
import pandas as pd

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
SPORT = "basketball_nba"

def get_team_recent_stats(team_abbreviation, days_back=14):
    """Получить статистику команды за последние игры из NBA API"""
    try:
        gamefinder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=team_abbreviation,
            date_from_nullable=(datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        )
        games = gamefinder.get_data_frames()[0]
        
        if games.empty:
            return None
        
        # Сортируем по дате
        games = games.sort_values('GAME_DATE', ascending=False)
        last_5 = games.head(5)
        
        wins = len(last_5[last_5['WL'] == 'W'])
        losses = len(last_5[last_5['WL'] == 'L'])
        ppg = round(last_5['PTS'].mean(), 1)
        
        # Серия
        streak = 0
        for _, game in last_5.iterrows():
            if game['WL'] == 'W':
                streak = streak + 1 if streak >= 0 else 1
            else:
                streak = streak - 1 if streak <= 0 else -1
        
        return {
            "form": f"{wins}-{losses}",
            "streak": streak,
            "ppg": ppg,
            "win_pct": round(wins / 5 * 100) if (wins + losses) == 5 else 0
        }
    except Exception as e:
        print(f"    Ошибка NBA API: {e}")
        return None

def get_upcoming_games():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h", "oddsFormat": "american"}
    resp = requests.get(url, params=params, timeout=15)
    return resp.json() if resp.status_code == 200 else []

def american_to_prob(odds):
    return 100 / (odds + 100) * 100 if odds > 0 else abs(odds) / (abs(odds) + 100) * 100

def main():
    print("🏀 NBA прогнозы + NBA API статистика")
    
    games = get_upcoming_games()
    if not games:
        print("Нет данных")
        return
    
    matches = []
    for game in games:
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue
        
        # Коэффициенты
        home_odds, away_odds = None, None
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "h2h":
                    for out in market["outcomes"]:
                        if out["name"] == home:
                            home_odds = out["price"]
                        elif out["name"] == away:
                            away_odds = out["price"]
                    break
            if home_odds and away_odds:
                break
        
        if not home_odds or not away_odds:
            continue
        
        # Вероятность
        home_prob = american_to_prob(home_odds)
        away_prob = american_to_prob(away_odds)
        total = home_prob + away_prob
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100
        
        winner = home if home_prob > away_prob else away
        winner_prob = round(max(home_prob, away_prob))
        
        # Статистика из NBA API
        print(f"📊 Статистика: {home} vs {away}")
        home_stats = get_team_recent_stats(home)
        away_stats = get_team_recent_stats(away)
        
        match = {
            "date": datetime.now().strftime("%d.%m.%Y"),
            "time": "04:30 МСК",
            "home": home,
            "away": away,
            "winner": winner,
            "probability": winner_prob,
            "home_ppg": home_stats["ppg"] if home_stats else None,
            "away_ppg": away_stats["ppg"] if away_stats else None,
            "home_form": home_stats["form"] if home_stats else None,
            "away_form": away_stats["form"] if away_stats else None,
            "home_streak": home_stats["streak"] if home_stats else None,
            "away_streak": away_stats["streak"] if away_stats else None,
        }
        matches.append(match)
        print(f"  ✅ {home}: {home_stats['form'] if home_stats else 'нет данных'}, PPG {home_stats['ppg'] if home_stats else '?'}")
        print(f"  ✅ {away}: {away_stats['form'] if away_stats else 'нет данных'}, PPG {away_stats['ppg'] if away_stats else '?'}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated": datetime.now().isoformat()}, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Сохранено {len(matches)} матчей")

if __name__ == "__main__":
    main()
