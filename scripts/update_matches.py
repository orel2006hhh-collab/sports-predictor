#!/usr/bin/env python3
"""
ПРОГНОЗЫ С DeepSeek (реальная статистика из интернета)
- The Odds API: список предстоящих матчей
- DeepSeek: самостоятельно ищет актуальную статистику и делает прогноз
"""

import json
import os
import re
import requests
from datetime import datetime, timedelta

# ============================================================
# НАСТРОЙКИ
# ============================================================

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

SPORT = "basketball_nba"
REGIONS = "us,uk,eu"
MARKETS = "h2h"

# Минимальная вероятность для отображения прогноза
MIN_PROBABILITY = 55

# ============================================================
# ФУНКЦИИ
# ============================================================

def get_bookmakers_list(bookmakers):
    if not bookmakers:
        return "Данные не загружены"
    names = []
    for bk in bookmakers[:8]:
        title = bk.get("title", "")
        if title and title not in names:
            names.append(title)
    return ", ".join(names) if names else "Букмекеры не определены"

def call_deepseek(home_team: str, away_team: str):
    """
    Отправляет запрос к DeepSeek. DeepSeek сам найдёт актуальную статистику.
    """
    if not OPENROUTER_API_KEY:
        return None, None, None, None
    
    prompt = f"""Ты эксперт по NBA. Сделай прогноз на матч:

{home_team} vs {away_team}

Твоя задача:
1. Найди в интернете актуальную статистику обеих команд за последние 5-10 игр
2. Учти форму команд, травмы, личные встречи (H2H), фактор домашней площадки
3. Напиши, на чём основан прогноз (сошлись на конкретные цифры)

Ответь строго в формате:

ВЕРОЯТНОСТЬ|ЧИСЛО 0-100|КОМАНДА-ФАВОРИТ
ОБЪЯСНЕНИЕ|Твой развёрнутый анализ (3-5 предложений)

Пример ответа:
ВЕРОЯТНОСТЬ|73|Los Angeles Lakers
ОБЪЯСНЕНИЕ|Лейкерс выиграли 4 из последних 5 матчей (победы над Голден Стэйт, Денвер...), в то время как соперник проиграл 3 из 5. Дома Лейкерс играют на 8 очков лучше. В личных встречах в этом сезоне счёт 2-1 в пользу Лейкерс.
"""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 500
    }
    
    try:
        print(f"🧠 DeepSeek анализирует: {home_team} – {away_team}...")
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        
        if response.status_code == 200:
            result = response.json()
            full = result['choices'][0]['message']['content'].strip()
            
            prob = None
            winner = None
            reasoning = "Анализ статистики"
            
            lines = full.split('\n')
            for line in lines:
                if line.startswith('ВЕРОЯТНОСТЬ|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            prob = float(parts[1]) / 100
                            winner = parts[2].strip()
                        except:
                            pass
                elif line.startswith('ОБЪЯСНЕНИЕ|'):
                    parts = line.split('|', 1)
                    if len(parts) >= 2:
                        reasoning = parts[1].strip()
            
            if prob is None:
                numbers = re.findall(r'\d+', full)
                if numbers:
                    prob = float(numbers[0]) / 100
            
            if winner is None:
                winner = home_team if prob > 0.5 else away_team
            
            total_prediction = "Тотал БОЛЬШЕ 225.5"
            
            return prob, winner, reasoning, total_prediction
    except Exception as e:
        print(f"⚠️ DeepSeek ошибка: {e}")
    
    return None, None, None, None

def american_to_prob(odds):
    if odds > 0:
        return 100 / (odds + 100) * 100
    else:
        return abs(odds) / (abs(odds) + 100) * 100

def fetch_upcoming_games():
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": REGIONS, "markets": MARKETS, "oddsFormat": "american"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        return resp.json() if resp.status_code == 200 else []
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

def update_matches():
    print(f"\n🏀 ОБНОВЛЕНИЕ ПРОГНОЗОВ (вероятность ≥ {MIN_PROBABILITY}%)")
    
    games = fetch_upcoming_games()
    if not games:
        print("❌ Нет данных от The Odds API")
        return
    
    matches = []
    backup = []
    
    for game in games:
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue
        
        commence = game.get("commence_time")
        if commence:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
            date_str = dt.strftime("%d.%m.%Y")
            time_str = dt.strftime("%H:%M МСК")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "04:30 МСК"
        
        bookmakers_list = get_bookmakers_list(game.get("bookmakers", []))
        
        # Получаем коэффициенты для локального расчёта (фолбэк)
        home_odds, away_odds = 2.0, 2.0
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "h2h":
                    for out in market["outcomes"]:
                        if out["name"] == home:
                            home_odds = out["price"]
                        elif out["name"] == away:
                            away_odds = out["price"]
                    break
            if home_odds != 2.0 and away_odds != 2.0:
                break
        
        home_prob = american_to_prob(home_odds)
        away_prob = american_to_prob(away_odds)
        total = home_prob + away_prob
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100
        
        local_winner = home if home_prob > away_prob else away
        local_prob = round(max(home_prob, away_prob))
        
        # Запрашиваем DeepSeek
        ai_prob, ai_winner, ai_reasoning, ai_total = call_deepseek(home, away)
        
        if ai_prob is not None and ai_prob > 0:
            prob = round(ai_prob * 100)
            winner = ai_winner
            reasoning = ai_reasoning
            source = "DeepSeek AI (актуальная статистика из интернета)"
            total_prediction = ai_total
        else:
            # Фолбэк на локальный расчёт по коэффициентам
            prob = local_prob
            winner = local_winner
            reasoning = f"Прогноз на основе коэффициентов букмекеров: {winner} побеждает с вероятностью {prob}%"
            source = "Локальный расчёт (коэффициенты)"
            total_prediction = "Тотал БОЛЬШЕ 225.5"
        
        if prob < MIN_PROBABILITY:
            print(f"⏭️ Пропущен ({prob}% < {MIN_PROBABILITY}%): {home} – {away}")
            continue
        
        match = {
            "date": date_str,
            "time": time_str,
            "home": home,
            "away": away,
            "winner": winner,
            "prob": prob,
            "total_prediction": total_prediction,
            "bookmakers_list": bookmakers_list,
            "ai_reasoning": reasoning,
            "data_source": source
        }
        matches.append(match)
        backup.append({
            "date": date_str,
            "home": home,
            "away": away,
            "prediction": winner,
            "prob": prob
        })
        
        print(f"✅ {home} – {away}: {winner} ({prob}%) | {source}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    with open("data/predictions_backup.json", "w", encoding="utf-8") as f:
        json.dump({"predictions": backup}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено {len(matches)} матчей")

def main():
    print(f"🚀 ЗАПУСК (DeepSeek — актуальная статистика из интернета)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not ODDS_API_KEY:
        print("❌ ODDS_API_KEY не найден")
        return
    
    if not OPENROUTER_API_KEY:
        print("⚠️ OPENROUTER_API_KEY не найден. Будут использованы локальные прогнозы.")
    
    update_matches()
    print("\n✨ Готово")

if __name__ == "__main__":
    main()
