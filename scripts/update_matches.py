#!/usr/bin/env python3
"""
ПРОГНОЗЫ С ИИ (DeepSeek V4) - КОМПАКТНЫЙ ПОДХОД
- Нейросеть возвращает только структурированные данные: форма, тренд, вероятность
- Пользователь видит только суть, без простыни из 5 матчей каждой команды
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
# КОМПАКТНЫЙ ВЫЗОВ DEEPSEEK (ВОЗВРАЩАЕТ ТОЛЬКО СУТЬ)
# ============================================================

def call_deepseek_compact(league: str, home: str, away: str) -> Dict[str, Any]:
    """
    Компактный вызов DeepSeek — только суть для пользователя.
    Возвращает словарь с полями:
    - prob_home: float (вероятность победы хозяев, 0-1)
    - total_direction: "БОЛЬШЕ" или "МЕНЬШЕ"
    - home_wins: int (победы в последних 5)
    - home_losses: int (поражения в последних 5)
    - home_streak: int (положительное = серия побед, отрицательное = серия поражений)
    - away_wins: int
    - away_losses: int
    - away_streak: int
    - trend: str (одна фраза о ключевом тренде)
    - reasoning: str (одна фраза с выводом)
    - error: str (если ошибка)
    """
    
    if not OPENROUTER_API_KEY:
        return {"error": "OPENROUTER_API_KEY не найден"}
    
    total_line = TOTAL_LINE_NHL if league == "nhl" else TOTAL_LINE_NBA
    league_name = "NHL" if league == "nhl" else "NBA"
    emoji = "🏒" if league == "nhl" else "🏀"
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # КОМПАКТНЫЙ ПРОМПТ — никаких дат, счетов, подробных матчей
    compact_prompt = f"""Ты эксперт {league_name}. Проанализируй форму команд и дай КРАТКИЙ прогноз на матч:

{home} vs {away}

Линия тотала: {total_line}

ОТВЕТЬ ТОЛЬКО В ЭТОМ ФОРМАТЕ, БЕЗ ЛИШНИХ СЛОВ, БЕЗ ДАТ, БЕЗ СЧЕТОВ:

HOME_WINS|ЧИСЛО (победы {home} в последних 5 играх, 0-5)
HOME_LOSSES|ЧИСЛО (поражения {home} в последних 5 играх, 0-5)
HOME_STREAK|ЧИСЛО (текущая серия: положительное = победы, отрицательное = поражения)
AWAY_WINS|ЧИСЛО (победы {away} в последних 5 играх)
AWAY_LOSSES|ЧИСЛО (поражения {away} в последних 5 играх)
AWAY_STREAK|ЧИСЛО (текущая серия)
TREND|ОДНА КОРОТКАЯ ФРАЗА (ключевой тренд, например: "Команда А проиграла 3 последних выезда")
REASONING|ОДНА КОРОТКАЯ ФРАЗА (почему победит тот или иной соперник)
PROB_HOME|ЧИСЛО 0-100 (вероятность победы {home} в процентах)
TOTAL|БОЛЬШЕ или МЕНЬШЕ {total_line}

ВАЖНО: НЕ ПИШИ даты, счета, соперников, названия команд в статистике. ТОЛЬКО ЭТИ 10 строк."""

    try:
        response = requests.post(url, headers=headers, json={
            "model": "deepseek/deepseek-chat",
            "messages": [{"role": "user", "content": compact_prompt}],
            "temperature": 0.3,
            "max_tokens": 400
        }, timeout=35)
        
        if response.status_code != 200:
            return {"error": f"DeepSeek ошибка: {response.status_code}"}
        
        content = response.json()['choices'][0]['message']['content'].strip()
        
        # Парсим ответ
        result = {
            "home_wins": 0,
            "home_losses": 0,
            "home_streak": 0,
            "away_wins": 0,
            "away_losses": 0,
            "away_streak": 0,
            "trend": "",
            "reasoning": "",
            "prob_home": 0.5,
            "total_direction": "БОЛЬШЕ",
            "error": None
        }
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("HOME_WINS|"):
                try:
                    result["home_wins"] = int(line.split("|")[1])
                except:
                    pass
            elif line.startswith("HOME_LOSSES|"):
                try:
                    result["home_losses"] = int(line.split("|")[1])
                except:
                    pass
            elif line.startswith("HOME_STREAK|"):
                try:
                    result["home_streak"] = int(line.split("|")[1])
                except:
                    pass
            elif line.startswith("AWAY_WINS|"):
                try:
                    result["away_wins"] = int(line.split("|")[1])
                except:
                    pass
            elif line.startswith("AWAY_LOSSES|"):
                try:
                    result["away_losses"] = int(line.split("|")[1])
                except:
                    pass
            elif line.startswith("AWAY_STREAK|"):
                try:
                    result["away_streak"] = int(line.split("|")[1])
                except:
                    pass
            elif line.startswith("TREND|"):
                result["trend"] = line.split("|", 1)[1].strip()
            elif line.startswith("REASONING|"):
                result["reasoning"] = line.split("|", 1)[1].strip()
            elif line.startswith("PROB_HOME|"):
                try:
                    prob = float(line.split("|")[1])
                    result["prob_home"] = prob / 100
                except:
                    pass
            elif line.startswith("TOTAL|"):
                total_val = line.split("|")[1].strip().upper()
                if "МЕНЬШЕ" in total_val or "МЕНЕЕ" in total_val or "UNDER" in total_val:
                    result["total_direction"] = "МЕНЬШЕ"
                else:
                    result["total_direction"] = "БОЛЬШЕ"
        
        # Валидация: сумма побед и поражений должна быть 5 или около того
        home_total = result["home_wins"] + result["home_losses"]
        away_total = result["away_wins"] + result["away_losses"]
        
        if home_total != 5 and home_total > 0:
            # Корректируем, если DeepSeek ошибся
            if result["home_wins"] > 5:
                result["home_wins"] = 5
                result["home_losses"] = 0
            elif result["home_losses"] > 5:
                result["home_wins"] = 0
                result["home_losses"] = 5
        
        if away_total != 5 and away_total > 0:
            if result["away_wins"] > 5:
                result["away_wins"] = 5
                result["away_losses"] = 0
            elif result["away_losses"] > 5:
                result["away_wins"] = 0
                result["away_losses"] = 5
        
        return result
        
    except Exception as e:
        return {"error": str(e)}


def get_fallback_prediction(home: str, away: str, home_odds: float, away_odds: float) -> Dict[str, Any]:
    """Локальный расчёт на основе коэффициентов (если DeepSeek недоступен)"""
    home_prob = american_to_probability(home_odds) * 100
    away_prob = american_to_probability(away_odds) * 100
    total = home_prob + away_prob
    home_prob = (home_prob / total) * 100
    away_prob = (away_prob / total) * 100
    
    prob_home = home_prob / 100
    
    return {
        "prob_home": prob_home,
        "total_direction": "БОЛЬШЕ",
        "home_wins": 0,
        "home_losses": 0,
        "home_streak": 0,
        "away_wins": 0,
        "away_losses": 0,
        "away_streak": 0,
        "trend": "Данные о форме временно недоступны",
        "reasoning": f"Прогноз на основе коэффициентов: {home if prob_home > 0.5 else away} фаворит",
        "error": None,
        "is_fallback": True
    }


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def american_to_probability(american_odds: int) -> float:
    """Конвертация американских коэффициентов в вероятность"""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)


def fetch_upcoming_games(sport: str) -> List[Dict]:
    """Получение предстоящих матчей из Odds API"""
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us,uk,eu",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american"
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        return resp.json() if resp.status_code == 200 else []
    except:
        return []


def fetch_completed_games(sport_key: str, days_back: int = 14) -> List[Dict]:
    """Получение завершённых матчей для истории"""
    scores_url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores"
    params = {"apiKey": ODDS_API_KEY, "daysFrom": days_back}
    try:
        resp = requests.get(scores_url, params=params, timeout=20)
        if resp.status_code == 200:
            return [g for g in resp.json() if g.get("completed", False)]
    except:
        pass
    return []


def update_history(league: str, sport_key: str, backup_file: str, history_file: str):
    """Обновление истории завершённых матчей"""
    repo_root = os.path.dirname(os.path.dirname(__file__))
    history_path = os.path.join(repo_root, history_file)
    backup_path = os.path.join(repo_root, backup_file)
    
    completed_games = fetch_completed_games(sport_key, 14)
    if not completed_games:
        return
    
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
    total_line = TOTAL_LINE_NBA if league == "nba" else TOTAL_LINE_NHL
    
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
        total_result = "success" if (predicted_total == "БОЛЬШЕ" and actual_total > total_line) or (predicted_total == "МЕНЬШЕ" and actual_total < total_line) else "failed"
        
        new_entries.append({
            "date": date_str,
            "home": home,
            "away": away,
            "prediction": predicted_winner,
            "result": result,
            "total_prediction": predicted_total,
            "total_result": total_result,
            "actual_score": f"{home_score}-{away_score}",
            "actual_total": actual_total,
            "prob": prob
        })
        print(f"  📊 История: {home} – {away}: {predicted_winner} → {actual_winner}")
    
    if new_entries:
        history["predictions"] = new_entries + history.get("predictions", [])
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"  ✨ Добавлено {len(new_entries)} записей в историю")


def update_league(league: str, sport_key: str, data_file: str, backup_file: str, history_file: str):
    """Обновление одного лига (NBA или NHL)"""
    print(f"\n{'🏀' if league == 'nba' else '🏒'} ОБНОВЛЕНИЕ {league.upper()}")
    
    repo_root = os.path.dirname(os.path.dirname(__file__))
    
    # Обновляем историю
    update_history(league, sport_key, backup_file, history_file)
    
    # Получаем предстоящие матчи
    games = fetch_upcoming_games(sport_key)
    if not games:
        print(f"❌ Нет данных для {league}")
        return
    
    matches = []
    new_backup = []
    total_games = len(games)
    total_line = TOTAL_LINE_NBA if league == "nba" else TOTAL_LINE_NHL
    
    for idx, game in enumerate(games, 1):
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue
        
        # Дата и время
        commence = game.get("commence_time")
        if commence:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
            date_str = dt.strftime("%d.%m.%Y")
            time_str = dt.strftime("%H:%M МСК")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "04:30 МСК"
        
        # Парсим коэффициенты
        home_odds, away_odds = 2.0, 2.0
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "h2h":
                    for out in market["outcomes"]:
                        if out["name"] == home:
                            home_odds = out["price"]
                        elif out["name"] == away:
                            away_odds = out["price"]
        
        # Локальный расчёт вероятности
        home_prob_local = american_to_probability(home_odds) * 100
        away_prob_local = american_to_probability(away_odds) * 100
        total_local = home_prob_local + away_prob_local
        home_prob_local = (home_prob_local / total_local) * 100
        away_prob_local = (away_prob_local / total_local) * 100
        
        local_winner = home if home_prob_local > away_prob_local else away
        local_prob = round(max(home_prob_local, away_prob_local))
        
        # Пропускаем матчи с низкой вероятностью
        if local_prob < MIN_PROBABILITY:
            print(f"  ⏭️ [{idx}/{total_games}] Пропущен ({local_prob}% < {MIN_PROBABILITY}%): {home} – {away}")
            continue
        
        # Тотал из коэффициентов (фолбэк)
        total_direction_fallback = "БОЛЬШЕ"
        for bk in game.get("bookmakers", []):
            for market in bk.get("markets", []):
                if market["key"] == "totals":
                    for out in market["outcomes"]:
                        if out["name"] == "Over" and out.get("point"):
                            total_direction_fallback = "БОЛЬШЕ"
                        elif out["name"] == "Under" and out.get("point"):
                            total_direction_fallback = "МЕНЬШЕ"
        
        # КОМПАКТНЫЙ ВЫЗОВ DEEPSEEK
        print(f"  🧠 [{idx}/{total_games}] DeepSeek анализирует: {home} – {away}")
        ai_result = call_deepseek_compact(league, home, away)
        
        if ai_result.get("error") is None and ai_result.get("prob_home", 0) > 0:
            # Используем данные от нейросети
            prob_home = ai_result["prob_home"]
            winner = home if prob_home > 0.5 else away
            prob = round(max(prob_home, 1 - prob_home) * 100)
            total_direction = ai_result["total_direction"]
            trend = ai_result["trend"]
            reasoning = ai_result["reasoning"]
            source = "DeepSeek V4"
            
            # Данные о форме
            home_form_str = f"{ai_result['home_wins']}-{ai_result['home_losses']}"
            away_form_str = f"{ai_result['away_wins']}-{ai_result['away_losses']}"
            home_streak_str = f"+{ai_result['home_streak']}" if ai_result['home_streak'] > 0 else f"{ai_result['home_streak']}"
            away_streak_str = f"+{ai_result['away_streak']}" if ai_result['away_streak'] > 0 else f"{ai_result['away_streak']}"
        else:
            # Фолбэк на локальный расчёт
            winner = local_winner
            prob = local_prob
            total_direction = total_direction_fallback
            trend = "Анализ формы временно недоступен"
            reasoning = f"Прогноз на основе коэффициентов: {winner} фаворит"
            source = "Локальный (коэффициенты)"
            home_form_str = "н/д"
            away_form_str = "н/д"
            home_streak_str = "н/д"
            away_streak_str = "н/д"
        
        # Список букмекеров
        bookmakers_list = ", ".join([bk.get("title", "") for bk in game.get("bookmakers", [])[:5]])
        
        total_prediction = f"Тотал {total_direction} {total_line}"
        
        # Формируем КОМПАКТНОЕ объяснение для пользователя (без простыни статистики)
        compact_reasoning = f"{trend}\n{reasoning}" if trend and reasoning else reasoning
        
        match = {
            "date": date_str,
            "time": time_str,
            "home": home,
            "away": away,
            "winner": winner,
            "prob": prob,
            "total_prediction": total_prediction,
            "total_direction": total_direction,
            "bookmakers_list": bookmakers_list,
            # КОМПАКТНЫЕ ДАННЫЕ О ФОРМЕ (без простыни)
            "home_form": home_form_str,      # например "3-2"
            "away_form": away_form_str,      # например "4-1"
            "home_streak": home_streak_str,  # например "+2" или "-1"
            "away_streak": away_streak_str,  # например "+3" или "-2"
            "trend": trend,                   # ключевой тренд одной фразой
            "ai_reasoning": compact_reasoning,  # короткий вывод
            "data_source": source
        }
        
        matches.append(match)
        new_backup.append({
            "date": date_str,
            "home": home,
            "away": away,
            "prediction": winner,
            "total_prediction": total_direction,
            "prob": prob
        })
        
        print(f"  ✅ [{idx}/{total_games}] {home} – {away}: {winner} ({prob}%) | {total_prediction}")
        print(f"       Форма: {home} {home_form_str} ({home_streak_str}) | {away} {away_form_str} ({away_streak_str})")
        
        # Небольшая задержка между запросами к DeepSeek
        time.sleep(1.5)
    
    # Сохраняем результаты
    data_path = os.path.join(repo_root, data_file)
    backup_path = os.path.join(repo_root, backup_file)
    
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": league, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump({"predictions": new_backup}, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Сохранено {len(matches)} матчей {league.upper()}")


def main():
    print(f"🚀 ЗАПУСК (DeepSeek V4 — компактный режим, без лишней статистики)")
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
