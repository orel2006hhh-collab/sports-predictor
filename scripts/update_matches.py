#!/usr/bin/env python3
"""
Автоматическое обновление матчей из The Odds API
"""

import json
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List

# ============================================================
# НАСТРОЙКИ
# ============================================================

# API ключ берется из секретов GitHub
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

# Спорт: basketball_nba, basketball_wnba, basketball_euroleague
SPORT = "basketball_nba"

# Регионы букмекеров (us, uk, eu)
REGIONS = "us,uk,eu"

# Рынки ставок
MARKETS = "h2h,spreads"

# ============================================================
# ФУНКЦИИ
# ============================================================

def fetch_upcoming_games() -> List[Dict[str, Any]]:
    """Получает список предстоящих матчей из The Odds API"""
    
    if not ODDS_API_KEY or ODDS_API_KEY == "ВАШ_API_КЛЮЧ":
        print("❌ ОШИБКА: API ключ не найден!")
        print("   Убедитесь, что вы добавили секрет ODDS_API_KEY в GitHub Secrets")
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
        print(f"📡 Запрос к The Odds API...")
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            print(f"❌ Ошибка API: {response.status_code}")
            return []
        
        # Информация о лимитах
        remaining = response.headers.get("x-requests-remaining")
        if remaining:
            print(f"📊 Осталось запросов: {remaining} из 500")
        
        data = response.json()
        print(f"✅ Получено {len(data)} матчей")
        return data
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

def american_to_probability(american_odds: int) -> float:
    """Конвертирует американские коэффициенты в вероятность (0-1)"""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)

def calculate_probability(bookmakers: List[Dict]) -> tuple:
    """
    Конвертирует коэффициенты букмекеров в вероятность победы.
    Возвращает (победитель, вероятность_в_процентах)
    """
    if not bookmakers:
        return ("Неизвестно", 50)
    
    # Собираем лучшие коэффициенты для каждой команды
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

def convert_to_site_format(api_games: List[Dict]) -> Dict:
    """Конвертирует данные из API в формат вашего сайта"""
    
    matches = []
    
    for game in api_games:
        home_team = game.get("home_team", "Unknown")
        away_team = game.get("away_team", "Unknown")
        
        # Конвертируем дату и время
        commence_time = game.get("commence_time", "")
        if commence_time:
            dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
            dt_msk = dt + timedelta(hours=3)  # МСК = UTC+3
            date_str = dt_msk.strftime("%d.%m.%Y")
            time_str = dt_msk.strftime("%H:%M МСК")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "04:30 МСК"
        
        # Рассчитываем вероятность победы
        winner, prob = calculate_probability(game.get("bookmakers", []))
        
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
    
    return {"matches": matches}

def update_matches_file(new_data: Dict):
    """Обновляет файл matches.json в репозитории"""
    
    # Определяем путь к файлу (от корня репозитория)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    matches_path = os.path.join(repo_root, "data", "matches.json")
    
    with open(matches_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Файл обновлен: {matches_path}")
    print(f"   Сохранено матчей: {len(new_data['matches'])}")

# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    print("🚀 Запуск автоматического обновления матчей")
    print("=" * 50)
    
    # Проверяем API ключ
    if not ODDS_API_KEY:
        print("⚠️ ВНИМАНИЕ: API ключ не найден!")
        print("   Добавьте секрет ODDS_API_KEY в GitHub Secrets")
        return
    
    # Получаем данные
    games = fetch_upcoming_games()
    
    if not games:
        print("❌ Не удалось получить данные о матчах")
        print("   Проверьте API ключ и интернет-соединение")
        return
    
    # Конвертируем в формат сайта
    site_data = convert_to_site_format(games)
    
    print(f"\n📋 Найдено матчей: {len(site_data['matches'])}")
    for match in site_data['matches'][:5]:
        print(f"   • {match['home']} vs {match['away']}")
        print(f"     → Прогноз: {match['winner']} ({match['prob']}%)")
    
    # Обновляем файл
    update_matches_file(site_data)
    
    print("\n✨ Обновление завершено!")

if __name__ == "__main__":
    main()
