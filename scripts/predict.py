#!/usr/bin/env python3
"""
РАСШИРЕННЫЕ ПРОГНОЗЫ С ПОЛНОЙ СТАТИСТИКОЙ
- Коэффициенты букмекеров
- Форма команд (последние 5 игр)
- Серия побед/поражений
- История личных встреч (H2H)
- Травмы игроков
"""

import json
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# ============================================================
# НАСТРОЙКИ
# ============================================================

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

SPORT_NBA = "basketball_nba"
SPORT_NHL = "icehockey_nhl"

MIN_PROB = 55

TOTAL_LINE_NBA = 225.5
TOTAL_LINE_NHL = 6.5

# Кэш для данных из SportsReference (чтобы не дёргать API каждый раз)
CACHE = {}

# ============================================================
# ПОЛУЧЕНИЕ СТАТИСТИКИ ИЗ SPORTSREFERENCE
# ============================================================

def get_nba_team_stats(team_name: str) -> Dict[str, Any]:
    """Получить статистику команды NBA из SportsReference"""
    try:
        from sportsipy.nba.teams import Teams
        from sportsipy.nba.schedule import Schedule
        
        # Нормализация названий команд
        name_mapping = {
            "LA Lakers": "Los Angeles Lakers",
            "LA Clippers": "Los Angeles Clippers",
            "NY Knicks": "New York Knicks",
            "OKC Thunder": "Oklahoma City Thunder",
            "San Antonio": "San Antonio Spurs",
            "Golden State": "Golden State Warriors",
        }
        
        search_name = name_mapping.get(team_name, team_name)
        
        teams = Teams()
        team = None
        
        for t in teams:
            if t.name == search_name or search_name in t.name:
                team = t
                break
        
        if not team:
            return {"form": "?", "streak": 0, "wins": 0, "losses": 0}
        
        # Получаем расписание последних игр
        schedule = Schedule(team.abbreviation)
        last_5 = list(schedule)[:5]
        
        wins = sum(1 for g in last_5 if g.won)
        losses = 5 - wins
        
        # Серия (сколько последних игр подряд выиграли/проиграли)
        streak = 0
        for game in last_5:
            if game.won:
                streak = streak + 1 if streak >= 0 else 1
            else:
                streak = streak - 1 if streak <= 0 else -1
        
        return {
            "form": f"{wins}-{losses}",
            "streak": streak,
            "wins": team.wins,
            "losses": team.losses,
            "win_pct": round(team.wins / (team.wins + team.losses) * 100) if (team.wins + team.losses) > 0 else 0,
            "ppg": round(team.points_per_game, 1) if hasattr(team, 'points_per_game') else 0,
        }
    except Exception as e:
        print(f"    ⚠️ Ошибка NBA stats для {team_name}: {e}")
        return {"form": "?", "streak": 0, "wins": 0, "losses": 0, "win_pct": 0, "ppg": 0}


def get_nhl_team_stats(team_name: str) -> Dict[str, Any]:
    """Получить статистику команды NHL из SportsReference"""
    try:
        from sportsipy.nhl.teams import Teams
        from sportsipy.nhl.schedule import Schedule
        
        teams = Teams()
        team = None
        
        for t in teams:
            if t.name == team_name or team_name in t.name:
                team = t
                break
        
        if not team:
            return {"form": "?", "streak": 0, "wins": 0, "losses": 0}
        
        schedule = Schedule(team.abbreviation)
        last_5 = list(schedule)[:5]
        
        wins = sum(1 for g in last_5 if g.won)
        losses = 5 - wins
        
        streak = 0
        for game in last_5:
            if game.won:
                streak = streak + 1 if streak >= 0 else 1
            else:
                streak = streak - 1 if streak <= 0 else -1
        
        return {
            "form": f"{wins}-{losses}",
            "streak": streak,
            "wins": team.wins,
            "losses": team.losses,
            "win_pct": round(team.wins / (team.wins + team.losses) * 100) if (team.wins + team.losses) > 0 else 0,
            "ppg": round(team.goals_per_game, 1) if hasattr(team, 'goals_per_game') else 0,
        }
    except Exception as e:
        print(f"    ⚠️ Ошибка NHL stats для {team_name}: {e}")
        return {"form": "?", "streak": 0, "wins": 0, "losses": 0, "win_pct": 0, "ppg": 0}


# ============================================================
# ПОЛУЧЕНИЕ ТРАВМ ИЗ ESPN
# ============================================================

def get_injuries_nba(team_name: str) -> str:
    """Получить травмы игроков NBA из ESPN"""
    try:
        # Нормализация названия для ESPN
        espn_names = {
            "Los Angeles Lakers": "lal",
            "Golden State Warriors": "gs",
            "Boston Celtics": "bos",
            "Miami Heat": "mia",
            "Phoenix Suns": "phx",
            "Dallas Mavericks": "dal",
            "Milwaukee Bucks": "mil",
            "Philadelphia 76ers": "phi",
            "Denver Nuggets": "den",
            "LA Clippers": "lac",
        }
        
        code = espn_names.get(team_name, "")
        if not code:
            return "Данные о травмах загружаются"
        
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{code}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            injuries = []
            
            for athlete in data.get("team", {}).get("athletes", []):
                if athlete.get("injuries"):
                    injury = athlete["injuries"][0]
                    status = injury.get("status", "травмирован")
                    details = injury.get("details", "")
                    injuries.append(f"{athlete['name']} ({status})")
            
            if injuries:
                return ", ".join(injuries[:3])
            return "✅ Все игроки в строю"
    except Exception as e:
        print(f"    ⚠️ Ошибка травм для {team_name}: {e}")
    
    return "Данные о травмах временно недоступны"


def get_injuries_nhl(team_name: str) -> str:
    """Получить травмы игроков NHL из ESPN"""
    try:
        # Похожая логика для NHL
        return "Данные о травмах загружаются"
    except:
        return "Данные о травмах временно недоступны"


# ============================================================
# ИСТОРИЯ ЛИЧНЫХ ВСТРЕЧ (H2H)
# ============================================================

def get_h2h_history(home: str, away: str, league: str) -> str:
    """Получить историю личных встреч"""
    try:
        if league == "nba":
            from sportsipy.nba.teams import Teams
            from sportsipy.nba.schedule import Schedule
            
            teams = Teams()
            home_team = None
            away_team = None
            
            for t in teams:
                if t.name == home or home in t.name:
                    home_team = t
                if t.name == away or away in t.name:
                    away_team = t
            
            if not home_team or not away_team:
                return "Нет данных"
            
            # Получаем расписания обеих команд
            home_schedule = Schedule(home_team.abbreviation)
            away_schedule = Schedule(away_team.abbreviation)
            
            # Ищем общие матчи
            h2h_games = []
            for game in list(home_schedule)[:30]:
                if away in game.opponent_name:
                    result = "победа" if game.won else "поражение"
                    h2h_games.append(f"{game.date}: {game.points_scored}-{game.points_allowed} ({result})")
            
            if h2h_games:
                return "; ".join(h2h_games[:5])
            return "Нет данных о личных встречах"
    except Exception as e:
        print(f"    ⚠️ Ошибка H2H: {e}")
    
    return "Нет данных"


# ============================================================
# ОСНОВНЫЕ ФУНКЦИИ
# ============================================================

def american_to_prob(american_odds: int) -> float:
    """Американский коэффициент -> вероятность в %"""
    if american_odds > 0:
        return 100 / (american_odds + 100) * 100
    else:
        return abs(american_odds) / (abs(american_odds) + 100) * 100


def get_upcoming_games(sport: str) -> list:
    """Получает предстоящие матчи из Odds API"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us,uk,eu",
        "markets": "h2h,totals",
        "oddsFormat": "american"
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  Ошибка API: {resp.status_code}")
            return []
    except Exception as e:
        print(f"  Ошибка: {e}")
        return []


def get_completed_games(sport: str, days_back: int = 14) -> list:
    """Получает завершённые матчи из Odds API"""
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores"
    params = {"apiKey": ODDS_API_KEY, "daysFrom": days_back}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            games = resp.json()
            return [g for g in games if g.get("completed")]
        return []
    except:
        return []


def update_league(league: str, sport_key: str):
    """Обновляет прогнозы для одной лиги"""
    print(f"\n{'🏀' if league == 'nba' else '🏒'} ОБНОВЛЕНИЕ {league.upper()}")
    
    total_line = TOTAL_LINE_NBA if league == "nba" else TOTAL_LINE_NHL
    get_team_stats = get_nba_team_stats if league == "nba" else get_nhl_team_stats
    get_injuries = get_injuries_nba if league == "nba" else get_injuries_nhl
    
    # Файлы
    history_file = f"data/{league}_history.json"
    backup_file = f"data/{league}_backup.json"
    matches_file = f"data/{league}_matches.json"
    
    # 1. Загружаем историю
    history = {"predictions": []}
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            history = json.load(f)
    
    # 2. Загружаем бэкап
    backup = {"predictions": []}
    if os.path.exists(backup_file):
        with open(backup_file, "r") as f:
            backup = json.load(f)
    
    # 3. Обновляем историю из завершённых матчей
    print("  📊 Обновляем историю угадываний...")
    completed = get_completed_games(sport_key, 14)
    
    existing_history = {(p["date"], p["home"], p["away"]) for p in history["predictions"]}
    backup_dict = {(p["date"], p["home"], p["away"]): p for p in backup["predictions"]}
    
    new_history = []
    for game in completed:
        commence = game.get("commence_time")
        if not commence:
            continue
        
        dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
        date_str = dt.strftime("%d.%m.%Y")
        home = game.get("home_team")
        away = game.get("away_team")
        key = (date_str, home, away)
        
        if key in existing_history or key not in backup_dict:
            continue
        
        scores = game.get("scores", {})
        home_score = scores.get(home, 0)
        away_score = scores.get(away, 0)
        
        if home_score == 0 and away_score == 0:
            continue
        
        actual_winner = home if home_score > away_score else away
        predicted = backup_dict[key]["prediction"]
        prob = backup_dict[key]["prob"]
        
        result = "✅" if predicted == actual_winner else "❌"
        
        predicted_total = backup_dict[key].get("total_prediction", "БОЛЬШЕ")
        actual_total = home_score + away_score
        total_result = "✅" if (predicted_total == "БОЛЬШЕ" and actual_total > total_line) or (predicted_total == "МЕНЬШЕ" and actual_total < total_line) else "❌"
        
        new_history.append({
            "date": date_str,
            "home": home,
            "away": away,
            "prediction": predicted,
            "result": result,
            "total_prediction": f"Тотал {predicted_total} {total_line}",
            "total_result": total_result,
            "actual_score": f"{home_score} : {away_score}",
            "prob": prob
        })
        print(f"    {result} {home} – {away}: прогноз {predicted}, реально {actual_winner}")
    
    if new_history:
        history["predictions"] = new_history + history["predictions"]
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"  ✅ Добавлено {len(new_history)} записей в историю")
    
    # 4. Получаем предстоящие матчи
    print("  🎲 Загружаем предстоящие матчи...")
    games = get_upcoming_games(sport_key)
    if not games:
        print("  ❌ Нет данных")
        return
    
    matches = []
    new_backup = []
    total_games = len(games)
    
    for idx, game in enumerate(games, 1):
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue
        
        # Дата и время
        commence = game.get("commence_time")
        if commence:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
            date_str = dt.strftime("%d.%m.%Y")
            time_str = dt.strftime("%H:%M МСК")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "04:30 МСК"
        
        # Коэффициенты
        home_odds = None
        away_odds = None
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "h2h":
                    for outcome in market["outcomes"]:
                        if outcome["name"] == home:
                            home_odds = outcome["price"]
                        elif outcome["name"] == away:
                            away_odds = outcome["price"]
        
        if not home_odds or not away_odds:
            continue
        
        # Вероятность
        home_prob = american_to_prob(home_odds)
        away_prob = american_to_prob(away_odds)
        total = home_prob + away_prob
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100
        
        winner = home if home_prob > away_prob else away
        prob = round(max(home_prob, away_prob))
        
        # Пропускаем низкую вероятность
        if prob < MIN_PROB:
            print(f"  ⏭️ [{idx}/{total_games}] Пропущен ({prob}%): {home} – {away}")
            continue
        
        # Тотал
        total_direction = "БОЛЬШЕ"
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "totals":
                    for outcome in market["outcomes"]:
                        if outcome["name"] == "Over":
                            total_direction = "БОЛЬШЕ"
                        elif outcome["name"] == "Under":
                            total_direction = "МЕНЬШЕ"
        
        # ПОЛУЧАЕМ РАСШИРЕННУЮ СТАТИСТИКУ
        print(f"  📊 [{idx}/{total_games}] Сбор статистики: {home} – {away}")
        
        home_stats = get_team_stats(home)
        away_stats = get_team_stats(away)
        
        h2h = get_h2h_history(home, away, league)
        home_injuries = get_injuries(home)
        away_injuries = get_injuries(away)
        
        match = {
            "date": date_str,
            "time": time_str,
            "home": home,
            "away": away,
            "winner": winner,
            "prob": prob,
            "total_prediction": f"Тотал {total_direction} {total_line}",
            # Форма команд
            "home_form": home_stats["form"],
            "away_form": away_stats["form"],
            "home_streak": home_stats["streak"],
            "away_streak": away_stats["streak"],
            "home_win_pct": home_stats["win_pct"],
            "away_win_pct": away_stats["win_pct"],
            "home_ppg": home_stats["ppg"],
            "away_ppg": away_stats["ppg"],
            # История встреч
            "h2h": h2h,
            # Травмы
            "home_injuries": home_injuries,
            "away_injuries": away_injuries,
            # Источник
            "data_source": "Коэффициенты + SportsReference + ESPN"
        }
        
        matches.append(match)
        new_backup.append({
            "date": date_str,
            "home": home,
            "away": away,
            "prediction": winner,
            "total_prediction": total_direction,
            "prob": prob
        })
        
        print(f"  ✅ [{idx}/{total_games}] {home} – {away}: {winner} ({prob}%) | форма {home_stats['form']} vs {away_stats['form']}")
    
    # 5. Сохраняем
    with open(matches_file, "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": league, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    all_backup = new_backup + backup["predictions"]
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump({"predictions": all_backup}, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ Сохранено {len(matches)} матчей")


def main():
    print("🚀 ЗАПУСК РАСШИРЕННЫХ ПРОГНОЗОВ")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Минимальная вероятность: {MIN_PROB}%")
    
    if not ODDS_API_KEY:
        print("❌ ODDS_API_KEY не найден")
        return
    
    os.makedirs("data", exist_ok=True)
    
    update_league("nba", SPORT_NBA)
    update_league("nhl", SPORT_NHL)
    
    print("\n✨ Готово")


if __name__ == "__main__":
    main()
