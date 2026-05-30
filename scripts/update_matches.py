#!/usr/bin/env python3
import json
import os
import requests
from datetime import datetime, timedelta

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

SPORT = "basketball_nba"
REGIONS = "us,uk,eu"
MARKETS = "h2h,totals"
MIN_PROBABILITY = 0

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
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

def get_bookmakers_list(bookmakers):
    if not bookmakers:
        return "Нет данных"
    names = [bk.get("title", "") for bk in bookmakers[:5] if bk.get("title")]
    return ", ".join(names) if names else "Букмекеры"

def get_total_line(bookmakers):
    for bk in bookmakers:
        for market in bk.get("markets", []):
            if market["key"] == "totals":
                for outcome in market["outcomes"]:
                    if outcome.get("point"):
                        return outcome["point"]
    return 225.5

def call_deepseek(home_team, away_team, total_line):
    """DeepSeek сам ищет статистику в интернете и делает прогноз"""
    if not OPENROUTER_API_KEY:
        return None, None, None, None, None, None, None, None
    
    prompt = f"""Ты эксперт по NBA. Сделай прогноз на матч:

{home_team} (дома) vs {away_team} (в гостях)

Найди в интернете актуальную статистику за последние 5-7 дней:

Для {home_team} (хозяева):
1. Форма дома (последние 5 домашних игр: сколько побед и поражений)
2. Средние очки за игру ДОМА (PPG home) за последние 5 домашних матчей
3. Процент побед ДОМА за последние 5 игр

Для {away_team} (гости):
1. Форма в гостях (последние 5 выездных игр: сколько побед и поражений)
2. Средние очки за игру В ГОСТЯХ (PPG away) за последние 5 выездных матчей
3. Процент побед В ГОСТЯХ за последние 5 игр

Линия тотала букмекеров: {total_line}

Верни ответ строго в формате (ничего лишнего, только эти строки):

ФОРМА_ДОМА|{home_team}|X-Y
ФОРМА_ГОСТИ|{away_team}|X-Y
PPG_ДОМА|{home_team}|ЧИСЛО
PPG_ГОСТИ|{away_team}|ЧИСЛО
ПРОЦЕНТ_ДОМА|{home_team}|ЧИСЛО
ПРОЦЕНТ_ГОСТИ|{away_team}|ЧИСЛО
ВЕРОЯТНОСТЬ|ЧИСЛО от 0 до 100
ОБЪЯСНЕНИЕ|Твой анализ в 2-3 предложениях
ТОТАЛ|БОЛЬШЕ или МЕНЬШЕ

Где X-Y — количество побед и поражений (например, 4-1 или 2-3)"""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 600,
        "web_search": True  # КЛЮЧЕВОЕ: DeepSeek ищет в интернете
    }
    
    try:
        print(f"   🧠 DeepSeek ищет статистику в интернете...")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"   📝 Ответ DeepSeek получен")
            
            # Парсим ответ
            home_form = None
            away_form = None
            home_ppg = None
            away_ppg = None
            home_win_pct = None
            away_win_pct = None
            prob = None
            explanation = ""
            total_dir = "БОЛЬШЕ"
            
            for line in content.split('\n'):
                if '|' not in line:
                    continue
                parts = line.split('|')
                if len(parts) < 3:
                    continue
                key = parts[0].strip()
                value = parts[2].strip()
                
                if key == 'ФОРМА_ДОМА':
                    home_form = value
                elif key == 'ФОРМА_ГОСТИ':
                    away_form = value
                elif key == 'PPG_ДОМА':
                    try:
                        home_ppg = float(value)
                    except:
                        pass
                elif key == 'PPG_ГОСТИ':
                    try:
                        away_ppg = float(value)
                    except:
                        pass
                elif key == 'ПРОЦЕНТ_ДОМА':
                    try:
                        home_win_pct = float(value)
                    except:
                        pass
                elif key == 'ПРОЦЕНТ_ГОСТИ':
                    try:
                        away_win_pct = float(value)
                    except:
                        pass
                elif key == 'ВЕРОЯТНОСТЬ':
                    try:
                        prob = float(value)
                    except:
                        pass
                elif key == 'ОБЪЯСНЕНИЕ':
                    explanation = value
                elif key == 'ТОТАЛ':
                    total_dir = value
            
            if prob is None:
                prob = 50
            
            winner = home_team if prob > 50 else away_team
            total_pred = f"Тотал {total_dir} {total_line}"
            
            stats = {
                "home_form": home_form,
                "away_form": away_form,
                "home_ppg": home_ppg,
                "away_ppg": away_ppg,
                "home_win_pct": home_win_pct,
                "away_win_pct": away_win_pct,
            }
            
            return prob, winner, total_pred, explanation, stats
        else:
            print(f"   ❌ DeepSeek ошибка: {response.status_code}")
            return None, None, None, None, None
    except Exception as e:
        print(f"   ❌ DeepSeek исключение: {e}")
        return None, None, None, None, None

def update_matches():
    print("=== ЗАПУСК ОБНОВЛЕНИЯ ===")
    print("Получаем матчи...")
    
    games = fetch_upcoming_games()
    if not games:
        print("Нет данных от API")
        return
    
    matches = []
    
    for game in games:
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue
        
        print(f"\n📋 {home} vs {away}")
        
        commence = game.get("commence_time")
        if commence:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
            date_str = dt.strftime("%d.%m.%Y")
            time_str = dt.strftime("%H:%M")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "04:30"
        
        bookmakers_list = get_bookmakers_list(game.get("bookmakers", []))
        total_line = get_total_line(game.get("bookmakers", []))
        
        # Получаем коэффициенты для запасного варианта
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
        
        home_prob_bm = american_to_prob(home_odds)
        away_prob_bm = american_to_prob(away_odds)
        total_prob = home_prob_bm + away_prob_bm
        home_prob_bm = home_prob_bm / total_prob * 100
        away_prob_bm = away_prob_bm / total_prob * 100
        
        # Запрашиваем прогноз у DeepSeek (он сам ищет статистику)
        result = call_deepseek(home, away, total_line)
        
        if result[0] is not None:
            prob, winner, total_prediction, explanation, stats = result
            prob = round(prob)
            home_form = stats.get("home_form")
            away_form = stats.get("away_form")
            home_ppg = stats.get("home_ppg")
            away_ppg = stats.get("away_ppg")
            home_win_pct = stats.get("home_win_pct")
            away_win_pct = stats.get("away_win_pct")
            reasoning = explanation
            print(f"   🎯 DeepSeek прогноз: {winner} ({prob}%)")
            print(f"   📊 Форма: {home_form} vs {away_form}")
            print(f"   📊 PPG: {home_ppg} vs {away_ppg}")
        else:
            # Запасной вариант — только если DeepSeek не ответил
            prob = round(max(home_prob_bm, away_prob_bm))
            winner = home if home_prob_bm > away_prob_bm else away
            total_prediction = f"Тотал БОЛЬШЕ {total_line}"
            reasoning = f"Прогноз на основе коэффициентов: {winner} ({prob}%)"
            home_form = away_form = "данные не загружены"
            home_ppg = away_ppg = None
            home_win_pct = away_win_pct = None
            print(f"   ⚠️ Локальный прогноз: {winner} ({prob}%)")
        
        if prob < MIN_PROBABILITY:
            print(f"   ⏭️ Пропущен (вероятность {prob}% < {MIN_PROBABILITY}%)")
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
            "home_form": home_form,
            "away_form": away_form,
            "home_ppg": home_ppg,
            "away_ppg": away_ppg,
            "home_win_pct": home_win_pct,
            "away_win_pct": away_win_pct,
            "home_odds": round(1 / (home_prob_bm / 100), 2),
            "away_odds": round(1 / (away_prob_bm / 100), 2)
        }
        matches.append(match)
        print(f"   ✅ Добавлен в прогнозы")
    
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено {len(matches)} матчей в data/matches.json")

def main():
    update_matches()
    print("=== ГОТОВО ===")

if __name__ == "__main__":
    main()
