#!/usr/bin/env python3
"""
NBA прогнозы + статистика команд
- Получение предстоящих матчей из The Odds API
- Получение статистики команд из balldontlie API (PPG, форма 5 игр)
"""

import json
import os
import requests
from datetime import datetime, timedelta

# --- Конфигурация ---
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
SPORT = "basketball_nba"
REGIONS = "us"
MARKETS = "h2h"
ODDS_FORMAT = "american"

# --- Маппинг названий команд Odds API -> balldontlie ---
TEAM_NAME_MAPPING = {
    "Los Angeles Lakers": "Lakers",
    "LA Lakers": "Lakers", 
    "Golden State Warriors": "Warriors",
    "Boston Celtics": "Celtics",
    "Miami Heat": "Heat",
    "Chicago Bulls": "Bulls",
    "Dallas Mavericks": "Mavericks",
    "Denver Nuggets": "Nuggets",
    "Phoenix Suns": "Suns",
    "Philadelphia 76ers": "76ers",
    "Milwaukee Bucks": "Bucks",
    "Brooklyn Nets": "Nets",
    "New York Knicks": "Knicks",
    "Toronto Raptors": "Raptors",
    "Atlanta Hawks": "Hawks",
    "Cleveland Cavaliers": "Cavaliers",
    "Indiana Pacers": "Pacers",
    "Detroit Pistons": "Pistons",
    "Charlotte Hornets": "Hornets",
    "Orlando Magic": "Magic",
    "Washington Wizards": "Wizards",
    "Memphis Grizzlies": "Grizzlies",
    "New Orleans Pelicans": "Pelicans",
    "San Antonio Spurs": "Spurs",
    "Oklahoma City Thunder": "Thunder",
    "Utah Jazz": "Jazz",
    "Sacramento Kings": "Kings",
    "Portland Trail Blazers": "Trail Blazers",
    "Minnesota Timberwolves": "Timberwolves",
    "Houston Rockets": "Rockets",
    "LA Clippers": "Clippers",
    "Los Angeles Clippers": "Clippers",
}

def get_balldontlie_teams():
    """Получить список всех команд из balldontlie с их ID"""
    try:
        resp = requests.get("https://www.balldontlie.io/api/v1/teams", timeout=10)
        if resp.status_code == 200:
            teams_data = resp.json()
            teams = {}
            for team in teams_data.get("data", []):
                teams[team["id"]] = team
            return teams
    except Exception as e:
        print(f"  ⚠️ Ошибка получения команд: {e}")
    return {}

def find_team_id(team_name, teams_dict):
    """Найти ID команды по названию"""
    if not teams_dict:
        return None
    
    # Прямое совпадение full_name
    for team_id, team_info in teams_dict.items():
        if team_info.get("full_name") == team_name:
            return team_id
    
    # Через маппинг
    short_name = TEAM_NAME_MAPPING.get(team_name, "")
    if short_name:
        for team_id, team_info in teams_dict.items():
            if team_info.get("name") == short_name:
                return team_id
    
    # Частичное совпадение
    for team_id, team_info in teams_dict.items():
        full = team_info.get("full_name", "")
        if team_name.lower() in full.lower():
            return team_id
    
    return None

def get_team_stats_balldontlie(team_id):
    """Получить статистику команды: PPG, форма 5 игр"""
    # Возвращаем значения по умолчанию сразу, если нет ID
    default_stats = {
        "ppg": 0,
        "opp_ppg": 0,
        "form": "0-0",
        "streak": 0,
        "win_pct": 0
    }
    
    if not team_id:
        return default_stats
    
    try:
        url = "https://www.balldontlie.io/api/v1/games"
        params = {
            "team_ids[]": team_id,
            "per_page": 10,
            "seasons[]": [2024, 2025],
        }
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code != 200:
            return default_stats
        
        games = resp.json().get("data", [])
        
        # Фильтруем завершённые игры
        completed_games = [g for g in games if g.get("status") == "Final"]
        last_5 = completed_games[:5]
        
        if not last_5:
            return default_stats
        
        wins = 0
        losses = 0
        streak = 0
        total_scored = 0
        total_allowed = 0
        
        for game in last_5:
            home_team = game.get("home_team")
            away_team = game.get("away_team")
            home_score = game.get("home_team_score", 0)
            away_score = game.get("away_team_score", 0)
            
            # Наша команда дома или в гостях?
            if home_team and home_team.get("id") == team_id:
                scored = home_score
                allowed = away_score
                won = home_score > away_score
            else:
                scored = away_score
                allowed = home_score
                won = away_score > home_score
            
            total_scored += scored
            total_allowed += allowed
            
            if won:
                wins += 1
                streak = streak + 1 if streak >= 0 else 1
            else:
                losses += 1
                streak = streak - 1 if streak <= 0 else -1
        
        games_count = len(last_5)
        
        return {
            "ppg": round(total_scored / games_count, 1),
            "opp_ppg": round(total_allowed / games_count, 1),
            "form": f"{wins}-{losses}",
            "streak": streak,
            "win_pct": round(wins / games_count * 100)
        }
        
    except Exception as e:
        print(f"  ⚠️ Ошибка: {e}")
        return default_stats

def fetch_games():
    """Получить предстоящие матчи из The Odds API"""
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT,
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка Odds API: {response.status_code}")
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
    print("🏀 NBA прогнозы + статистика команд")
    print("=" * 50)
    
    # 1. Получаем список команд из balldontlie
    print("📡 Загружаем список команд...")
    teams_dict = get_balldontlie_teams()
    if teams_dict:
        print(f"  ✅ Загружено {len(teams_dict)} команд")
    else:
        print("  ⚠️ Не удалось загрузить команды, статистика будет ограниченной")
    
    # 2. Получаем матчи
    print("📡 Загружаем матчи из Odds API...")
    games = fetch_games()
    if not games:
        print("❌ Нет данных")
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
        total = home_prob + away_prob
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100
        
        if home_prob > away_prob:
            winner = home
            winner_prob = round(home_prob)
        else:
            winner = away
            winner_prob = round(away_prob)
        
        # Дата и время матча
        commence = game.get("commence_time")
        if commence:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
            date_str = dt.strftime("%d.%m.%Y")
            time_str = dt.strftime("%H:%M")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "00:00"
        
        # Получаем статистику команд
        print(f"📊 Статистика: {home} vs {away}")
        
        home_id = find_team_id(home, teams_dict)
        away_id = find_team_id(away, teams_dict)
        
        home_stats = get_team_stats_balldontlie(home_id)
        away_stats = get_team_stats_balldontlie(away_id)
        
        # Форматируем серию
        def format_streak(s):
            if s > 0:
                return f"+{s}"
            elif s < 0:
                return str(s)
            return "0"
        
        match_data = {
            "date": date_str,
            "time": time_str,
            "home": home,
            "away": away,
            "winner": winner,
            "probability": winner_prob,
            # Хозяева
            "home_ppg": home_stats["ppg"],
            "home_form": home_stats["form"],
            "home_streak": format_streak(home_stats["streak"]),
            "home_win_pct": home_stats["win_pct"],
            # Гости
            "away_ppg": away_stats["ppg"],
            "away_form": away_stats["form"],
            "away_streak": format_streak(away_stats["streak"]),
            "away_win_pct": away_stats["win_pct"],
        }
        matches.append(match_data)
        
        print(f"  ✅ {home}: {home_stats['form']} (PPG {home_stats['ppg']})")
        print(f"  ✅ {away}: {away_stats['form']} (PPG {away_stats['ppg']})")
    
    # Сохраняем
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({
            "matches": matches,
            "last_updated": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Сохранено {len(matches)} матчей")

if __name__ == "__main__":
    main()
