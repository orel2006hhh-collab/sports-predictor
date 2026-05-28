#!/usr/bin/env python3
"""
ПОЛНОЕ АВТООБНОВЛЕНИЕ САЙТА ПРОГНОЗОВ (ВАРИАНТ Б)
- Сохраняет прогнозы перед обновлением
- Сравнивает с реальными результатами
- Накопливает статистику
- Обновляет предстоящие матчи
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
SPORT = "basketball_nba"
REGIONS = "us,uk,eu"
MARKETS = "h2h,spreads"

# ============================================================
# РАБОТА С ФАЙЛАМИ
# ============================================================

def get_repo_root() -> str:
    """Возвращает путь к корню репозитория"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)

def load_matches() -> Dict:
    """Загружает текущие матчи из matches.json"""
    path = os.path.join(get_repo_root(), "data", "matches.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"matches": []}

def save_matches(matches: Dict):
    """Сохраняет матчи в matches.json"""
    path = os.path.join(get_repo_root(), "data", "matches.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)
    print(f"✅ Сохранено {len(matches.get('matches', []))} предстоящих матчей")

def load_history() -> Dict:
    """Загружает историю прогнозов из history.json"""
    path = os.path.join(get_repo_root(), "data", "history.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"predictions": []}

def save_history(history: Dict):
    """Сохраняет историю прогнозов в history.json"""
    path = os.path.join(get_repo_root(), "data", "history.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"✅ Сохранено {len(history.get('predictions', []))} записей в истории")

def load_predictions_backup() -> Dict:
    """Загружает сохранённые прогнозы из backup файла"""
    path = os.path.join(get_repo_root(), "data", "predictions_backup.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"predictions": []}

def save_predictions_backup(predictions: Dict):
    """Сохраняет прогнозы в backup файл"""
    path = os.path.join(get_repo_root(), "data", "predictions_backup.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)
    print(f"💾 Сохранено {len(predictions.get('predictions', []))} прогнозов в бэкап")

# ============================================================
# РАБОТА С API
# ============================================================

def fetch_upcoming_games() -> List[Dict]:
    """Получает предстоящие матчи из API"""
    if not ODDS_API_KEY:
        print("❌ API ключ не найден")
        return []
    
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": "american",
        "dateFormat": "iso"
    }
    
    try:
        print("📡 Запрос предстоящих матчей...")
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            print(f"❌ Ошибка: {response.status_code}")
            return []
        
        remaining = response.headers.get("x-requests-remaining")
        if remaining:
            print(f"📊 Осталось запросов: {remaining}")
        
        data = response.json()
        print(f"✅ Получено {len(data)} предстоящих матчей")
        return data
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

def fetch_completed_games(days_back: int = 14) -> List[Dict]:
    """
    Получает завершённые матчи за последние N дней
    Возвращает только те, у которых есть явный победитель
    """
    if not ODDS_API_KEY:
        return []
    
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/scores"
    params = {
        "apiKey": ODDS_API_KEY,
        "daysFrom": days_back,
        "dateFormat": "iso"
    }
    
    try:
        print(f"📊 Запрос результатов за последние {days_back} дней...")
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            print(f"⚠️ Ошибка получения результатов: {response.status_code}")
            return []
        
        games = response.json()
        
        # Фильтруем только завершённые матчи с явным счётом
        completed = []
        for game in games:
            if not game.get("completed", False):
                continue
            
            scores = game.get("scores", {})
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            
            home_score = scores.get(home, 0) if isinstance(scores, dict) else 0
            away_score = scores.get(away, 0) if isinstance(scores, dict) else 0
            
            if home_score > 0 or away_score > 0:
                completed.append(game)
        
        print(f"✅ Найдено завершённых матчей: {len(completed)}")
        return completed
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

def american_to_probability(american_odds: int) -> float:
    """Конвертирует американские коэффициенты в вероятность (0-1)"""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)

def calculate_winner_and_prob(bookmakers: List[Dict]) -> tuple:
    """Рассчитывает победителя и вероятность на основе коэффициентов"""
    if not bookmakers:
        return ("Неизвестно", 50)
    
    best_odds = {}
    for bookmaker in bookmakers:
        for market in bookmaker.get("markets", []):
            if market["key"] == "h2h":
                for outcome in market["outcomes"]:
                    team = outcome["name"]
                    price = outcome["price"]
                    if team not in best_odds or price > best_odds[team]:
                        best_odds[team] = price
    
    if len(best_odds) < 2:
        return ("Неизвестно", 50)
    
    teams = list(best_odds.keys())
    prob1 = american_to_probability(best_odds[teams[0]])
    prob2 = american_to_probability(best_odds[teams[1]])
    
    total = prob1 + prob2
    prob1_norm = (prob1 / total) * 100
    prob2_norm = (prob2 / total) * 100
    
    if prob1_norm > prob2_norm:
        return (teams[0], round(prob1_norm))
    else:
        return (teams[1], round(prob2_norm))

def convert_to_site_format(api_games: List[Dict]) -> tuple:
    """
    Конвертирует данные из API в формат вашего сайта.
    Возвращает (matches_list, predictions_backup_list)
    """
    matches = []
    predictions_backup = []
    
    for game in api_games:
        home_team = game.get("home_team", "Unknown")
        away_team = game.get("away_team", "Unknown")
        
        # Конвертируем дату и время
        commence_time = game.get("commence_time", "")
        if commence_time:
            dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
            dt_msk = dt + timedelta(hours=3)
            date_str = dt_msk.strftime("%d.%m.%Y")
            time_str = dt_msk.strftime("%H:%M МСК")
            iso_date = dt_msk.isoformat()
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "04:30 МСК"
            iso_date = datetime.now().isoformat()
        
        winner, prob = calculate_winner_and_prob(game.get("bookmakers", []))
        
        # Формат для matches.json (для сайта)
        match = {
            "date": date_str,
            "time": time_str,
            "home": home_team,
            "away": away_team,
            "home_ppg": 0,
            "away_ppg": 0,
            "home_win_pct": 0,
            "away_win_pct": 0,
            "winner": winner,
            "prob": prob,
            "total_prediction": f"Автообновление {datetime.now().strftime('%d.%m %H:%M')}",
            "home_form": "Из API",
            "away_form": "Из API",
            "home_streak": "N/A",
            "away_streak": "N/A",
            "h2h": f"Данные The Odds API · {datetime.now().strftime('%Y-%m-%d')}",
            "injuries": "Данные из API",
            "data_source": f"The Odds API · {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        }
        matches.append(match)
        
        # Формат для predictions_backup.json (для сравнения с результатами)
        backup_entry = {
            "date": date_str,
            "iso_date": iso_date,
            "home": home_team,
            "away": away_team,
            "prediction": winner,
            "prob": prob
        }
        predictions_backup.append(backup_entry)
    
    return matches, predictions_backup

# ============================================================
# ОСНОВНАЯ ЛОГИКА ОБНОВЛЕНИЯ СТАТИСТИКИ
# ============================================================

def update_statistics():
    """
    Сравнивает прошедшие матчи с сохранёнными прогнозами
    и добавляет результаты в историю.
    История НАКАПЛИВАЕТСЯ, ничего не удаляется.
    """
    print("\n" + "=" * 50)
    print("📊 ОБНОВЛЕНИЕ СТАТИСТИКИ")
    print("=" * 50)
    
    # Загружаем текущую историю
    history = load_history()
    existing_predictions = history.get("predictions", [])
    
    # Создаём множество ключей уже обработанных матчей
    processed_keys = set()
    for pred in existing_predictions:
        key = f"{pred.get('date')}_{pred.get('home')}_{pred.get('away')}"
        processed_keys.add(key)
    
    # Загружаем сохранённые прогнозы из бэкапа
    backup = load_predictions_backup()
    backup_predictions = backup.get("predictions", [])
    
    if not backup_predictions:
        print("⚠️ Нет сохранённых прогнозов для сравнения")
        print("   (Это нормально для первого запуска)")
        return
    
    # Получаем завершённые матчи за последние 14 дней
    completed_games = fetch_completed_games(days_back=14)
    
    if not completed_games:
        print("📭 Нет завершённых матчей для обработки")
        return
    
    # Создаём словарь прогнозов для быстрого поиска по дате и командам
    predictions_dict = {}
    for pred in backup_predictions:
        key = f"{pred.get('date')}_{pred.get('home')}_{pred.get('away')}"
        predictions_dict[key] = pred
    
    new_entries = []
    
    for game in completed_games:
        # Извлекаем данные из API
        commence_time = game.get("commence_time", "")
        if not commence_time:
            continue
            
        dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        dt_msk = dt + timedelta(hours=3)
        date_str = dt_msk.strftime("%d.%m.%Y")
        
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        
        if not home or not away:
            continue
        
        # Ключ для поиска прогноза
        match_key = f"{date_str}_{home}_{away}"
        
        # Проверяем, не добавлен ли уже этот матч в историю
        if match_key in processed_keys:
            print(f"⏭️ Уже в истории: {home} vs {away}")
            continue
        
        # Ищем прогноз для этого матча
        prediction_data = predictions_dict.get(match_key)
        
        if not prediction_data:
            print(f"⚠️ Нет прогноза для матча: {home} vs {away} ({date_str})")
            continue
        
        # Определяем фактического победителя по счёту
        scores = game.get("scores", {})
        home_score = 0
        away_score = 0
        
        if isinstance(scores, dict):
            home_score = scores.get(home, 0)
            away_score = scores.get(away, 0)
        
        if home_score == 0 and away_score == 0:
            print(f"⚠️ Нет счёта для матча: {home} vs {away}")
            continue
        
        if home_score > away_score:
            actual_winner = home
            actual_score = f"{home_score}-{away_score}"
        else:
            actual_winner = away
            actual_score = f"{home_score}-{away_score}"
        
        # Сравниваем прогноз с результатом
        predicted_winner = prediction_data.get("prediction")
        prob = prediction_data.get("prob", 50)
        
        if predicted_winner == actual_winner:
            result_status = "success"
            result_emoji = "✅"
        else:
            result_status = "failed"
            result_emoji = "❌"
        
        # Создаём запись для истории
        new_entry = {
            "date": date_str,
            "home": home,
            "away": away,
            "league": "NBA",
            "prediction": predicted_winner,
            "result": result_status,
            "actual_score": actual_score,
            "prob": prob
        }
        
        new_entries.append(new_entry)
        print(f"{result_emoji} {home} vs {away}")
        print(f"   Прогноз: {predicted_winner} | Факт: {actual_winner} ({actual_score})")
    
    # Добавляем новые записи в начало списка (свежие сверху)
    if new_entries:
        all_predictions = new_entries + existing_predictions
        save_history({"predictions": all_predictions})
        print(f"\n✨ Добавлено {len(new_entries)} новых записей в историю")
        
        # Выводим общую статистику
        total = len(all_predictions)
        successes = len([p for p in all_predictions if p.get("result") == "success"])
        accuracy = round((successes / total) * 100) if total > 0 else 0
        print(f"\n📊 ТЕКУЩАЯ ТОЧНОСТЬ: {accuracy}% ({successes}/{total})")
    else:
        print("📭 Новых результатов для добавления нет")

def update_upcoming_matches():
    """Обновляет список предстоящих матчей и сохраняет бэкап прогнозов"""
    print("\n" + "=" * 50)
    print("🏀 ОБНОВЛЕНИЕ ПРЕДСТОЯЩИХ МАТЧЕЙ")
    print("=" * 50)
    
    games = fetch_upcoming_games()
    
    if not games:
        print("❌ Не удалось получить данные о матчах")
        return False
    
    # Конвертируем в формат сайта и получаем бэкап прогнозов
    matches, predictions_backup = convert_to_site_format(games)
    
    # Сохраняем матчи для сайта
    save_matches({"matches": matches})
    
    # Сохраняем бэкап прогнозов для будущего сравнения
    save_predictions_backup({"predictions": predictions_backup})
    
    print(f"📋 Сохранено прогнозов на будущее: {len(predictions_backup)}")
    return True

# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    print("🚀 ЗАПУСК АВТООБНОВЛЕНИЯ (ВАРИАНТ Б)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not ODDS_API_KEY:
        print("❌ ОШИБКА: API ключ не найден!")
        print("   Добавьте секрет ODDS_API_KEY в GitHub Secrets")
        return
    
    # Шаг 1: Обновляем статистику (сравниваем прошедшие матчи с сохранёнными прогнозами)
    update_statistics()
    
    # Шаг 2: Обновляем предстоящие матчи и сохраняем новые прогнозы
    update_upcoming_matches()
    
    print("\n" + "=" * 50)
    print("✨ ВСЕ ОБНОВЛЕНИЯ ЗАВЕРШЕНЫ")
    print("=" * 50)

if __name__ == "__main__":
    main()
