#!/usr/bin/env python3
"""
ПРОГНОЗЫ С ИИ (DeepSeek V4) - NBA и NHL
- АВТОМАТИЧЕСКИЙ РАСЧЁТ СТАТИСТИКИ из последних 10 игр
- Полностью динамические данные (PPG, форма, серии)
- Обновление статистики каждые сутки
"""

import json
import os
import re
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict
from statistics import mean

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

# Линии тотала
TOTAL_LINE_NBA = 225.5
TOTAL_LINE_NHL = 6.5

# Сколько дней истории загружать для расчёта статистики
HISTORY_DAYS = 30  # Загружаем игры за последние 30 дней

# ============================================================
# КЭШ ДЛЯ СТАТИСТИКИ (чтобы не дёргать API слишком часто)
# ============================================================

_stats_cache = {}  # {(league, team_name): stats_data}
_last_cache_update = {}

def get_or_fetch_team_stats(league: str, team_name: str, all_completed_games: List[Dict]) -> Dict:
    """
    Рассчитывает статистику команды на основе последних 10 игр из переданных результатов.
    Использует кэш для ускорения.
    """
    cache_key = f"{league}_{team_name}"
    
    # Проверяем кэш (действителен 1 час)
    if cache_key in _stats_cache:
        cache_time = _last_cache_update.get(cache_key, 0)
        if time.time() - cache_time < 3600:  # 1 час
            return _stats_cache[cache_key]
    
    # Собираем игры команды из всех завершённых матчей
    team_games = []
    for game in all_completed_games:
        home = game.get("home_team")
        away = game.get("away_team")
        if home == team_name or away == team_name:
            scores = game.get("scores", {})
            home_score = scores.get(home, 0) if isinstance(scores, dict) else 0
            away_score = scores.get(away, 0) if isinstance(scores, dict) else 0
            
            if home_score > 0 or away_score > 0:
                is_home = (home == team_name)
                team_score = home_score if is_home else away_score
                opp_score = away_score if is_home else home_score
                won = team_score > opp_score
                
                team_games.append({
                    "date": game.get("commence_time", ""),
                    "is_home": is_home,
                    "team_score": team_score,
                    "opp_score": opp_score,
                    "won": won
                })
    
    # Сортируем по дате и берём последние 10 игр
    team_games.sort(key=lambda x: x["date"], reverse=True)
    last_10 = team_games[:10]
    
    if not last_10:
        # Если нет данных — возвращаем дефолтные значения
        return get_default_stats(league, team_name)
    
    # Рассчитываем PPG (среднее очков за игру)
    ppg = round(mean([g["team_score"] for g in last_10]), 1)
    
    # Рассчитываем форму (победы/поражения)
    wins = sum(1 for g in last_10 if g["won"])
    losses = len(last_10) - wins
    form = f"{wins}-{losses}"
    
    # Рассчитываем текущую серию
    streak = "N/A"
    if last_10:
        current_streak = 1
        last_result = "W" if last_10[0]["won"] else "L"
        for i in range(1, len(last_10)):
            is_won = last_10[i]["won"]
            if (is_won and last_result == "W") or (not is_won and last_result == "L"):
                current_streak += 1
            else:
                break
        streak = f"{last_result}{current_streak}"
    
    # Рассчитываем процент побед дома и в гостях
    home_games = [g for g in last_10 if g["is_home"]]
    away_games = [g for g in last_10 if not g["is_home"]]
    home_win_pct = round((sum(1 for g in home_games if g["won"]) / len(home_games)) * 100) if home_games else 50
    away_win_pct = round((sum(1 for g in away_games if g["won"]) / len(away_games)) * 100) if away_games else 45
    
    # Рассчитываем PPG пропускает
    opp_ppg = round(mean([g["opp_score"] for g in last_10]), 1) if last_10 else ppg
    
    stats = {
        "ppg": ppg,
        "opp_ppg": opp_ppg,
        "home_win_pct": home_win_pct,
        "away_win_pct": away_win_pct,
        "form": form,
        "streak": streak,
        "games_analyzed": len(last_10),
        "data_source": "Авторасчёт из последних 10 игр"
    }
    
    # Сохраняем в кэш
    _stats_cache[cache_key] = stats
    _last_cache_update[cache_key] = time.time()
    
    return stats

def get_default_stats(league: str, team_name: str) -> Dict:
    """Возвращает дефолтную статистику, если нет данных об играх"""
    if league == "nba":
        return {
            "ppg": 110.0, "opp_ppg": 110.0,
            "home_win_pct": 50.0, "away_win_pct": 45.0,
            "form": "5-5", "streak": "N/A",
            "data_source": "Дефолтные значения (нет данных об играх)"
        }
    else:
        return {
            "ppg": 3.0, "opp_ppg": 3.0,
            "home_win_pct": 50.0, "away_win_pct": 45.0,
            "form": "5-5", "streak": "N/A",
            "data_source": "Дефолтные значения (нет данных об играх)"
        }

def get_h2h_info(league: str, home: str, away: str, all_completed_games: List[Dict]) -> str:
    """Анализирует последние 5 личных встреч команд"""
    h2h_games = []
    for game in all_completed_games:
        game_home = game.get("home_team")
        game_away = game.get("away_team")
        if (game_home == home and game_away == away) or (game_home == away and game_away == home):
            scores = game.get("scores", {})
            home_score = scores.get(game_home, 0) if isinstance(scores, dict) else 0
            away_score = scores.get(game_away, 0) if isinstance(scores, dict) else 0
            if home_score > 0 or away_score > 0:
                h2h_games.append({
                    "date": game.get("commence_time", ""),
                    "home": game_home,
                    "away": game_away,
                    "home_score": home_score,
                    "away_score": away_score,
                    "winner": game_home if home_score > away_score else game_away
                })
    
    # Сортируем по дате и берём последние 5
    h2h_games.sort(key=lambda x: x["date"], reverse=True)
    last_5 = h2h_games[:5]
    
    if not last_5:
        return f"Нет данных о личных встречах {home} и {away}"
    
    home_wins = sum(1 for g in last_5 if g["winner"] == home)
    away_wins = len(last_5) - home_wins
    
    avg_total = round(mean([g["home_score"] + g["away_score"] for g in last_5]), 1) if last_5 else 0
    
    return f"Последние 5 встреч: {home} победил {home_wins} раз, {away} — {away_wins} раз. Средний тотал: {avg_total} очков."

def get_bookmakers_list(bookmakers: List[Dict]) -> str:
    if not bookmakers:
        return "Данные не загружены"
    names = []
    for bk in bookmakers[:5]:
        name = bk.get("title", bk.get("key", "")).capitalize()
        if name:
            names.append(name)
    return ", ".join(names)

def american_to_probability(american_odds: int) -> float:
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)

def call_deepseek_ai(league: str, home: str, away: str, stats: Dict) -> Tuple[Optional[str], Optional[str]]:
    if not OPENROUTER_API_KEY:
        return None, None
    
    total_line = TOTAL_LINE_NHL if league == "nhl" else TOTAL_LINE_NBA
    league_name = "NHL" if league == "nhl" else "NBA"
    
    prompt = f"""Ты эксперт {league_name}. Дай краткий прогноз на матч (2-3 предложения).

АКТУАЛЬНАЯ СТАТИСТИКА (рассчитана из последних 10 игр):

{home} (дома):
- PPG: {stats['home_ppg']}
- Против PPG: {stats['home_opp_ppg']}
- Побед дома: {stats['home_win_pct']}%
- Форма: {stats['home_form']}
- Серия: {stats['home_streak']}

{away} (в гостях):
- PPG: {stats['away_ppg']}
- Против PPG: {stats['away_opp_ppg']}
- Побед в гостях: {stats['away_win_pct']}%
- Форма: {stats['away_form']}
- Серия: {stats['away_streak']}

Личные встречи: {stats['h2h']}
Линия тотала: {total_line}

Ответь в формате:
ПОБЕДА: (твой прогноз, 1 предложение)
ТОТАЛ: (твой прогноз, 1 предложение)"""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 150
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if response.status_code == 200:
            full = response.json()['choices'][0]['message']['content'].strip()
            winner_reason = ""
            total_reason = ""
            for line in full.split('\n'):
                if line.startswith('ПОБЕДА:'):
                    winner_reason = line.replace('ПОБЕДА:', '').strip()
                elif line.startswith('ТОТАЛ:'):
                    total_reason = line.replace('ТОТАЛ:', '').strip()
            return winner_reason, total_reason
    except Exception as e:
        print(f"    ⚠️ DeepSeek ошибка: {e}")
    return None, None

def fetch_upcoming_games(sport: str) -> List[Dict]:
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": REGIONS, "markets": MARKETS, "oddsFormat": "american"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        return resp.json() if resp.status_code == 200 else []
    except:
        return []

def fetch_completed_games(sport: str) -> List[Dict]:
    """Загружает завершённые матчи за последние HISTORY_DAYS дней"""
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores"
    params = {"apiKey": ODDS_API_KEY, "daysFrom": HISTORY_DAYS, "dateFormat": "iso"}
    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code == 200:
            games = resp.json()
            return [g for g in games if g.get("completed", False)]
    except Exception as e:
        print(f"    ⚠️ Ошибка загрузки результатов: {e}")
    return []

def update_league(league: str, sport_key: str, data_file: str, backup_file: str, history_file: str):
    print(f"\n{'🏀' if league == 'nba' else '🏒'} ОБНОВЛЕНИЕ {league.upper()}")
    
    repo_root = os.path.dirname(os.path.dirname(__file__))
    
    # ===== 1. ЗАГРУЖАЕМ ЗАВЕРШЁННЫЕ МАТЧИ ДЛЯ РАСЧЁТА СТАТИСТИКИ =====
    print(f"📊 Загрузка результатов за последние {HISTORY_DAYS} дней...")
    completed_games = fetch_completed_games(sport_key)
    print(f"   Найдено завершённых матчей: {len(completed_games)}")
    
    # ===== 2. ОБНОВЛЕНИЕ ИСТОРИИ ПРОГНОЗОВ =====
    history_path = os.path.join(repo_root, history_file)
    backup_path = os.path.join(repo_root, backup_file)
    
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
    
    for game in completed_games[:50]:  # Ограничиваем для производительности
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
        
        total_line = TOTAL_LINE_NHL if league == "nhl" else TOTAL_LINE_NBA
        actual_total = home_score + away_score
        predicted_total = backup[key].get("total_prediction", "БОЛЬШЕ")
        total_result = "success" if (predicted_total == "БОЛЬШЕ" and actual_total > total_line) or (predicted_total == "МЕНЬШЕ" and actual_total < total_line) else "failed"
        
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
    
    # ===== 3. ОБНОВЛЕНИЕ ПРЕДСТОЯЩИХ МАТЧЕЙ =====
    games = fetch_upcoming_games(sport_key)
    if not games:
        print(f"❌ Нет данных для {league}")
        return
    
    matches = []
    new_backup = []
    
    total_games = len(games)
    print(f"📋 Найдено {total_games} предстоящих матчей. Обрабатываю...")
    
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
        
        # ===== РАСЧЁТ АКТУАЛЬНОЙ СТАТИСТИКИ =====
        home_stats = get_or_fetch_team_stats(league, home, completed_games)
        away_stats = get_or_fetch_team_stats(league, away, completed_games)
        h2h_info = get_h2h_info(league, home, away, completed_games)
        
        stats_for_ai = {
            'home_ppg': home_stats['ppg'], 'home_opp_ppg': home_stats['opp_ppg'],
            'home_win_pct': home_stats['home_win_pct'], 'home_form': home_stats['form'],
            'home_streak': home_stats['streak'],
            'away_ppg': away_stats['ppg'], 'away_opp_ppg': away_stats['opp_ppg'],
            'away_win_pct': away_stats['away_win_pct'], 'away_form': away_stats['form'],
            'away_streak': away_stats['streak'],
            'h2h': h2h_info
        }
        
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
        
        home_prob = american_to_probability(home_odds) * 100
        away_prob = american_to_probability(away_odds) * 100
        total = home_prob + away_prob
        home_prob = (home_prob / total) * 100
        away_prob = (away_prob / total) * 100
        
        if home_prob > away_prob:
            winner = home
            prob = round(home_prob)
        else:
            winner = away
            prob = round(away_prob)
        
        if prob < MIN_PROBABILITY:
            print(f"  ⏭️ [{idx}/{total_games}] Пропущен ({prob}% < {MIN_PROBABILITY}%): {home} – {away}")
            continue
        
        # Прогноз тотала
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
        
        print(f"  🤖 [{idx}/{total_games}] DeepSeek анализирует: {home} – {away}")
        ai_winner_reason, ai_total_reason = call_deepseek_ai(league, home, away, stats_for_ai)
        
        if ai_winner_reason:
            final_reason = ai_winner_reason
        else:
            final_reason = f"{winner} побеждает с вероятностью {prob}% (статистика: форма {home_stats['form']} vs {away_stats['form']})"
        
        if ai_total_reason:
            final_total_reason = ai_total_reason
        else:
            final_total_reason = total_prediction
        
        time.sleep(1)  # Задержка между запросами к DeepSeek
        
        match = {
            "date": date_str, "time": time_str,
            "home": home, "away": away,
            "winner": winner, "prob": prob,
            "total_prediction": total_prediction,
            "bookmakers_list": get_bookmakers_list(game.get("bookmakers", [])),
            "ai_reasoning": f"{'🏀' if league == 'nba' else '🏒'} ПОБЕДА: {final_reason}\n\n📊 ТОТАЛ: {final_total_reason}",
            "home_ppg": home_stats['ppg'], "away_ppg": away_stats['ppg'],
            "home_win_pct": home_stats['home_win_pct'], "away_win_pct": away_stats['away_win_pct'],
            "home_form": home_stats['form'], "away_form": away_stats['form'],
            "home_streak": home_stats['streak'], "away_streak": away_stats['streak'],
            "h2h": h2h_info,
            "injuries": "✅ По данным API",
            "data_source": f"Автостатистика ({home_stats['games_analyzed'] if 'games_analyzed' in home_stats else 10}+ игр) + DeepSeek AI"
        }
        matches.append(match)
        new_backup.append({
            "date": date_str, "home": home, "away": away,
            "prediction": winner, "total_prediction": total_direction, "prob": prob
        })
        print(f"  ✅ [{idx}/{total_games}] {home} – {away}: {winner} ({prob}%) | {total_prediction}")
    
    with open(os.path.join(repo_root, data_file), "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": league}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(repo_root, backup_file), "w", encoding="utf-8") as f:
        json.dump({"predictions": new_backup}, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Сохранено {len(matches)} матчей {league.upper()}")

def main():
    print(f"🚀 ЗАПУСК (NBA + NHL с АВТОСТАТИСТИКОЙ)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Минимальная вероятность: {MIN_PROBABILITY}%")
    
    if not ODDS_API_KEY:
        print("❌ ODDS_API_KEY не найден в Secrets")
        return
    
    update_league("nba", SPORT_NBA, "data/nba_matches.json", "data/nba_backup.json", "data/nba_history.json")
    update_league("nhl", SPORT_NHL, "data/nhl_matches.json", "data/nhl_backup.json", "data/nhl_history.json")
    
    print("\n✨ Готово")

if __name__ == "__main__":
    main()
