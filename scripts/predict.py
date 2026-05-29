#!/usr/bin/env python3
"""
РАСШИРЕННЫЕ ПРОГНОЗЫ С ESPN API
- Коэффициенты букмекеров
- Форма команд из ESPN (последние 5 игр)
- Серия побед/поражений
- История личных встреч (H2H)
- Травмы игроков
"""

import json
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List

# ============================================================
# НАСТРОЙКИ
# ============================================================

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

SPORT_NBA = "basketball_nba"
SPORT_NHL = "icehockey_nhl"

MIN_PROB = 55

TOTAL_LINE_NBA = 225.5
TOTAL_LINE_NHL = 6.5

# Кэш для ESPN
espn_cache = {}

# ============================================================
# ESPN API ФУНКЦИИ
# ============================================================

def get_espn_team_id(team_name: str) -> str:
    """Получить ESPN team ID по названию команды"""
    cache_key = "team_ids"
    if cache_key in espn_cache:
        return espn_cache[cache_key].get(team_name)
    
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            team_map = {}
            for team in data["sports"][0]["leagues"][0]["teams"]:
                display_name = team["team"]["displayName"]
                team_map[display_name] = team["team"]["id"]
            espn_cache[cache_key] = team_map
            return team_map.get(team_name)
    except Exception as e:
        print(f"    ⚠️ Ошибка получения ID для {team_name}: {e}")
    
    return None


def get_team_form_espn(team_name: str) -> Dict[str, Any]:
    """Получить форму команды через ESPN API"""
    team_id = get_espn_team_id(team_name)
    if not team_id:
        return {"form": "?", "streak": 0, "win_pct": 0, "ppg": 0, "form_icons": ""}
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/schedule"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return {"form": "?", "streak": 0, "win_pct": 0, "ppg": 0, "form_icons": ""}
        
        data = resp.json()
        events = data.get("events", [])[:10]
        
        if not events:
            return {"form": "?", "streak": 0, "win_pct": 0, "ppg": 0, "form_icons": ""}
        
        wins = 0
        losses = 0
        streak = 0
        recent_results = []
        total_points = 0
        
        for game in events:
            comp = game["competitions"][0]
            status = comp["status"]["type"]["name"]
            
            if status != "STATUS_FINAL":
                continue
            
            home_team = comp["competitors"][0]["team"]["displayName"]
            away_team = comp["competitors"][1]["team"]["displayName"]
            home_score = int(comp["competitors"][0]["score"])
            away_score = int(comp["competitors"][1]["score"])
            
            # Очки нашей команды
            if team_name == home_team:
                our_score = home_score
                total_points += our_score
            else:
                our_score = away_score
                total_points += our_score
            
            # Победила ли наша команда
            won = (team_name == home_team and home_score > away_score) or \
                  (team_name == away_team and away_score > home_score)
            
            if won:
                wins += 1
                streak = streak + 1 if streak >= 0 else 1
                recent_results.append("✅")
            else:
                losses += 1
                streak = streak - 1 if streak <= 0 else -1
                recent_results.append("❌")
        
        total_games = wins + losses
        if total_games == 0:
            return {"form": "?", "streak": 0, "win_pct": 0, "ppg": 0, "form_icons": ""}
        
        return {
            "form": f"{wins}-{losses}",
            "form_icons": " ".join(recent_results[:5]),
            "streak": streak,
            "wins": wins,
            "losses": losses,
            "win_pct": round(wins / total_games * 100),
            "ppg": round(total_points / total_games, 1)
        }
    except Exception as e:
        print(f"    ⚠️ Ошибка получения формы для {team_name}: {e}")
        return {"form": "?", "streak": 0, "win_pct": 0, "ppg": 0, "form_icons": ""}


def get_espn_game_results(date_str: str) -> List[Dict]:
    """Получить результаты матчей за конкретную дату (формат: YYYYMMDD)"""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    params = {"dates": date_str}
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        events = data.get("events", [])
        
        results = []
        for event in events:
            comp = event["competitions"][0]
            status = comp["status"]["type"]["name"]
            
            home = comp["competitors"][0]["team"]["displayName"]
            away = comp["competitors"][1]["team"]["displayName"]
            home_score = int(comp["competitors"][0]["score"])
            away_score = int(comp["competitors"][1]["score"])
            
            results.append({
                "home": home,
                "away": away,
                "home_score": home_score,
                "away_score": away_score,
                "completed": status == "STATUS_FINAL"
            })
        
        return results
    except Exception as e:
        print(f"    ⚠️ Ошибка получения результатов за {date_str}: {e}")
        return []


def get_h2h_espn(team1: str, team2: str) -> str:
    """Получить историю личных встреч через ESPN"""
    h2h_games = []
    
    # Проверяем последние 60 дней с шагом 7 дней
    for days_ago in range(0, 60, 7):
        date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")
        games = get_espn_game_results(date)
        
        for game in games:
            if (game["home"] == team1 and game["away"] == team2) or \
               (game["home"] == team2 and game["away"] == team1):
                
                if game["completed"]:
                    date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%d.%m")
                    result = f"{date_str}: {game['home']} {game['home_score']}–{game['away_score']} {game['away']}"
                    h2h_games.append(result)
    
    if h2h_games:
        return "; ".join(h2h_games[:5])
    return "Нет данных о личных встречах за последние 60 дней"


def get_injuries_espn(team_name: str) -> str:
    """Получить травмы игроков через ESPN"""
    team_id = get_espn_team_id(team_name)
    if not team_id:
        return "Данные о травмах загружаются"
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return "Данные о травмах загружаются"
        
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
        print(f"    ⚠️ Ошибка получения травм для {team_name}: {e}")
        return "Данные о травмах временно недоступны"


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


def get_completed_games_odds(sport: str, days_back: int = 14) -> list:
    """Получает завершённые матчи из Odds API для истории"""
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
    
    # Файлы
    history_file = f"data/{league}_history.json"
    backup_file = f"data/{league}_backup.json"
    matches_file = f"data/{league}_matches.json"
    
    # 1. Загружаем существующую историю
    history = {"predictions": []}
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            history = json.load(f)
    
    # 2. Загружаем бэкап
    backup = {"predictions": []}
    if os.path.exists(backup_file):
        with open(backup_file, "r") as f:
            backup = json.load(f)
    
    # 3. Обновляем историю из Odds API
    print("  📊 Обновляем историю угадываний...")
    completed = get_completed_games_odds(sport_key, 14)
    
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
        home_score = scores.get(home, 0) if isinstance(scores, dict) else 0
        away_score = scores.get(away, 0) if isinstance(scores, dict) else 0
        
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
        
        # ПОЛУЧАЕМ РАСШИРЕННУЮ СТАТИСТИКУ ИЗ ESPN
        print(f"  📊 [{idx}/{total_games}] ESPN анализ: {home} – {away}")
        
        home_stats = get_team_form_espn(home)
        away_stats = get_team_form_espn(away)
        
        h2h = get_h2h_espn(home, away)
        
        home_injuries = get_injuries_espn(home)
        away_injuries = get_injuries_espn(away)
        
        # Формируем серию в читаемый вид
        home_streak_str = f"+{home_stats['streak']}" if home_stats['streak'] > 0 else str(home_stats['streak'])
        away_streak_str = f"+{away_stats['streak']}" if away_stats['streak'] > 0 else str(away_stats['streak'])
        
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
            "home_form_icons": home_stats.get("form_icons", ""),
            "away_form_icons": away_stats.get("form_icons", ""),
            "home_streak": home_streak_str,
            "away_streak": away_streak_str,
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
            "data_source": "Коэффициенты Odds API + Статистика ESPN"
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
        
        print(f"  ✅ [{idx}/{total_games}] {home} – {away}: {winner} ({prob}%) | форма {home_stats['form']} ({home_streak_str}) vs {away_stats['form']} ({away_streak_str})")
    
    # 5. Сохраняем
    with open(matches_file, "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": league, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    all_backup = new_backup + backup["predictions"]
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump({"predictions": all_backup}, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ Сохранено {len(matches)} матчей")


def main():
    print("🚀 ЗАПУСК ПРОГНОЗОВ С ESPN API")
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
