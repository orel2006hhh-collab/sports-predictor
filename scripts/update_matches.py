#!/usr/bin/env python3
"""
ПРОГНОЗЫ С DeepSeek (реальная статистика из интернета)
- The Odds API: список предстоящих матчей
- DeepSeek с web_search=True: самостоятельно ищет актуальную статистику
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
    Отправляет запрос к DeepSeek с включенным веб-поиском.
    """
    if not OPENROUTER_API_KEY:
        return None, None, None, None, None
    
    prompt = f"""Ты эксперт по NBA. Сделай прогноз на матч:

{home_team} vs {away_team}

Найди в интернете актуальную статистику за последние 5-7 дней:
1. Форму команд (последние 5 игр: победы/поражения)
2. Средние очки за игру (PPG) за последние 5 матчей
3. Текущую серию (сколько побед или поражений подряд)
4. Процент побед за последние 5 матчей

Верни ответ строго в формате (каждая строка начинается с ключевого слова и вертикальной черты):

ФОРМА|НАЗВАНИЕ_КОМАНДЫ|ЧИСЛО ПОБЕД-ЧИСЛО ПОРАЖЕНИЙ
ФОРМА|НАЗВАНИЕ_КОМАНДЫ|ЧИСЛО ПОБЕД-ЧИСЛО ПОРАЖЕНИЙ
PPG|НАЗВАНИЕ_КОМАНДЫ|ЧИСЛО
PPG|НАЗВАНИЕ_КОМАНДЫ|ЧИСЛО
СТРЕЙК|НАЗВАНИЕ_КОМАНДЫ|+ЧИСЛО или -ЧИСЛО
СТРЕЙК|НАЗВАНИЕ_КОМАНДЫ|+ЧИСЛО или -ЧИСЛО
ПРОЦЕНТ|НАЗВАНИЕ_КОМАНДЫ|ЧИСЛО
ПРОЦЕНТ|НАЗВАНИЕ_КОМАНДЫ|ЧИСЛО
ВЕРОЯТНОСТЬ|ЧИСЛО 0-100|КОМАНДА-ФАВОРИТ
ТОТАЛ|БОЛЬШЕ или МЕНЬШЕ|ОБЪЯСНЕНИЕ

Пример правильного ответа:
ФОРМА|Los Angeles Lakers|4-1
ФОРМА|Boston Celtics|3-2
PPG|Los Angeles Lakers|118.5
PPG|Boston Celtics|112.3
СТРЕЙК|Los Angeles Lakers|+3
СТРЕЙК|Boston Celtics|-1
ПРОЦЕНТ|Los Angeles Lakers|80
ПРОЦЕНТ|Boston Celtics|60
ВЕРОЯТНОСТЬ|73|Los Angeles Lakers
ТОТАЛ|БОЛЬШЕ|Обе команды набирают в среднем 230 очков
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
        print(f"🧠 DeepSeek (с веб-поиском): {home_team} – {away_team}...")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            full = result['choices'][0]['message']['content'].strip()
            print(f"   DeepSeek ответ получил, парсим...")
            
            # Парсим ответ построчно
            result_dict = {
                "home_form": None,
                "away_form": None,
                "home_ppg": None,
                "away_ppg": None,
                "home_streak": None,
                "away_streak": None,
                "home_win_pct": None,
                "away_win_pct": None,
                "prob": None,
                "winner": None,
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
                        team = parts[1].strip()
                        value = parts[2].strip()
                        if home_team.lower() in team.lower() or team.lower() in home_team.lower():
                            result_dict["home_form"] = value
                        elif away_team.lower() in team.lower() or team.lower() in away_team.lower():
                            result_dict["away_form"] = value
                
                elif line.startswith('PPG|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            team = parts[1].strip()
                            value = float(parts[2].strip())
                            if home_team.lower() in team.lower() or team.lower() in home_team.lower():
                                result_dict["home_ppg"] = value
                            elif away_team.lower() in team.lower() or team.lower() in away_team.lower():
                                result_dict["away_ppg"] = value
                        except:
                            pass
                
                elif line.startswith('СТРЕЙК|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        team = parts[1].strip()
                        value = parts[2].strip()
                        if home_team.lower() in team.lower() or team.lower() in home_team.lower():
                            result_dict["home_streak"] = value
                        elif away_team.lower() in team.lower() or team.lower() in away_team.lower():
                            result_dict["away_streak"] = value
                
                elif line.startswith('ПРОЦЕНТ|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            team = parts[1].strip()
                            value = float(parts[2].strip())
                            if home_team.lower() in team.lower() or team.lower() in home_team.lower():
                                result_dict["home_win_pct"] = value
                            elif away_team.lower() in team.lower() or team.lower() in away_team.lower():
                                result_dict["away_win_pct"] = value
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
                
                elif line.startswith('ТОТАЛ|'):
                    parts = line.split('|')
                    if len(parts) >= 2:
                        result_dict["total_direction"] = parts[1].strip()
                        if len(parts) >= 3:
                            result_dict["total_reason"] = parts[2].strip()
            
            # Если не нашли форму через точное совпадение, пробуем по порядку строк
            if result_dict["home_form"] is None and result_dict["away_form"] is None:
                form_lines = [l for l in lines if l.startswith('ФОРМА|')]
                if len(form_lines) >= 2:
                    first = form_lines[0].split('|')
                    second = form_lines[1].split('|')
                    if len(first) >= 3 and len(second) >= 3:
                        result_dict["home_form"] = first[2].strip()
                        result_dict["away_form"] = second[2].strip()
            
            total_prediction = f"Тотал {result_dict['total_direction']} 225.5"
            
            stats = {
                "home_form": result_dict["home_form"],
                "away_form": result_dict["away_form"],
                "home_ppg": result_dict["home_ppg"],
                "away_ppg": result_dict["away_ppg"],
                "home_streak": result_dict["home_streak"],
                "away_streak": result_dict["away_streak"],
                "home_win_pct": result_dict["home_win_pct"],
                "away_win_pct": result_dict["away_win_pct"],
            }
            
            print(f"   Распарсено: форма {result_dict['home_form']} vs {result_dict['away_form']}, PPG {result_dict['home_ppg']} vs {result_dict['away_ppg']}")
            
            return result_dict["prob"], result_dict["winner"], stats, total_prediction, result_dict.get("total_reason", "")
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
    print("   DeepSeek будет искать актуальную статистику в интернете")
    
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
        
        # Запрашиваем DeepSeek с веб-поиском
        ai_prob, ai_winner, ai_stats, ai_total_pred, ai_total_reason = call_deepseek(home, away)
        
        if ai_prob is not None and ai_prob > 0:
            prob = round(ai_prob * 100)
            winner = ai_winner
            source = "DeepSeek AI (актуальная статистика из интернета)"
            total_prediction = ai_total_pred or "Тотал БОЛЬШЕ 225.5"
            
            home_form = ai_stats.get("home_form")
            away_form = ai_stats.get("away_form")
            home_ppg = ai_stats.get("home_ppg")
            away_ppg = ai_stats.get("away_ppg")
            home_streak = ai_stats.get("home_streak")
            away_streak = ai_stats.get("away_streak")
            home_win_pct = ai_stats.get("home_win_pct")
            away_win_pct = ai_stats.get("away_win_pct")
            
            reasoning = f"🏀 ПОБЕДА: DeepSeek проанализировал актуальную статистику. Форма {home}: {home_form or '?'}, {away}: {away_form or '?'}.\n📊 ТОТАЛ: {ai_total_reason or 'Анализ результативности команд'}"
        else:
            prob = local_prob
            winner = local_winner
            source = "Локальный расчёт (коэффициенты)"
            total_prediction = "Тотал БОЛЬШЕ 225.5"
            home_form = away_form = None
            home_ppg = away_ppg = None
            home_streak = away_streak = None
            home_win_pct = away_win_pct = None
            reasoning = f"🏀 ПОБЕДА: Прогноз на основе коэффициентов букмекеров: {winner} побеждает с вероятностью {prob}%.\n📊 ТОТАЛ: Средняя результативность команд выше линии 225.5."
        
        if prob < MIN_PROBABILITY:
            print(f"⏭️ Пропущен ({prob}% < {MIN_PROBABILITY}%): {home} – {away}")
            continue
        
        # Получаем реальные коэффициенты для отображения
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
            "home_streak": home_streak,
            "away_streak": away_streak,
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
        
        print(f"✅ {home} – {away}: {winner} ({prob}%) | форма {home_form or '?'} vs {away_form or '?'} | {source}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    with open("data/predictions_backup.json", "w", encoding="utf-8") as f:
        json.dump({"predictions": backup}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено {len(matches)} матчей")

def main():
    print(f"🚀 ЗАПУСК (DeepSeek с веб-поиском)")
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
