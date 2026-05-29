#!/usr/bin/env python3
"""
ПРОСТЫЕ ПРОГНОЗЫ НА ОСНОВЕ КОЭФФИЦИЕНТОВ
- Без нейросетей
- Только вероятность победы
- Сохраняем прогнозы для истории
"""

import json
import os
import requests
from datetime import datetime, timedelta

# ============================================================
# НАСТРОЙКИ
# ============================================================

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

SPORT_NBA = "basketball_nba"
SPORT_NHL = "icehockey_nhl"

# Минимальная вероятность для показа прогноза (55% = 1.82 коэффициенту)
MIN_PROB = 55

TOTAL_LINE_NBA = 225.5
TOTAL_LINE_NHL = 6.5

# ============================================================
# ФУНКЦИИ
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
    print(f"\n{'🏀' if league == 'nba' else '🏒'} {league.upper()}")
    
    total_line = TOTAL_LINE_NBA if league == "nba" else TOTAL_LINE_NHL
    
    # 1. Загружаем существующую историю
    history_file = f"data/{league}_history.json"
    backup_file = f"data/{league}_backup.json"
    matches_file = f"data/{league}_matches.json"
    
    history = {"predictions": []}
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            history = json.load(f)
    
    # 2. Загружаем существующий бэкап (старые прогнозы)
    backup = {"predictions": []}
    if os.path.exists(backup_file):
        with open(backup_file, "r") as f:
            backup = json.load(f)
    
    # 3. Получаем завершённые матчи и обновляем историю
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
        
        if key in existing_history:
            continue
        
        if key not in backup_dict:
            continue
        
        scores = game.get("scores", {})
        home_score = scores.get(home, 0)
        away_score = scores.get(away, 0)
        
        if home_score == 0 and away_score == 0:
            continue
        
        # Кто победил на самом деле
        actual_winner = home if home_score > away_score else away
        
        # Что мы прогнозировали
        predicted = backup_dict[key]["prediction"]
        prob = backup_dict[key]["prob"]
        
        # Угадали?
        result = "✅" if predicted == actual_winner else "❌"
        
        # Тотал
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
    
    for game in games:
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue
        
        # Дата
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
        
        # Нормируем (сумма вероятностей часто >100%)
        total = home_prob + away_prob
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100
        
        # Фаворит
        if home_prob > away_prob:
            winner = home
            prob = round(home_prob)
        else:
            winner = away
            prob = round(away_prob)
        
        # Пропускаем низкую вероятность
        if prob < MIN_PROB:
            print(f"  ⏭️ Пропущен ({prob}%): {home} – {away}")
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
        
        match = {
            "date": date_str,
            "time": time_str,
            "home": home,
            "away": away,
            "winner": winner,
            "prob": prob,
            "total_prediction": f"Тотал {total_direction} {total_line}",
            "data_source": "Коэффициенты букмекеров"
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
        
        print(f"  ✅ {home} – {away}: {winner} ({prob}%)")
    
    # 5. Сохраняем
    with open(matches_file, "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": league, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    # Объединяем старый и новый бэкап
    all_backup = new_backup + backup["predictions"]
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump({"predictions": all_backup}, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ Сохранено {len(matches)} матчей")


def main():
    print("🚀 ЗАПУСК ПРОГНОЗОВ")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Минимальная вероятность: {MIN_PROB}%")
    
    if not ODDS_API_KEY:
        print("❌ ODDS_API_KEY не найден")
        return
    
    # Создаем папку data если нет
    os.makedirs("data", exist_ok=True)
    
    update_league("nba", SPORT_NBA)
    update_league("nhl", SPORT_NHL)
    
    print("\n✨ Готово")


if __name__ == "__main__":
    main()
