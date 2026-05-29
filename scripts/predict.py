#!/usr/bin/env python3
"""
РАСШИРЕННЫЕ ПРОГНОЗЫ С ФОРМОЙ ИЗ ИСТОРИИ МАТЧЕЙ
- Коэффициенты букмекеров
- Форма команд (из реальных результатов завершённых матчей)
- Серия побед/поражений
- История личных встреч
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

# Кэш для завершённых матчей
completed_games_cache = {}

# ============================================================
# ПОЛУЧЕНИЕ ФОРМЫ КОМАНДЫ ИЗ ИСТОРИИ
# ============================================================

def fetch_completed_games(sport: str, days_back: int = 30) -> List[Dict]:
    """Получает завершённые матчи за последние N дней"""
    cache_key = f"{sport}_{days_back}"
    if cache_key in completed_games_cache:
        return completed_games_cache[cache_key]
    
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores"
    params = {"apiKey": ODDS_API_KEY, "daysFrom": days_back}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            games = resp.json()
            completed = [g for g in games if g.get("completed")]
            completed_games_cache[cache_key] = completed
            print(f"    📥 Загружено {len(completed)} завершённых матчей за {days_back} дней")
            return completed
        return []
    except Exception as e:
        print(f"    ⚠️ Ошибка загрузки истории: {e}")
        return []


def get_team_form(team_name: str, sport: str, days_back: int = 30) -> Dict[str, Any]:
    """
    Рассчитывает форму команды на основе реальных результатов
    Возвращает: форма (победы-поражения), серия, процент побед, PPG
    """
    completed = fetch_completed_games(sport, days_back)
    
    # Собираем все матчи команды
    team_games = []
    for game in completed:
        home = game.get("home_team")
        away = game.get("away_team")
        scores = game.get("scores", {})
        home_score = scores.get(home, 0) if isinstance(scores, dict) else 0
        away_score = scores.get(away, 0) if isinstance(scores, dict) else 0
        
        if home_score == 0 and away_score == 0:
            continue
        
        if home == team_name:
            # Команда играла дома
            won = home_score > away_score
            opp = away
            scored = home_score
            allowed = away_score
            team_games.append({
                "date": game.get("commence_time", ""),
                "won": won,
                "opponent": opp,
                "scored": scored,
                "allowed": allowed,
                "home": True
            })
        elif away == team_name:
            # Команда играла в гостях
            won = away_score > home_score
            opp = home
            scored = away_score
            allowed = home_score
            team_games.append({
                "date": game.get("commence_time", ""),
                "won": won,
                "opponent": opp,
                "scored": scored,
                "allowed": allowed,
                "home": False
            })
    
    # Сортируем по дате (новые сверху)
    team_games.sort(key=lambda x: x["date"], reverse=True)
    
    # Берём последние 5 матчей для формы
    last_5 = team_games[:5]
    total_games = len(last_5)
    
    if total_games == 0:
        return {
            "form": "?",
            "streak": 0,
            "wins": 0,
            "losses": 0,
            "win_pct": 0,
            "ppg": 0,
            "recent_games": []
        }
    
    wins = sum(1 for g in last_5 if g["won"])
    losses = total_games - wins
    
    # Серия (сколько последних игр подряд выиграли/проиграли)
    streak = 0
    for game in last_5:
        if game["won"]:
            if streak >= 0:
                streak += 1
            else:
                streak = 1
        else:
            if streak <= 0:
                streak -= 1
            else:
                streak = -1
    
    # Среднее набранных очков за игру
    ppg = round(sum(g["scored"] for g in last_5) / total_games, 1) if total_games > 0 else 0
    
    # Форма в читаемом виде
    form_parts = []
    for game in last_5[:5]:
        form_parts.append("✅" if game["won"] else "❌")
    form_str = " ".join(form_parts)
    
    return {
        "form": f"{wins}-{losses}",
        "form_icons": form_str,
        "streak": streak,
        "wins": wins,
        "losses": losses,
        "win_pct": round(wins / total_games * 100) if total_games > 0 else 0,
        "ppg": ppg,
        "games_count": total_games
    }


def get_h2h_history(home: str, away: str, sport: str, days_back: int = 90) -> str:
    """Получает историю личных встреч двух команд"""
    completed = fetch_completed_games(sport, days_back)
    
    h2h_games = []
    for game in completed:
        home_team = game.get("home_team")
        away_team = game.get("away_team")
        
        if (home_team == home and away_team == away) or (home_team == away and away_team == home):
            scores = game.get("scores", {})
            home_score = scores.get(home_team, 0) if isinstance(scores, dict) else 0
            away_score = scores.get(away_team, 0) if isinstance(scores, dict) else 0
            
            if home_score == 0 and away_score == 0:
                continue
            
            # Определяем победителя
            winner = home_team if home_score > away_score else away_team
            
            # Формируем строку
            date = game.get("commence_time", "")
            if date:
                dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
                date_str = dt.strftime("%d.%m")
            else:
                date_str = "?"
            
            h2h_games.append(f"{date_str}: {home_team} {home_score}—{away_score} {away_team} ({'победа ' + winner})")
    
    if h2h_games:
        return "; ".join(h2h_games[:5])
    return "Нет данных о личных встречах за последние 90 дней"


def get_injuries_info(team_name: str, sport: str) -> str:
    """Информация о травмах (пока заглушка, потом добавим ESPN)"""
    # TODO: подключить ESPN API для реальных травм
    return "Данные загружаются"


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
    
    # 3. Обновляем историю из завершённых матчей
    print("  📊 Обновляем историю угадываний...")
    completed = fetch_completed_games(sport_key, 14)
    
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
    
    # Предварительно загружаем историю для всех команд (один раз)
    print("  📊 Загружаем статистику для расчёта формы команд...")
    all_completed = fetch_completed_games(sport_key, 30)
    
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
        
        # ПОЛУЧАЕМ ФОРМУ КОМАНД ИЗ ИСТОРИИ
        print(f"  📊 [{idx}/{total_games}] Анализ формы: {home} – {away}")
        
        home_stats = get_team_form(home, sport_key, 30)
        away_stats = get_team_form(away, sport_key, 30)
        
        h2h = get_h2h_history(home, away, sport_key, 90)
        
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
            "home_streak": home_stats["streak"],
            "away_streak": away_stats["streak"],
            "home_win_pct": home_stats["win_pct"],
            "away_win_pct": away_stats["win_pct"],
            "home_ppg": home_stats["ppg"],
            "away_ppg": away_stats["ppg"],
            # История встреч
            "h2h": h2h,
            "data_source": "Коэффициенты + история матчей Odds API"
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
        
        streak_home = f"+{home_stats['streak']}" if home_stats['streak'] > 0 else str(home_stats['streak'])
        streak_away = f"+{away_stats['streak']}" if away_stats['streak'] > 0 else str(away_stats['streak'])
        print(f"  ✅ [{idx}/{total_games}] {home} – {away}: {winner} ({prob}%) | форма {home_stats['form']} ({streak_home}) vs {away_stats['form']} ({streak_away})")
    
    # 5. Сохраняем
    with open(matches_file, "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": league, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    all_backup = new_backup + backup["predictions"]
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump({"predictions": all_backup}, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ Сохранено {len(matches)} матчей")


def main():
    print("🚀 ЗАПУСК ПРОГНОЗОВ С ФОРМОЙ ИЗ ИСТОРИИ")
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
