#!/usr/bin/env python3
"""
ПРОГНОЗЫ С ИИ (DeepSeek V4) - ДВУХЭТАПНЫЙ ПОДХОД
1. DeepSeek вспоминает последние 5 игр команд
2. Анализирует статистику и даёт прогноз
3. ВСЯ статистика показывается пользователю
"""

import json
import os
import re
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional

# ============================================================
# НАСТРОЙКИ
# ============================================================

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

SPORT_NBA = "basketball_nba"
SPORT_NHL = "icehockey_nhl"
REGIONS = "us,uk,eu"
MARKETS = "h2h,spreads,totals"
MIN_PROBABILITY = 55

TOTAL_LINE_NBA = 225.5
TOTAL_LINE_NHL = 6.5

# ============================================================
# ДВУХЭТАПНЫЙ ВЫЗОВ DEEPSEEK
# ============================================================

def call_deepseek_two_step(league: str, home: str, away: str) -> Tuple[Optional[float], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Двухэтапный вызов DeepSeek:
    1. Запрос статистики последних 5 матчей команд
    2. Анализ этой статистики для прогноза
    Возвращает: (вероятность_победы_home, объяснение_победы, прогноз_тотала, объяснение_тотала, статистика_текст)
    """
    if not OPENROUTER_API_KEY:
        return None, None, None, None, None
    
    total_line = TOTAL_LINE_NHL if league == "nhl" else TOTAL_LINE_NBA
    league_name = "NHL" if league == "nhl" else "NBA"
    emoji = "🏒" if league == "nhl" else "🏀"
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    
    # ===== ШАГ 1: ЗАПРАШИВАЕМ СТАТИСТИКУ ПОСЛЕДНИХ 5 МАТЧЕЙ =====
    stats_prompt = f"""Ты эксперт {league_name}. Вспомни и напиши статистику последних 5 матчей команд:

{home} — последние 5 игр (укажи дату, соперника, счёт, кто победил)
{away} — последние 5 игр (укажи дату, соперника, счёт, кто победил)

Ответь в понятном формате, например:

{home}:
1. 27 мая vs Оклахома: 114-127 (ПОРАЖЕНИЕ)
2. 24 мая vs Оклахома: 118-121 (ПОРАЖЕНИЕ)
3. 22 мая @ Оклахома: 109-115 (ПОБЕДА)
...

{away}:
1. 27 мая @ Сан-Антонио: 127-114 (ПОБЕДА)
2. 24 мая @ Сан-Антонио: 121-118 (ПОБЕДА)
..."""

    try:
        print(f"  📊 Шаг 1/2: DeepSeek вспоминает статистику {home} и {away}...")
        stats_response = requests.post(url, headers=headers, json={
            "model": "deepseek/deepseek-chat",
            "messages": [{"role": "user", "content": stats_prompt}],
            "temperature": 0.3,
            "max_tokens": 800
        }, timeout=30)
        
        if stats_response.status_code != 200:
            print(f"    ⚠️ Ошибка запроса статистики: {stats_response.status_code}")
            return None, None, None, None, None
        
        stats_data = stats_response.json()['choices'][0]['message']['content'].strip()
        print(f"    📊 Статистика получена ({len(stats_data)} символов)")
        
        # ===== ШАГ 2: АНАЛИЗ СТАТИСТИКИ ДЛЯ ПРОГНОЗА =====
        analysis_prompt = f"""Ты эксперт {league_name}. Проанализируй следующую статистику и дай прогноз.

{stats_data}

ЛИНИЯ ТОТАЛА: {total_line}

На основе этих данных:
1. Посчитай точную форму каждой команды (сколько побед/поражений в последних 5 играх)
2. Определи текущую серию
3. Сделай прогноз на победителя (с вероятностью в %)
4. Сделай прогноз на тотал (БОЛЬШЕ или МЕНЬШЕ {total_line})

Ответь строго в формате:
ФОРМА|{home}|X побед, Y поражений, серия Z
ФОРМА|{away}|X побед, Y поражений, серия Z
ВЕРОЯТНОСТЬ|ЧИСЛО (0-100)
ТОТАЛ|БОЛЬШЕ или МЕНЬШЕ
ПОЧЕМУ: (короткое объяснение, 2-3 предложения)"""

        print(f"  🤖 Шаг 2/2: DeepSeek анализирует статистику и делает прогноз...")
        analysis_response = requests.post(url, headers=headers, json={
            "model": "deepseek/deepseek-chat",
            "messages": [{"role": "user", "content": analysis_prompt}],
            "temperature": 0.3,
            "max_tokens": 400
        }, timeout=30)
        
        if analysis_response.status_code != 200:
            print(f"    ⚠️ Ошибка анализа: {analysis_response.status_code}")
            return None, None, None, None, stats_data
        
        analysis = analysis_response.json()['choices'][0]['message']['content'].strip()
        
        # Парсим ответ
        prob = None
        total_direction = "БОЛЬШЕ"
        reasoning = ""
        home_form_line = ""
        away_form_line = ""
        
        lines = analysis.split('\n')
        for line in lines:
            if line.startswith('ФОРМА|'):
                parts = line.split('|')
                if len(parts) >= 3:
                    if parts[1].strip() == home:
                        home_form_line = parts[2].strip()
                    elif parts[1].strip() == away:
                        away_form_line = parts[2].strip()
            elif line.startswith('ВЕРОЯТНОСТЬ|'):
                parts = line.split('|')
                if len(parts) >= 2:
                    try:
                        prob = float(parts[1]) / 100
                    except:
                        pass
            elif line.startswith('ТОТАЛ|'):
                parts = line.split('|')
                if len(parts) >= 2:
                    total_direction = parts[1].strip()
            elif line.startswith('ПОЧЕМУ:'):
                reasoning = line.replace('ПОЧЕМУ:', '').strip()
        
        if prob is None:
            numbers = re.findall(r'\d+', analysis)
            if numbers:
                prob = float(numbers[0]) / 100
        
        total_pred = f"Тотал {total_direction} {total_line}"
        
        # Формируем полное объяснение со статистикой
        full_reasoning = f"""📊 СТАТИСТИКА ПОСЛЕДНИХ 5 ИГР:

{stats_data}

📈 ФОРМА КОМАНД:
• {home}: {home_form_line if home_form_line else 'анализ выше'}
• {away}: {away_form_line if away_form_line else 'анализ выше'}

🎯 ВЫВОД НЕЙРОСЕТИ:
{reasoning}"""
        
        return prob, full_reasoning, total_pred, "", stats_data
        
    except Exception as e:
        print(f"    ⚠️ DeepSeek ошибка: {e}")
        return None, None, None, None, None

# ============================================================
# ФОЛБЭК: ЛОКАЛЬНЫЙ РАСЧЁТ (если DeepSeek недоступен)
# ============================================================

def american_to_probability(american_odds: int) -> float:
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)

def fetch_upcoming_games(sport: str) -> List[Dict]:
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": "us,uk,eu", "markets": "h2h,spreads,totals", "oddsFormat": "american"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

def update_league(league: str, sport_key: str, data_file: str, backup_file: str, history_file: str):
    print(f"\n{'🏀' if league == 'nba' else '🏒'} ОБНОВЛЕНИЕ {league.upper()}")
    
    repo_root = os.path.dirname(os.path.dirname(__file__))
    
    # ОБНОВЛЕНИЕ ИСТОРИИ (загружаем завершённые матчи)
    history_path = os.path.join(repo_root, history_file)
    backup_path = os.path.join(repo_root, backup_file)
    
    # Получаем завершённые матчи для истории
    scores_url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores"
    params = {"apiKey": ODDS_API_KEY, "daysFrom": 14}
    try:
        resp = requests.get(scores_url, params=params, timeout=20)
        if resp.status_code == 200:
            completed_games = [g for g in resp.json() if g.get("completed", False)]
            
            history = {"predictions": []}
            if os.path.exists(history_path):
                with open(history_path, "r") as f:
                    history = json.load(f)
            
            existing = {(p["date"], p["home"], p["away"]) for p in history.get("predictions", [])}
            
            backup = {}
            if os.path.exists(backup_path):
                with open(backup_path, "r") as f:
                    data = json.load(f)
                    for p in data.get("predictions", []):
                        backup[(p["date"], p["home"], p["away"])] = p
            
            new_entries = []
            for game in completed_games:
                commence = game.get("commence_time")
                if not commence:
                    continue
                dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
                date_str = dt.strftime("%d.%m.%Y")
                home = game.get("home_team")
                away = game.get("away_team")
                key = (date_str, home, away)
                
                if key in existing or key not in backup:
                    continue
                
                scores = game.get("scores", {})
                home_score = scores.get(home, 0) if isinstance(scores, dict) else 0
                away_score = scores.get(away, 0) if isinstance(scores, dict) else 0
                if home_score == 0 and away_score == 0:
                    continue
                
                actual_winner = home if home_score > away_score else away
                predicted_winner = backup[key]["prediction"]
                prob = backup[key]["prob"]
                result = "success" if predicted_winner == actual_winner else "failed"
                
                actual_total = home_score + away_score
                predicted_total = backup[key].get("total_prediction", "БОЛЬШЕ")
                total_result = "success" if (predicted_total == "БОЛЬШЕ" and actual_total > TOTAL_LINE_NBA) or (predicted_total == "МЕНЬШЕ" and actual_total < TOTAL_LINE_NBA) else "failed"
                
                new_entries.append({
                    "date": date_str, "home": home, "away": away,
                    "prediction": predicted_winner, "result": result,
                    "total_prediction": predicted_total, "total_result": total_result,
                    "actual_score": f"{home_score}-{away_score}", "actual_total": actual_total,
                    "prob": prob
                })
                print(f"  📊 История: {home} – {away}: {predicted_winner} → {actual_winner}")
            
            if new_entries:
                history["predictions"] = new_entries + history.get("predictions", [])
                with open(history_path, "w", encoding="utf-8") as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
                print(f"  ✨ Добавлено {len(new_entries)} записей в историю")
    except Exception as e:
        print(f"  ⚠️ Ошибка загрузки истории: {e}")
    
    # ОБНОВЛЕНИЕ ПРЕДСТОЯЩИХ МАТЧЕЙ
    games = fetch_upcoming_games(sport_key)
    if not games:
        print(f"❌ Нет данных для {league}")
        return
    
    matches = []
    new_backup = []
    total_games = len(games)
    
    for idx, game in enumerate(games, 1):
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
        
        # Парсим коэффициенты для локального фолбэка
        home_odds, away_odds = 2.0, 2.0
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "h2h":
                    for out in market["outcomes"]:
                        if out["name"] == home:
                            home_odds = out["price"]
                        elif out["name"] == away:
                            away_odds = out["price"]
        
        home_prob = american_to_probability(home_odds) * 100
        away_prob = american_to_probability(away_odds) * 100
        total = home_prob + away_prob
        home_prob = (home_prob / total) * 100
        away_prob = (away_prob / total) * 100
        
        if home_prob > away_prob:
            coef_winner = home
            coef_prob = round(home_prob)
        else:
            coef_winner = away
            coef_prob = round(away_prob)
        
        if coef_prob < MIN_PROBABILITY:
            print(f"  ⏭️ [{idx}/{total_games}] Пропущен ({coef_prob}% < {MIN_PROBABILITY}%): {home} – {away}")
            continue
        
        # Прогноз тотала из коэффициентов
        total_prediction = f"Тотал БОЛЬШЕ {TOTAL_LINE_NBA if league == 'nba' else TOTAL_LINE_NHL}"
        total_direction = "БОЛЬШЕ"
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "totals":
                    for out in market["outcomes"]:
                        if out["name"] == "Over" and out.get("point"):
                            total_prediction = f"Тотал БОЛЬШЕ {out['point']}"
                            total_direction = "БОЛЬШЕ"
                        elif out["name"] == "Under" and out.get("point"):
                            total_prediction = f"Тотал МЕНЬШЕ {out['point']}"
                            total_direction = "МЕНЬШЕ"
        
        # ДВУХЭТАПНЫЙ ВЫЗОВ DEEPSEEK
        print(f"  🧠 [{idx}/{total_games}] DeepSeek анализирует: {home} – {away}")
        ai_prob, ai_reasoning, ai_total_pred, _, stats_text = call_deepseek_two_step(league, home, away)
        
        if ai_prob is not None:
            # Используем вероятность от DeepSeek (если он дал)
            prob = round(ai_prob * 100)
            winner = home if ai_prob > 0.5 else away
            reasoning = ai_reasoning
            source = "DeepSeek V4 (анализ последних 5 игр)"
        else:
            # Фолбэк на локальный расчёт
            winner = coef_winner
            prob = coef_prob
            reasoning = f"Локальный расчёт на основе коэффициентов: {winner} побеждает с вероятностью {prob}%"
            source = "Локальный (коэффициенты)"
            stats_text = "Статистика временно недоступна"
        
        # Список букмекеров
        bookmakers_list = ", ".join([bk.get("title", "") for bk in game.get("bookmakers", [])[:5]])
        
        # Извлекаем форму из статистики для отображения в карточке
        home_form_display = "анализ DeepSeek"
        away_form_display = "анализ DeepSeek"
        
        # Пытаемся найти цифры формы в тексте статистики
        if stats_text and stats_text != "Статистика временно недоступна":
            # Ищем строки с результатами
            lines = stats_text.split('\n')
            home_found = False
            away_found = False
            for line in lines:
                if home in line and not home_found and ('побед' in line.lower() or 'поражен' in line.lower() or 'W' in line or 'L' in line):
                    home_form_display = line.strip()
                    home_found = True
                elif away in line and not away_found and ('побед' in line.lower() or 'поражен' in line.lower() or 'W' in line or 'L' in line):
                    away_form_display = line.strip()
                    away_found = True
        
        match = {
            "date": date_str, "time": time_str,
            "home": home, "away": away,
            "winner": winner, "prob": prob,
            "total_prediction": ai_total_pred if ai_total_pred else total_prediction,
            "bookmakers_list": bookmakers_list,
            "ai_reasoning": reasoning,
            "home_ppg": "см. статистику ниже",
            "away_ppg": "см. статистику ниже",
            "home_win_pct": home_form_display,
            "away_win_pct": away_form_display,
            "home_form": home_form_display,
            "away_form": away_form_display,
            "home_streak": "см. статистику",
            "away_streak": "см. статистику",
            "h2h": f"Статистика последних 5 игр:\n{stats_text if stats_text else 'данные загружаются'}",
            "injuries": "данные о травмах не загружены",
            "data_source": source
        }
        matches.append(match)
        new_backup.append({
            "date": date_str, "home": home, "away": away,
            "prediction": winner, "total_prediction": total_direction, "prob": prob
        })
        print(f"  ✅ [{idx}/{total_games}] {home} – {away}: {winner} ({prob}%) | {total_prediction}")
        
        # Небольшая задержка между матчами
        time.sleep(2)
    
    with open(os.path.join(repo_root, data_file), "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": league}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(repo_root, backup_file), "w", encoding="utf-8") as f:
        json.dump({"predictions": new_backup}, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Сохранено {len(matches)} матчей {league.upper()}")

def main():
    print(f"🚀 ЗАПУСК (DeepSeek V4 — двухэтапный анализ с отображением статистики)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Минимальная вероятность: {MIN_PROBABILITY}%")
    
    if not ODDS_API_KEY:
        print("❌ ODDS_API_KEY не найден в Secrets")
        return
    
    if not OPENROUTER_API_KEY:
        print("⚠️ OPENROUTER_API_KEY не найден. Будут использованы локальные прогнозы.")
    
    update_league("nba", SPORT_NBA, "data/nba_matches.json", "data/nba_backup.json", "data/nba_history.json")
    update_league("nhl", SPORT_NHL, "data/nhl_matches.json", "data/nhl_backup.json", "data/nhl_history.json")
    
    print("\n✨ Готово")

if __name__ == "__main__":
    main()
