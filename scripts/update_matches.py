#!/usr/bin/env python3
"""
ПРОГНОЗЫ С DeepSeek (реальная статистика + травмы из интернета)
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
MARKETS = "h2h,totals"

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
        return None, None, None, None, None, None, None
    
    prompt = f"""Ты эксперт по NBA. Сделай подробный прогноз на матч:

{home_team} vs {away_team}

Линия тотала: {total_line}

**ВАЖНО: Найди в интернете актуальную информацию о травмах игроков обеих команд на сегодня.**
1. Кто из ключевых игроков травмирован?
2. Какой у них статус? (Out — точно не играет, Questionable — под вопросом, Probable — скорее всего сыграет)
3. Как отсутствие этих игроков может повлиять на игру команды?

Также найди актуальную статистику за последние 5-7 дней:
1. Форму команд (последние 5 игр: победы/поражения)
2. Средние очки за игру (PPG) за последние 5 матчей
3. Процент побед за последние 5 матчей

Верни ответ строго в формате:

ФОРМА|{home_team}|ЧИСЛО ПОБЕД-ЧИСЛО ПОРАЖЕНИЙ
ФОРМА|{away_team}|ЧИСЛО ПОБЕД-ЧИСЛО ПОРАЖЕНИЙ
PPG|{home_team}|ЧИСЛО
PPG|{away_team}|ЧИСЛО
ПРОЦЕНТ|{home_team}|ЧИСЛО
ПРОЦЕНТ|{away_team}|ЧИСЛО
ТРАВМЫ|{home_team}|Игрок (статус) - перечисли основных травмированных (если нет травм, напиши "Все здоровы")
ТРАВМЫ|{away_team}|Игрок (статус) - перечисли основных травмированных (если нет травм, напиши "Все здоровы")
ВЕРОЯТНОСТЬ|ЧИСЛО 0-100|{home_team} или {away_team}
ОБЪЯСНЕНИЕ|Твой развёрнутый анализ (3-5 предложений), обязательно учитывающий травмы
ТОТАЛ|БОЛЬШЕ или МЕНЬШЕ|Краткое объяснение

Пример правильного ответа:
ФОРМА|Los Angeles Lakers|4-1
ФОРМА|Boston Celtics|3-2
PPG|Los Angeles Lakers|118.5
PPG|Boston Celtics|112.3
ПРОЦЕНТ|Los Angeles Lakers|80
ПРОЦЕНТ|Boston Celtics|60
ТРАВМЫ|Los Angeles Lakers|Anthony Davis (Probable), LeBron James (Out)
ТРАВМЫ|Boston Celtics|Kristaps Porzingis (Questionable)
ВЕРОЯТНОСТЬ|73|Los Angeles Lakers
ОБЪЯСНЕНИЕ|Лейкерс имеют преимущество домашней площадки и лучшую форму. Однако отсутствие Леброна может сказаться.
ТОТАЛ|БОЛЬШЕ|Обе команды набирают много очков.
"""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 800,
        "web_search": True
    }
    
    try:
        print(f"🧠 DeepSeek (поиск статистики + травм): {home_team} – {away_team}...")
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
                "home_injuries": None,
                "away_injuries": None,
                "prob": None,
                "winner": None,
                "explanation": "",
                "total_direction": "БОЛЬШЕ",
                "total_reason": ""
            }
            
            lines = full.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('ФОРМА|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        if home_team in parts[1]:
                            result_dict["home_form"] = parts[2]
                        elif away_team in parts[1]:
                            result_dict["away_form"] = parts[2]
                
                elif line.startswith('PPG|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            if home_team in parts[1]:
                                result_dict["home_ppg"] = float(parts[2])
                            elif away_team in parts[1]:
                                result_dict["away_ppg"] = float(parts[2])
                        except:
                            pass
                
                elif line.startswith('ПРОЦЕНТ|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            if home_team in parts[1]:
                                result_dict["home_win_pct"] = float(parts[2])
                            elif away_team in parts[1]:
                                result_dict["away_win_pct"] = float(parts[2])
                        except:
                            pass
                
                elif line.startswith('ТРАВМЫ|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        if home_team in parts[1]:
                            result_dict["home_injuries"] = parts[2]
                        elif away_team in parts[1]:
                            result_dict["away_injuries"] = parts[2]
                
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
                        if len(parts) >= 3:
                            result_dict["total_reason"] = parts[2].strip()
            
            # Fallback для формы
            if result_dict["home_form"] is None:
                for line in lines:
                    if line.startswith('ФОРМА|'):
                        parts = line.split('|')
                        if len(parts) >= 3 and result_dict["home_form"] is None:
                            result_dict["home_form"] = parts[2]
                        elif len(parts) >= 3:
                            result_dict["away_form"] = parts[2]
                            break
            
            # Fallback для травм
            if result_dict["home_injuries"] is None:
                result_dict["home_injuries"] = "Нет данных о травмах"
            if result_dict["away_injuries"] is None:
                result_dict["away_injuries"] = "Нет данных о травмах"
            
            total_prediction = f"Тотал {result_dict['total_direction']} {total_line}"
            full_explanation = result_dict["explanation"]
            if result_dict["total_reason"]:
                full_explanation += f" По тоталу: {result_dict['total_reason']}"
            
            stats = {
                "home_form": result_dict["home_form"],
                "away_form": result_dict["away_form"],
                "home_ppg": result_dict["home_ppg"],
                "away_ppg": result_dict["away_ppg"],
                "home_win_pct": result_dict["home_win_pct"],
                "away_win_pct": result_dict["away_win_pct"],
                "home_injuries": result_dict["home_injuries"],
                "away_injuries": result_dict["away_injuries"],
            }
            
            print(f"   Распарсено: форма {result_dict['home_form']} vs {result_dict['away_form']}, "
                  f"травмы: {result_dict['home_injuries'][:40]}...")
            
            return result_dict["prob"], result_dict["winner"], stats, total_prediction, full_explanation
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
    print("   DeepSeek ищет статистику + травмы в интернете")
    
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
        
        # Коэффициенты
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
        
        # DeepSeek (ищет статистику и травмы)
        ai_prob, ai_winner, ai_stats, ai_total_pred, ai_explanation = call_deepseek(
            home, away, total_line
        )
        
        if ai_prob is not None and ai_prob > 0:
            prob = round(ai_prob * 100)
            winner = ai_winner
            source = "DeepSeek AI (статистика + травмы)"
            total_prediction = ai_total_pred or f"Тотал БОЛЬШЕ {total_line}"
            home_form = ai_stats.get("home_form")
            away_form = ai_stats.get("away_form")
            home_ppg = ai_stats.get("home_ppg")
            away_ppg = ai_stats.get("away_ppg")
            home_win_pct = ai_stats.get("home_win_pct")
            away_win_pct = ai_stats.get("away_win_pct")
            home_injuries = ai_stats.get("home_injuries")
            away_injuries = ai_stats.get("away_injuries")
            reasoning = ai_explanation
        else:
            prob = local_prob
            winner = local_winner
            source = "Локальный расчёт (коэффициенты)"
            total_prediction = f"Тотал БОЛЬШЕ {total_line}"
            home_form = away_form = None
            home_ppg = away_ppg = None
            home_win_pct = away_win_pct = None
            home_injuries = "Нет данных о травмах"
            away_injuries = "Нет данных о травмах"
            reasoning = f"Прогноз на основе коэффициентов букмекеров."
        
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
            "total_line": total_line,
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
            "away_odds": away_odds_decimal,
            "home_injuries": home_injuries,
            "away_injuries": away_injuries
        }
        matches.append(match)
        backup.append({
            "date": date_str,
            "home": home,
            "away": away,
            "prediction": winner,
            "prob": prob,
            "total_line": total_line
        })
        
        print(f"✅ {home} – {away}: {winner} ({prob}%) | форма {home_form or '?'} vs {away_form or '?'} | травмы: {home_injuries[:30] if home_injuries else '?'} | тотал {total_line}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    with open("data/predictions_backup.json", "w", encoding="utf-8") as f:
        json.dump({"predictions": backup}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено {len(matches)} матчей")

def main():
    print(f"🚀 ЗАПУСК (DeepSeek + статистика + травмы)")
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
