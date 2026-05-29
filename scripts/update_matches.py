#!/usr/bin/env python3
"""
ПРОГНОЗЫ С ИИ (DeepSeek V4) - КОМПАКТНЫЙ ПОДХОД
- Нейросеть возвращает только структурированные данные: форма, тренд, вероятность
- Автоматическое создание файлов истории, если их нет
- Корректное обновление статистики угадываний
"""

import json
import os
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

# ============================================================
# НАСТРОЙКИ
# ============================================================

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

SPORT_NBA = "basketball_nba"
SPORT_NHL = "icehockey_nhl"
MIN_PROBABILITY = 55

TOTAL_LINE_NBA = 225.5
TOTAL_LINE_NHL = 6.5

# ============================================================
# КОМПАКТНЫЙ ВЫЗОВ DEEPSEEK
# ============================================================

def call_deepseek_compact(league: str, home: str, away: str) -> Dict[str, Any]:
    """Компактный вызов DeepSeek — только суть для пользователя."""
    if not OPENROUTER_API_KEY:
        return {"error": "OPENROUTER_API_KEY не найден"}
    
    total_line = TOTAL_LINE_NHL if league == "nhl" else TOTAL_LINE_NBA
    league_name = "NHL" if league == "nhl" else "NBA"
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
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
TREND|ОДНА КОРОТКАЯ ФРАЗА (ключевой тренд)
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
        
        result = {
            "home_wins": 0, "home_losses": 0, "home_streak": 0,
            "away_wins": 0, "away_losses": 0, "away_streak": 0,
            "trend": "", "reasoning": "", "prob_home": 0.5, "total_direction": "БОЛЬШЕ",
            "error": None
        }
        
        for line in content.split('\n'):
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
                    result["prob_home"] = float(line.split("|")[1]) / 100
                except:
                    pass
            elif line.startswith("TOTAL|"):
                total_val = line.split("|")[1].strip().upper()
                if "МЕНЬШЕ" in total_val or "UNDER" in total_val:
                    result["total_direction"] = "МЕНЬШЕ"
                else:
                    result["total_direction"] = "БОЛЬШЕ"
        
        return result
    except Exception as e:
        return {"error": str(e)}


def get_fallback_prediction(home: str, away: str, home_odds: float, away_odds: float, total_direction_fallback: str) -> Dict[str, Any]:
    """Локальный расчёт на основе коэффициентов (если DeepSeek недоступен)"""
    home_prob = american_to_probability(home_odds) * 100
    away_prob = american_to_probability(away_odds) * 100
    total = home_prob + away_prob
    home_prob = (home_prob / total) * 100
    
    return {
        "prob_home": home_prob / 100,
        "total_direction": total_direction_fallback,
        "home_wins": 0, "home_losses": 0, "home_streak": 0,
        "away_wins": 0, "away_losses": 0, "away_streak": 0,
        "trend": "Анализ формы временно недоступен",
        "reasoning": f"Прогноз на основе коэффициентов",
        "error": None,
        "is_fallback": True
    }


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
            games = resp.json()
            return [g for g in games if g.get("completed", False)]
    except Exception as e:
        print(f"    ⚠️ Ошибка загрузки счетов: {e}")
    return []


def ensure_history_file(history_path: str) -> None:
    """Создаёт файл истории, если его нет"""
    if not os.path.exists(history_path):
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump({"predictions": []}, f, ensure_ascii=False, indent=2)
        print(f"  📁 Создан новый файл истории: {os.path.basename(history_path)}")


def update_history(league: str, sport_key: str, backup_file: str, history_file: str):
    """Обновление истории завершённых матчей"""
    print(f"\n  📜 Обновление истории {league.upper()}...")
    
    repo_root = os.path.dirname(os.path.dirname(__file__))
    history_path = os.path.join(repo_root, history_file)
    backup_path = os.path.join(repo_root, backup_file)
    
    # СОЗДАЁМ ФАЙЛ ИСТОРИИ, ЕСЛИ ЕГО НЕТ
    ensure_history_file(history_path)
    
    # Проверяем, есть ли бэкап
    if not os.path.exists(backup_path):
        print(f"  ⚠️ Файл бэкапа {backup_file} не найден, историю не обновить")
        return
    
    completed_games = fetch_completed_games(sport_key, 14)
    if not completed_games:
        print(f"  ⚠️ Нет завершённых матчей за последние 14 дней")
        return
    
    # Загружаем существующую историю
    with open(history_path, "r", encoding="utf-8") as f:
        history = json.load(f)
    
    existing_keys = {(p["date"], p["home"], p["away"]) for p in history.get("predictions", [])}
    
    # Загружаем бэкап прогнозов
    with open(backup_path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)
        backup = {(p["date"], p["home"], p["away"]): p for p in backup_data.get("predictions", [])}
    
    total_line = TOTAL_LINE_NBA if league == "nba" else TOTAL_LINE_NHL
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
        
        # Пропускаем уже добавленные
        if key in existing_keys:
            continue
        
        # Пропускаем, если нет прогноза в бэкапе
        if key not in backup:
            print(f"    ⏭️ Нет прогноза в бэкапе: {home} – {away}")
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
            "actual_score": f"{home_score} : {away_score}",
            "actual_total": actual_total,
            "prob": prob
        })
        
        result_emoji = "✅" if result == "success" else "❌"
        print(f"    {result_emoji} {home} – {away}: предсказали {predicted_winner} → {actual_winner}")
    
    if new_entries:
        history["predictions"] = new_entries + history.get("predictions", [])
        # Ограничиваем историю последними 100 записями
        history["predictions"] = history["predictions"][:100]
        history["last_updated"] = datetime.now().isoformat()
        
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
        wins = sum(1 for e in new_entries if e["result"] == "success")
        print(f"  ✨ Добавлено {len(new_entries)} записей в историю (угадано {wins}/{len(new_entries)})")
    else:
        print(f"  📭 Новых завершённых матчей для истории нет")


def update_league(league: str, sport_key: str, data_file: str, backup_file: str, history_file: str):
    """Обновление одной лиги (NBA или NHL)"""
    print(f"\n{'🏀' if league == 'nba' else '🏒'} ОБНОВЛЕНИЕ {league.upper()}")
    
    repo_root = os.path.dirname(os.path.dirname(__file__))
    
    # 1. ОБНОВЛЯЕМ ИСТОРИЮ
    update_history(league, sport_key, backup_file, history_file)
    
    # 2. ПОЛУЧАЕМ ПРЕДСТОЯЩИЕ МАТЧИ
    print(f"\n  🎲 Загрузка предстоящих матчей...")
    games = fetch_upcoming_games(sport_key)
    if not games:
        print(f"  ❌ Нет данных для {league}")
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
        
        # Локальный расчёт вероятности для фильтрации
        home_prob_local = american_to_probability(home_odds) * 100
        away_prob_local = american_to_probability(away_odds) * 100
        total_local = home_prob_local + away_prob_local
        home_prob_local = (home_prob_local / total_local) * 100
        local_prob = round(max(home_prob_local, 100 - home_prob_local))
        
        # Пропускаем матчи с низкой вероятностью
        if local_prob < MIN_PROBABILITY:
            print(f"  ⏭️ [{idx}/{total_games}] Пропущен ({local_prob}% < {MIN_PROBABILITY}%): {home} – {away}")
            continue
        
        # КОМПАКТНЫЙ ВЫЗОВ DEEPSEEK
        print(f"  🧠 [{idx}/{total_games}] DeepSeek анализирует: {home} – {away}")
        ai_result = call_deepseek_compact(league, home, away)
        
        if ai_result.get("error") is None and ai_result.get("prob_home", 0) > 0:
            prob_home = ai_result["prob_home"]
            winner = home if prob_home > 0.5 else away
            prob = round(max(prob_home, 1 - prob_home) * 100)
            total_direction = ai_result["total_direction"]
            trend = ai_result["trend"]
            reasoning = ai_result["reasoning"]
            source = "DeepSeek V4"
            home_form = f"{ai_result['home_wins']}-{ai_result['home_losses']}"
            away_form = f"{ai_result['away_wins']}-{ai_result['away_losses']}"
            home_streak = f"+{ai_result['home_streak']}" if ai_result['home_streak'] > 0 else f"{ai_result['home_streak']}"
            away_streak = f"+{ai_result['away_streak']}" if ai_result['away_streak'] > 0 else f"{ai_result['away_streak']}"
        else:
            if ai_result.get("error"):
                print(f"    ⚠️ Ошибка DeepSeek: {ai_result['error']}, использую локальный расчёт")
            winner = home if home_prob_local > 50 else away
            prob = local_prob
            total_direction = total_direction_fallback
            trend = "Анализ формы временно недоступен"
            reasoning = "Прогноз на основе коэффициентов букмекеров"
            source = "Локальный (коэффициенты)"
            home_form = "?"
            away_form = "?"
            home_streak = "?"
            away_streak = "?"
        
        bookmakers_list = ", ".join([bk.get("title", "") for bk in game.get("bookmakers", [])[:5]])
        total_prediction = f"Тотал {total_direction} {total_line}"
        compact_reasoning = f"{trend}\n{reasoning}" if trend and reasoning else reasoning or "Анализ проведён"
        
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
            "home_form": home_form,
            "away_form": away_form,
            "home_streak": home_streak,
            "away_streak": away_streak,
            "trend": trend,
            "ai_reasoning": compact_reasoning,
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
        print(f"       Форма: {home_form} ({home_streak}) | {away_form} ({away_streak})")
        
        time.sleep(1.5)
    
    # Сохраняем результаты
    data_path = os.path.join(repo_root, data_file)
    backup_path = os.path.join(repo_root, backup_file)
    
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": league, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump({"predictions": new_backup, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ Сохранено {len(matches)} матчей {league.upper()}")


def main():
    print(f"🚀 ЗАПУСК (DeepSeek V4 — компактный режим)")
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
