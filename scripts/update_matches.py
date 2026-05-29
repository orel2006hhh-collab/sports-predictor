#!/usr/bin/env python3
"""
NBA прогнозы + статистика через fastbreak
"""

import json
import os
import requests
import asyncio
from datetime import datetime, timedelta
from fastbreak import NBAClient

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
SPORT = "basketball_nba"

def get_upcoming_games():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h", "oddsFormat": "american"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        return resp.json() if resp.status_code == 200 else []
    except Exception as e:
        print(f"Ошибка Odds API: {e}")
        return []

def american_to_prob(odds):
    if odds > 0:
        return 100 / (odds + 100) * 100
    else:
        return abs(odds) / (abs(odds) + 100) * 100

async def get_team_stats_fastbreak(team_name):
    try:
        async with NBAClient() as client:
            # Поиск команды
            teams = await client.teams()
            team = None
            for t in teams:
                if t.full_name == team_name or t.name in team_name or team_name in t.full_name:
                    team = t
                    break
            
            if not team:
                return None
            
            # Получаем расписание команды
            schedule = await client.team_schedule(team.id)
            games = schedule.games
            
            if not games:
                return None
            
            # Берём последние 5 игр
            last_5 = []
            for game in games:
                if game.status == "Final":
                    last_5.append(game)
                    if len(last_5) >= 5:
                        break
            
            if not last_5:
                return None
            
            wins = 0
            losses = 0
            streak = 0
            total_points = 0
            
            for game in last_5:
                if game.home_team.id == team.id:
                    scored = game.home_score
                    allowed = game.away_score
                    won = game.home_score > game.away_score
                else:
                    scored = game.away_score
                    allowed = game.home_score
                    won = game.away_score > game.home_score
                
                total_points += scored
                
                if won:
                    wins += 1
                    streak = streak + 1 if streak >= 0 else 1
                else:
                    losses += 1
                    streak = streak - 1 if streak <= 0 else -1
            
            games_count = len(last_5)
            ppg = round(total_points / games_count, 1)
            
            return {
                "form": f"{wins}-{losses}",
                "streak": streak,
                "ppg": ppg,
                "win_pct": round(wins / games_count * 100)
            }
    except Exception as e:
        print(f"    Ошибка fastbreak для {team_name}: {e}")
        return None

def main():
    print("🏀 NBA прогнозы + fastbreak")
    
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
        
        home_prob = american_to_prob(home_odds)
        away_prob = american_to_prob(away_odds)
        total = home_prob + away_prob
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100
        
        winner = home if home_prob > away_prob else away
        winner_prob = round(max(home_prob, away_prob))
        
        commence = game.get("commence_time")
        if commence:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
            date_str = dt.strftime("%d.%m.%Y")
            time_str = dt.strftime("%H:%M")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "04:30"
        
        print(f"📊 Статистика: {home} vs {away}")
        
        home_stats = asyncio.run(get_team_stats_fastbreak(home))
        away_stats = asyncio.run(get_team_stats_fastbreak(away))
        
        match = {
            "date": date_str,
            "time": time_str,
            "home": home,
            "away": away,
            "winner": winner,
            "probability": winner_prob,
            "home_form": home_stats["form"] if home_stats else None,
            "away_form": away_stats["form"] if away_stats else None,
            "home_streak": home_stats["streak"] if home_stats else None,
            "away_streak": away_stats["streak"] if away_stats else None,
            "home_ppg": home_stats["ppg"] if home_stats else None,
            "away_ppg": away_stats["ppg"] if away_stats else None,
        }
        matches.append(match)
        
        print(f"  ✅ {home}: {home_stats['form'] if home_stats else 'нет'} | PPG {home_stats['ppg'] if home_stats else '?'}")
        print(f"  ✅ {away}: {away_stats['form'] if away_stats else 'нет'} | PPG {away_stats['ppg'] if away_stats else '?'}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated_at": datetime.now().isoformat()}, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Сохранено {len(matches)} матчей")

if __name__ == "__main__":
    main()
