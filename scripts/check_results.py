#!/usr/bin/env python3
"""
Проверка результатов прошедших матчей и обновление статистики
"""

import json
import os
import requests
from datetime import datetime, timedelta

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

SPORT = "basketball_nba"
REGIONS = "us,uk,eu"

def fetch_completed_games():
    """Получение завершённых матчей за последние 2 дня"""
    if not ODDS_API_KEY:
        return []
    
    # Дата от (2 дня назад) до сегодня
    date_from = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    date_to = datetime.now().strftime("%Y-%m-%d")
    
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/scores"
    params = {
        "apiKey": ODDS_API_KEY,
        "daysFrom": 2,
        "dateFormat": "iso"
    }
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            games = resp.json()
            # Фильтруем только завершённые
            completed = [g for g in games if g.get("completed")]
            print(f"Найдено завершённых матчей: {len(completed)}")
            return completed
        else:
            print(f"Ошибка API: {resp.status_code}")
            return []
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

def load_predictions():
    """Загружает последние прогнозы из matches.json"""
    try:
        with open("data/matches.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("matches", [])
    except:
        return []

def load_results_history():
    """Загружает историю результатов"""
    try:
        with open("data/results.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"results": [], "stats": {"total": 0, "correct": 0, "accuracy": 0}}

def save_results_history(history):
    """Сохраняет историю результатов"""
    os.makedirs("data", exist_ok=True)
    with open("data/results.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def check_match_result(prediction, actual_game):
    """Проверяет, угадан ли прогноз"""
    home_team = prediction["home"]
    away_team = prediction["away"]
    
    # Получаем реальный счёт
    home_score = actual_game.get("home_score")
    away_score = actual_game.get("away_score")
    
    if home_score is None or away_score is None:
        return None
    
    # Определяем реального победителя
    if home_score > away_score:
        actual_winner = home_team
    elif away_score > home_score:
        actual_winner = away_team
    else:
        actual_winner = "Ничья"
    
    # Проверяем победителя
    winner_correct = (prediction["winner"] == actual_winner)
    
    # Проверяем тотал
    predicted_total = prediction.get("total_prediction", "")
    total_line = float(predicted_total.split()[-1]) if predicted_total.split() else 225.5
    actual_total = home_score + away_score
    
    if "БОЛЬШЕ" in predicted_total:
        total_correct = (actual_total > total_line)
    else:
        total_correct = (actual_total < total_line)
    
    return {
        "date": prediction["date"],
        "home": home_team,
        "away": away_team,
        "predicted_winner": prediction["winner"],
        "actual_winner": actual_winner,
        "winner_correct": winner_correct,
        "predicted_total": predicted_total,
        "actual_total": actual_total,
        "total_correct": total_correct,
        "home_score": home_score,
        "away_score": away_score,
        "checked_at": datetime.now().isoformat()
    }

def update_statistics():
    """Основная функция обновления статистики"""
    print("=== ПРОВЕРКА РЕЗУЛЬТАТОВ МАТЧЕЙ ===")
    print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Загружаем прогнозы
    predictions = load_predictions()
    if not predictions:
        print("Нет прогнозов для проверки")
        return
    
    print(f"Загружено прогнозов: {len(predictions)}")
    
    # Загружаем завершённые матчи
    completed_games = fetch_completed_games()
    if not completed_games:
        print("Нет завершённых матчей для проверки")
        return
    
    # Загружаем историю результатов
    history = load_results_history()
    existing_results = {f"{r['home']}_{r['away']}_{r['date']}" for r in history["results"]}
    
    new_results = []
    
    for prediction in predictions:
        match_key = f"{prediction['home']}_{prediction['away']}_{prediction['date']}"
        
        # Пропускаем уже проверенные
        if match_key in existing_results:
            continue
        
        # Ищем реальный матч
        for game in completed_games:
            if game.get("home_team") == prediction["home"] and game.get("away_team") == prediction["away"]:
                result = check_match_result(prediction, game)
                if result:
                    new_results.append(result)
                    print(f"\n📊 {prediction['home']} vs {prediction['away']}")
                    print(f"   Прогноз: {prediction['winner']} | {prediction['total_prediction']}")
                    print(f"   Результат: {result['actual_winner']} ({result['home_score']}:{result['away_score']})")
                    print(f"   Тотал: {result['actual_total']}")
                    print(f"   Победитель: {'✅' if result['winner_correct'] else '❌'}")
                    print(f"   Тотал: {'✅' if result['total_correct'] else '❌'}")
                break
    
    # Добавляем новые результаты
    if new_results:
        history["results"].extend(new_results)
        
        # Пересчитываем статистику
        total = len(history["results"])
        correct_winners = sum(1 for r in history["results"] if r["winner_correct"])
        correct_totals = sum(1 for r in history["results"] if r["total_correct"])
        
        history["stats"] = {
            "total": total,
            "correct_winners": correct_winners,
            "correct_totals": correct_totals,
            "winners_accuracy": round(correct_winners / total * 100, 1) if total > 0 else 0,
            "totals_accuracy": round(correct_totals / total * 100, 1) if total > 0 else 0,
            "last_updated": datetime.now().isoformat()
        }
        
        save_results_history(history)
        print(f"\n✅ Добавлено новых результатов: {len(new_results)}")
        print(f"📊 Всего проверено: {total}")
        print(f"📊 Точность победителей: {history['stats']['winners_accuracy']}%")
        print(f"📊 Точность тоталов: {history['stats']['totals_accuracy']}%")
    else:
        print("\nНовых результатов для добавления нет")
    
    print("\n=== ГОТОВО ===")

def main():
    update_statistics()

if __name__ == "__main__":
    main()
