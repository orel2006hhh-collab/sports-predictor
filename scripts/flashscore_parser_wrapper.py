#!/usr/bin/env python3
"""
ОБНОВЛЕНИЕ ДАННЫХ ЧЕРЕЗ FLASHSCORE-PARSER
"""

import json
import os
import subprocess
from datetime import datetime

def main():
    print("🚀 Запуск flashscore-parser...")
    
    # Создаем папку data если нет
    os.makedirs("data", exist_ok=True)
    
    # Запускаем парсер (сохраняет в data/flashscore.json)
    result = subprocess.run([
        "python", "-m", "flashscore_parser",
        "--sport", "basketball",
        "--league", "nba",
        "--output", "data/flashscore.json"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ Ошибка парсера:")
        print(result.stderr)
        return
    
    # Загружаем результат
    with open("data/flashscore.json", "r") as f:
        parsed_data = json.load(f)
    
    # Преобразуем в нужный формат для сайта
    matches = []
    for game in parsed_data.get("games", []):
        match = {
            "date": game.get("date", ""),
            "time": game.get("time", ""),
            "home": game.get("home_team", {}).get("name", ""),
            "away": game.get("away_team", {}).get("name", ""),
            "home_score": game.get("home_team", {}).get("score", None),
            "away_score": game.get("away_team", {}).get("score", None),
            "status": game.get("status", ""),
            "home_form": game.get("home_team", {}).get("form", None),
            "away_form": game.get("away_team", {}).get("form", None),
        }
        matches.append(match)
    
    # Сохраняем в нужный файл
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({
            "matches": matches,
            "last_updated": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Сохранено {len(matches)} матчей")

if __name__ == "__main__":
    main()
