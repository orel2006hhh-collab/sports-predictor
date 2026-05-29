#!/usr/bin/env python3
"""
ПРОГНОЗЫ С DeepSeek (статистика дома/гостей)
"""

import json
import os
import re
import requests
from datetime import datetime, timedelta

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

SPORT = "basketball_nba"
REGIONS = "us,uk,eu"
MARKETS = "h2h,totals"

MIN_PROBABILITY = 55

def get_bookmakers_list(bookmakers):
    if not bookmakers:
        return "Данные не загружены"
    names = []
    for bk in bookmakers[:8]:
        title = bk.get("title", "")
        if title and title not in names:
            names.append(title)
    return ", ".join(names) if names else "Букмекеры не определены"

def get_total_line(bookmakers):
    total_points = []
    for bk in bookmakers:
        for market in bk.get("markets", []):
            if market["key"] == "totals":
                for outcome in market["outcomes"]:
                    point = outcome.get("point")
                    if point and point not in total_points:
                        total_points.append(float(point))
                break
    if total_points:
        return round(sum(total_points) / len(total_points), 1)
    return 225.5

def call_deepseek(home_team: str, away_team: str, total_line: float):
    if not OPENROUTER_API_KEY:
        return None, None, None, None, None
    
    prompt = f"""Ты эксперт по NBA. Сделай прогноз на матч:

{home_team} (дома) vs {away_team} (в гостях)

Линия тотала: {total_line}

Найди в интернете актуальную статистику за последние 5-7 дней:

**ВАЖНО: Учитывай раздельно статистику дома и в гостях!**

Для {home_team} (хозяева):
1. Форма дома (последние 5 домашних игр: победы/поражения)
2. Средние очки за игру ДОМА (PPG home) за последние 5 домашних матчей
3. Процент побед ДОМА за последние 5 игр

Для {away_team} (гости):
1. Форма в гостях (последние 5 выездных игр: победы/поражения)
2. Средние очки за игру В ГОСТЯХ (PPG away) за последние 5 выездных матчей
3. Процент побед В ГОСТЯХ за последние 5 игр

Верни ответ строго в формате:

ФОРМА_ДОМА|{home_team}|ЧИСЛО ПОБЕД-ЧИСЛО ПОРАЖЕНИЙ
ФОРМА_ГОСТИ|{away_team}|ЧИСЛО ПОБЕД-ЧИСЛО ПОРАЖЕНИЙ
PPG_ДОМА|{home_team}|ЧИСЛО
PPG_ГОСТИ|{away_team}|ЧИСЛО
ПРОЦЕНТ_ДОМА|{home_team}|ЧИСЛО
ПРОЦЕНТ_ГОСТИ|{away_team}|ЧИСЛО
ВЕРОЯТНОСТЬ|ЧИСЛО 0-100|{home_team} или {away_team}
ОБЪЯСНЕНИЕ|Твой развёрнутый анализ (3-5 предложений), обязательно учитывающий разницу между игрой дома и в гостях
ТОТАЛ|БОЛЬШЕ или МЕНЬШЕ|Краткое объяснение, учитывающее PPG дома и в гостях

Пример:
ФОРМА_ДОМА|Los Angeles Lakers|4-1
ФОРМА_ГОСТИ|Boston Celtics|2-3
PPG_ДОМА|Los Angeles Lakers|120.5
PPG_ГОСТИ|Boston Celtics|108.2
ПРОЦЕНТ_ДОМА|Los Angeles Lakers|80
ПРОЦЕНТ_ГОСТИ|Boston Celtics|40
ВЕРОЯТНОСТЬ|73|Los Angeles Lakers
ОБЪЯСНЕНИЕ|Лейкерс дома играют сильно (120.5 PPG), в то время как Селтикс на выезде набирают только 108.2 PPG.
ТОТАЛ|БОЛЬШЕ|Лейкерс дома набирают много очков, а защита гостей слабее.
"""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 600,
        "web_search": True
    }
    
    try:
        print(f"🧠 DeepSeek (с учётом дома/гостей): {home_team} – {away_team}...")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            full = result['choices'][0]['message']['content'].strip()
            
            result_dict = {
                "home_form": None,
                "away_form": None,
                "home_ppg": None,
                "away_ppg": None,
                "home_win_pct": None,
                "away_win_pct": None,
                "prob": None,
                "winner": None,
                "explanation": "",
                "total_direction": "БОЛЬШЕ"
            }
            
            lines = full.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('ФОРМА_ДОМА|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        result_dict["home_form"] = parts[2]
                
                elif line.startswith('ФОРМА_ГОСТИ|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        result_dict["away_form"] = parts[2]
                
                elif line.startswith('PPG_ДОМА|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            result_dict["home_ppg"] = float(parts[2])
                        except:
                            pass
                
                elif line.startswith('PPG_ГОСТИ|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            result_dict["away_ppg"] = float(parts[2])
                        except:
                            pass
                
                elif line.startswith('ПРОЦЕНТ_ДОМА|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            result_dict["home_win_pct"] = float(parts[2])
                        except:
                            pass
                
                elif line.startswith('ПРОЦЕНТ_ГОСТИ|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            result_dict["away_win_pct"] = float(parts[2])
                        except:
                            pass
                
                elif line.startswith('ВЕРОЯТНОСТЬ|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            result_dict["prob"] = float(parts[1]) / 100
                            result_dict["winner"] = parts[2].strip()
                        except:
                            pass
                
                elif line.startswith('ОБЪЯСНЕНИЕ|'):
                    parts = line.split('|', 1)
                    if len(parts) >= 2:
                        result_dict["explanation"] = parts[1].strip()
                
                elif line.startswith('ТОТАЛ|'):
                    parts = line.split('|')
                    if len(parts) >= 2:
                        result_dict["total_direction"] = parts[1].strip()
            
            if result_dict["home_form"] is None:
                form_lines = [l for l in lines if l.startswith('ФОРМА_ДОМА|') or l.startswith('ФОРМА_ГОСТИ|')]
                if len(form_lines) >= 2:
                    first = form_lines[0].split('|')
                    second = form_lines[1].split('|')
                    if len(first) >= 3 and len(second) >= 3:
                        if 'ДОМА' in first[0]:
                            result_dict["home_form"] = first[2].strip()
                            result_dict["away_form"] = second[2].strip()
                        else:
                            result_dict["away_form"] = first[2].strip()
                            result_dict["home_form"] = second[2].strip()
            
            total_prediction = f"Тотал {result_dict['total_direction']} {total_line}"
            stats = {
                "home_form": result_dict["home_form"],
                "away_form": result_dict["away_form"],
                "home_ppg": result_dict["home_ppg"],
                "away_ppg": result_dict["away_ppg"],
                "home_win_pct": result_dict["home_win_pct"],
                "away_win_pct": result_dict["away_win_pct"],
            }
            
            return result_dict["prob"], result_dict["winner"], stats, total_prediction, result_dict["explanation"]
    except Exception as e:
        print(f"⚠️ DeepSeek ошибка: {e}")
    
    return None, None, None, None, None

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
    print("   DeepSeek учитывает статистику дома/гостей")
    
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
        total_line = get_total_line(game.get("bookmakers", []))
        
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
        
        ai_prob, ai_winner, ai_stats, ai_total_pred, ai_explanation = call_deepseek(home, away, total_line)
        
        if ai_prob is not None and ai_prob > 0:
            prob = round(ai_prob * 100)
            winner = ai_winner
            source = "DeepSeek AI"
            total_prediction = ai_total_pred or f"Тотал БОЛЬШЕ {total_line}"
            home_form = ai_stats.get("home_form")
            away_form = ai_stats.get("away_form")
            home_ppg = ai_stats.get("home_ppg")
            away_ppg = ai_stats.get("away_ppg")
            home_win_pct = ai_stats.get("home_win_pct")
            away_win_pct = ai_stats.get("away_win_pct")
            reasoning = ai_explanation
        else:
            prob = local_prob
            winner = local_winner
            source = "Локальный расчёт"
            total_prediction = f"Тотал БОЛЬШЕ {total_line}"
            home_form = away_form = None
            home_ppg = away_ppg = None
            home_win_pct = away_win_pct = None
            reasoning = f"Прогноз на основе коэффициентов: {winner} ({prob}%)"
        
        if prob < MIN_PROBABILITY:
            print(f"⏭️ Пропущен ({prob}%): {home} – {away}")
            continue
        
        home_odds_decimal = round(1 / (home_prob / 100), 2) if home_prob > 0 else 0
        away_odds_decimal = round(1 / (away_prob / 100), 2) if away_prob > 0 else 0
        
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
            "data_source": source,
            "home_form": home_form,
            "away_form": away_form,
            "home_ppg": home_ppg,
            "away_ppg": away_ppg,
            "home_win_pct": home_win_pct,
            "away_win_pct": away_win_pct,
            "home_odds": home_odds_decimal,
            "away_odds": away_odds_decimal
        }
        matches.append(match)
        backup.append({
            "date": date_str,
            "home": home,
            "away": away,
            "prediction": winner,
            "prob": prob
        })
        
        print(f"✅ {home} – {away}: {winner} ({prob}%) | форма дома {home_form or '?'} vs форма гостей {away_form or '?'}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    with open("data/predictions_backup.json", "w", encoding="utf-8") as f:
        json.dump({"predictions": backup}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено {len(matches)} матчей")

def main():
    print(f"🚀 ЗАПУСК (DeepSeek + статистика дома/гостей)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not ODDS_API_KEY:
        print("❌ ODDS_API_KEY не найден")
        return
    
    if not OPENROUTER_API_KEY:
        print("⚠️ OPENROUTER_API_KEY не найден")
    
    update_matches()
    print("\n✨ Готово")

if __name__ == "__main__":
    main()
