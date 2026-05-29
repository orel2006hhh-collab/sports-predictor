#!/usr/bin/env python3
"""
NBA прогнозы + статистика команд
- Получение предстоящих матчей из The Odds API
- Получение статистики команд из balldontlie API (PPG, OPP PPG, форма 5 игр)
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

# --- Работа с balldontlie API (бесплатно, без ключа) ---
BALLDONTLIE_BASE = "https://www.balldontlie.io/api/v1"

# Маппинг названий команд Odds API -> названия в balldontlie
# balldontlie возвращает города и названия (например "L.A. Lakers"), поэтому ищем по частичному совпадению
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
        resp = requests.get(f"{BALLDONTLIE_BASE}/teams", timeout=10)
        if resp.status_code == 200:
            teams_data = resp.json()
            teams = {}
            for team in teams_data.get("data", []):
                # Сохраняем по ID и по названию для поиска
                teams[team["id"]] = team
            return teams
    except Exception as e:
        print(f"  ⚠️ Ошибка получения команд из balldontlie: {e}")
    return {}

def find_team_id(team_name, teams_dict):
    """Найти ID команды по названию"""
    # Сначала пробуем прямое совпадение
    for team_id, team_info in teams_dict.items():
        if team_info.get("full_name") == team_name:
            return team_id
        if team_info.get("name") == team_name:
            return team_id
    
    # Потом через маппинг
    short_name = TEAM_NAME_MAPPING.get(team_name, "")
    if short_name:
        for team_id, team_info in teams_dict.items():
            if team_info.get("name") == short_name:
                return team_id
            if short_name.lower() in team_info.get("full_name", "").lower():
                return team_id
    
    # Поиск по частичному совпадению
    for team_id, team_info in teams_dict.items():
        full = team_info.get("full_name", "")
        if team_name.lower() in full.lower() or any(word.lower() in full.lower() for word in team_name.split()):
            return team_id
    return None

def get_team_stats_balldontlie(team_name, teams_dict, team_id):
    """Получить статистику команды: PPG, OPP PPG, форма 5 игр"""
    if not team_id:
        return {"ppg": 0, "opp_ppg": 0, "form": "0-0", "streak": 0}
    
    try:
        # Получаем последние игры команды
        # Используем параметр team_ids[] для фильтрации по команде
        url = f"{BALLDONTLIE_BASE}/games"
        params = {
            "team_ids[]": team_id,
            "per_page": 10,
            "seasons[]": [datetime.now().year, datetime.now().year - 1],
        }
        resp = requests.get(url, params=params, timeout=10)
        
        if resp.status_code != 200:
            return {"ppg": 0, "opp_ppg": 0, "form": "0-0", "streak": 0}
        
        games = resp.json().get("data", [])
        
        # Фильтруем только завершённые игры
        completed_games = [g for g in games if g.get("status") == "Final"]
        
        # Берём последние 5 игр
        last_5 = completed_games[:5]
        
        if not last_5:
            return {"ppg": 0, "opp_ppg": 0, "form": "0-0", "streak": 0}
        
        wins = 0
        losses = 0
        streak = 0
        total_points_scored = 0
        total_points_allowed = 0
        
        for game in last_5:
            home_team = game.get("home_team")
            away_team = game.get("away_team")
            home_score = game.get("home_team_score", 0)
            away_score = game.get("away_team_score", 0)
            
            # Определяем, была ли наша команда дома или в гостях
            if home_team and home_team.get("id") == team_id:
                scored = home_score
                allowed = away_score
                won = home_score > away_score
            else:
                scored = away_score
                allowed = home_score
                won = away_score > home_score
            
            total_points_scored += scored
            total_points_allowed += allowed
            
            if won:
                wins += 1
                streak = streak + 1 if streak >= 0 else 1
            else:
                losses += 1
                streak = streak - 1 if streak <= 0 else -1
        
        games_count = len(last_5)
        ppg = round(total_points_scored / games_count, 1) if games_count > 0 else 0
        opp_ppg = round(total_points_allowed / games_count, 1) if games_count > 0 else 0
        
        # Процент побед
        win_pct = round(wins / games_count * 100) if games_count > 0 else 0
        
        return {
            "ppg": ppg,
            "opp_ppg": opp_ppg,
            "form": f"{wins}-{losses}",
            "streak": streak,
            "win_pct": win_pct
        }
        
    except Exception as e:
        print(f"  ⚠️ Ошибка получения статистики для {team_name}: {e}")
        return {"ppg": 0, "opp_ppg": 0, "form": "0-0", "streak": 0, "win_pct": 0}

# --- Основные функции (без изменений) ---
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
    print("📡 Загружаем список команд из balldontlie...")
    teams_dict = get_balldontlie_teams()
    if not teams_dict:
        print("⚠️ Не удалось получить данные команд, статистика будет ограниченной")
    
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
        
        # --- Получаем статистику команд из balldontlie ---
        print(f"📊 Собираем статистику для: {home} vs {away}")
        
        home_id = find_team_id(home, teams_dict)
        away_id = find_team_id(away, teams_dict)
        
        home_stats = get_team_stats_balldontlie(home, teams_dict, home_id)
        away_stats = get_team_stats_balldontlie(away, teams_dict, away_id)
        
        # Формируем серию в читаемый вид
        home_streak_str = f"+{home_stats['streak']}" if home_stats['streak'] > 0 else str(home_stats['streak'])
        away_streak_str = f"+{away_stats['streak']}" if away_stats['streak'] > 0 else str(away_stats['streak'])
        
        matches.append({
            "date": date_str,
            "time": time_str,
            "home": home,
            "away": away,
            "winner": winner,
            "probability": winner_prob,
            # Статистика хозяев
            "home_ppg": home_stats["ppg"],
            "home_opp_ppg": home_stats["opp_ppg"],
            "home_form": home_stats["form"],
            "home_streak": home_streak_str,
            "home_win_pct": home_stats["win_pct"],
            # Статистика гостей
            "away_ppg": away_stats["ppg"],
            "away_opp_ppg": away_stats["opp_ppg"],
            "away_form": away_stats["form"],
            "away_streak": away_streak_str,
            "away_win_pct": away_stats["win_pct"],
            "source": "The Odds API + balldontlie"
        })
        
        print(f"  ✅ {home}: форма {home_stats['form']}, PPG {home_stats['ppg']}")
        print(f"  ✅ {away}: форма {away_stats['form']}, PPG {away_stats['ppg']}")
    
    # Сохраняем
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({
            "matches": matches, 
            "last_updated": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Сохранено {len(matches)} матчей с полной статистикой")

if __name__ == "__main__":
    main()
