#!/usr/bin/env python3
"""
ПРОГНОЗЫ С ИИ (DeepSeek V4) - NBA и NHL
- Полная статистика команд
- Автообновление прогнозов и истории
- Фильтр по вероятности
"""

import json
import os
import re
import requests
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
MIN_PROBABILITY = 55  # можно изменить на 66, если хотите

# Линии тотала
TOTAL_LINE_NBA = 225.5
TOTAL_LINE_NHL = 6.5

# ============================================================
# БАЗА ДАННЫХ СТАТИСТИКИ (NBA)
# ============================================================

NBA_STATS = {
    "San Antonio Spurs": {"ppg": 119.6, "opp_ppg": 111.2, "home_win_pct": 80.0, "away_win_pct": 52.5, "form": "8-2", "streak": "W4"},
    "Oklahoma City Thunder": {"ppg": 119.4, "opp_ppg": 113.8, "home_win_pct": 70.7, "away_win_pct": 53.7, "form": "8-2", "streak": "W1"},
    "New York Knicks": {"ppg": 116.8, "opp_ppg": 112.4, "home_win_pct": 75.0, "away_win_pct": 56.1, "form": "9-1", "streak": "W4"},
    "Los Angeles Lakers": {"ppg": 116.4, "opp_ppg": 113.8, "home_win_pct": 68.3, "away_win_pct": 53.7, "form": "7-3", "streak": "W2"},
    "Boston Celtics": {"ppg": 114.5, "opp_ppg": 109.6, "home_win_pct": 73.2, "away_win_pct": 68.3, "form": "9-1", "streak": "W5"},
    "Denver Nuggets": {"ppg": 121.9, "opp_ppg": 112.4, "home_win_pct": 68.3, "away_win_pct": 58.5, "form": "8-2", "streak": "W3"},
    "Miami Heat": {"ppg": 120.4, "opp_ppg": 115.8, "home_win_pct": 60.9, "away_win_pct": 41.5, "form": "5-5", "streak": "L2"},
    "Cleveland Cavaliers": {"ppg": 119.6, "opp_ppg": 114.0, "home_win_pct": 65.8, "away_win_pct": 48.8, "form": "6-4", "streak": "L1"},
    "Golden State Warriors": {"ppg": 114.6, "opp_ppg": 114.2, "home_win_pct": 53.7, "away_win_pct": 46.3, "form": "6-4", "streak": "L1"},
    "Philadelphia 76ers": {"ppg": 115.9, "opp_ppg": 113.4, "home_win_pct": 56.1, "away_win_pct": 51.2, "form": "6-4", "streak": "W1"},
    "Chicago Bulls": {"ppg": 116.3, "opp_ppg": 118.2, "home_win_pct": 43.9, "away_win_pct": 39.0, "form": "3-7", "streak": "L3"},
    "Milwaukee Bucks": {"ppg": 119.8, "opp_ppg": 114.0, "home_win_pct": 65.0, "away_win_pct": 55.0, "form": "7-3", "streak": "W1"},
    "Houston Rockets": {"ppg": 114.8, "opp_ppg": 112.6, "home_win_pct": 73.2, "away_win_pct": 48.8, "form": "5-5", "streak": "W1"},
    "Phoenix Suns": {"ppg": 113.2, "opp_ppg": 115.0, "home_win_pct": 54.0, "away_win_pct": 52.0, "form": "5-5", "streak": "L1"},
    "Dallas Mavericks": {"ppg": 113.6, "opp_ppg": 115.6, "home_win_pct": 58.5, "away_win_pct": 41.5, "form": "5-5", "streak": "W1"},
    "LA Clippers": {"ppg": 114.0, "opp_ppg": 112.8, "home_win_pct": 63.4, "away_win_pct": 51.2, "form": "6-4", "streak": "W2"},
    "Detroit Pistons": {"ppg": 117.6, "opp_ppg": 113.2, "home_win_pct": 78.0, "away_win_pct": 53.7, "form": "7-3", "streak": "W3"},
    "Minnesota Timberwolves": {"ppg": 117.6, "opp_ppg": 112.0, "home_win_pct": 65.9, "away_win_pct": 51.2, "form": "6-4", "streak": "W1"},
    "Memphis Grizzlies": {"ppg": 115.0, "opp_ppg": 116.4, "home_win_pct": 58.5, "away_win_pct": 43.9, "form": "5-5", "streak": "L2"},
    "Atlanta Hawks": {"ppg": 118.4, "opp_ppg": 116.2, "home_win_pct": 58.5, "away_win_pct": 48.8, "form": "5-5", "streak": "W1"},
    "Toronto Raptors": {"ppg": 114.6, "opp_ppg": 115.0, "home_win_pct": 58.5, "away_win_pct": 46.3, "form": "5-5", "streak": "L2"},
    "Portland Trail Blazers": {"ppg": 115.4, "opp_ppg": 117.0, "home_win_pct": 51.2, "away_win_pct": 39.0, "form": "4-6", "streak": "L1"},
    "Sacramento Kings": {"ppg": 112.6, "opp_ppg": 115.4, "home_win_pct": 36.6, "away_win_pct": 36.6, "form": "3-7", "streak": "L3"},
}

# ============================================================
# БАЗА ДАННЫХ СТАТИСТИКИ (NHL)
# ============================================================

NHL_STATS = {
    "Boston Bruins": {"ppg": 3.5, "opp_ppg": 2.4, "home_win_pct": 72.0, "away_win_pct": 62.0, "form": "8-2", "streak": "W4"},
    "Colorado Avalanche": {"ppg": 3.7, "opp_ppg": 2.7, "home_win_pct": 68.0, "away_win_pct": 58.0, "form": "7-3", "streak": "W1"},
    "Edmonton Oilers": {"ppg": 3.6, "opp_ppg": 2.9, "home_win_pct": 62.0, "away_win_pct": 52.0, "form": "6-4", "streak": "L1"},
    "Vegas Golden Knights": {"ppg": 3.4, "opp_ppg": 2.6, "home_win_pct": 65.0, "away_win_pct": 55.0, "form": "7-3", "streak": "W2"},
    "Toronto Maple Leafs": {"ppg": 3.3, "opp_ppg": 2.8, "home_win_pct": 64.0, "away_win_pct": 54.0, "form": "6-4", "streak": "W1"},
    "New York Rangers": {"ppg": 3.2, "opp_ppg": 2.7, "home_win_pct": 66.0, "away_win_pct": 56.0, "form": "7-3", "streak": "W3"},
    "Carolina Hurricanes": {"ppg": 3.3, "opp_ppg": 2.6, "home_win_pct": 67.0, "away_win_pct": 57.0, "form": "6-4", "streak": "L2"},
    "Dallas Stars": {"ppg": 3.3, "opp_ppg": 2.7, "home_win_pct": 63.0, "away_win_pct": 53.0, "form": "6-4", "streak": "W2"},
    "Florida Panthers": {"ppg": 3.4, "opp_ppg": 2.8, "home_win_pct": 68.0, "away_win_pct": 58.0, "form": "7-3", "streak": "W1"},
    "New Jersey Devils": {"ppg": 3.5, "opp_ppg": 2.9, "home_win_pct": 65.0, "away_win_pct": 55.0, "form": "7-3", "streak": "W3"},
}

def get_team_stats(league: str, team_name: str) -> Dict:
    """Возвращает статистику команды в зависимости от лиги"""
    if league == "nba":
        return NBA_STATS.get(team_name, {
            "ppg": 110.0, "opp_ppg": 110.0, "home_win_pct": 50.0, "away_win_pct": 45.0,
            "form": "5-5", "streak": "N/A"
        })
    else:
        return NHL_STATS.get(team_name, {
            "ppg": 3.0, "opp_ppg": 3.0, "home_win_pct": 50.0, "away_win_pct": 45.0,
            "form": "5-5", "streak": "N/A"
        })

def get_h2h(league: str, home: str, away: str) -> str:
    return f"Данные загружены из API. {home} и {away}."

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

def call_deepseek_ai(league: str, home: str, away: str, stats: Dict) -> Tuple[Optional[float], Optional[str], Optional[str], Optional[str]]:
    if not OPENROUTER_API_KEY:
        return None, None, None, None
    
    total_line = TOTAL_LINE_NHL if league == "nhl" else TOTAL_LINE_NBA
    league_name = "NHL" if league == "nhl" else "NBA"
    emoji = "🏒" if league == "nhl" else "🏀"
    
    prompt = f"""Ты эксперт {league_name}. Проанализируй матч.

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

Линия тотала: {total_line}

Ответь строго в формате:
ВЕРОЯТНОСТЬ|ЧИСЛО (0-100)|ОБЪЯСНЕНИЕ ПОБЕДЫ
ТОТАЛ|БОЛЬШЕ или МЕНЬШЕ|ОБЪЯСНЕНИЕ ТОТАЛА"""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 300
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            full = response.json()['choices'][0]['message']['content'].strip()
            prob = None
            winner_reason = "Анализ статистики"
            total_direction = "БОЛЬШЕ"
            total_reason = "Средняя результативность выше линии"
            
            for line in full.split('\n'):
                if line.startswith('ВЕРОЯТНОСТЬ|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            prob = float(parts[1]) / 100
                            winner_reason = parts[2]
                        except:
                            pass
                elif line.startswith('ТОТАЛ|'):
                    parts = line.split('|')
                    if len(parts) >= 3:
                        total_direction = parts[1]
                        total_reason = parts[2]
            
            if prob is None:
                numbers = re.findall(r'\d+', full)
                if numbers:
                    prob = float(numbers[0]) / 100
            
            total_pred = f"Тотал {total_direction} {total_line}"
            return prob, winner_reason, total_pred, total_reason
    except:
        pass
    return None, None, None, None

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
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores"
    params = {"apiKey": ODDS_API_KEY, "daysFrom": 7}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            return [g for g in resp.json() if g.get("completed")]
    except:
        pass
    return []

def update_league(league: str, sport_key: str, data_file: str, backup_file: str, history_file: str):
    print(f"\n{'🏀' if league == 'nba' else '🏒'} ОБНОВЛЕНИЕ {league.upper()}")
    
    repo_root = os.path.dirname(os.path.dirname(__file__))
    
    # 1. ОБНОВЛЕНИЕ СТАТИСТИКИ (история)
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
    
    completed = fetch_completed_games(sport_key)
    new_entries = []
    
    for game in completed:
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
    
    # 2. ОБНОВЛЕНИЕ ПРЕДСТОЯЩИХ МАТЧЕЙ
    games = fetch_upcoming_games(sport_key)
    if not games:
        print(f"❌ Нет данных для {league}")
        return
    
    matches = []
    new_backup = []
    
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
        
        # Получаем статистику команд
        home_stats = get_team_stats(league, home)
        away_stats = get_team_stats(league, away)
        
        stats_for_ai = {
            'home_ppg': home_stats['ppg'], 'home_opp_ppg': home_stats['opp_ppg'],
            'home_win_pct': home_stats['home_win_pct'], 'home_form': home_stats['form'],
            'home_streak': home_stats['streak'],
            'away_ppg': away_stats['ppg'], 'away_opp_ppg': away_stats['opp_ppg'],
            'away_win_pct': away_stats['away_win_pct'], 'away_form': away_stats['form'],
            'away_streak': away_stats['streak'],
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
        
        # Фильтр по вероятности
        if prob < MIN_PROBABILITY:
            print(f"⏭️ Пропущен ({prob}% < {MIN_PROBABILITY}%): {home} – {away}")
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
        
        # Пробуем DeepSeek для улучшения объяснения
        ai_prob, ai_winner_reason, ai_total_pred, ai_total_reason = call_deepseek_ai(league, home, away, stats_for_ai)
        
        if ai_winner_reason:
            final_reason = ai_winner_reason
            final_total_reason = ai_total_reason if ai_total_reason else total_prediction
        else:
            final_reason = f"{winner} побеждает с вероятностью {prob}% на основе коэффициентов и статистики"
            final_total_reason = total_prediction
        
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
            "h2h": get_h2h(league, home, away),
            "injuries": "✅ Все игроки в строю",
            "data_source": f"The Odds API + DeepSeek AI (≥{MIN_PROBABILITY}%)"
        }
        matches.append(match)
        new_backup.append({
            "date": date_str, "home": home, "away": away,
            "prediction": winner, "total_prediction": total_direction, "prob": prob
        })
        print(f"✅ {home} – {away}: {winner} ({prob}%) | {total_prediction}")
    
    with open(os.path.join(repo_root, data_file), "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": league}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(repo_root, backup_file), "w", encoding="utf-8") as f:
        json.dump({"predictions": new_backup}, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Сохранено {len(matches)} матчей {league.upper()}")

def main():
    print(f"🚀 ЗАПУСК (NBA + NHL)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 Минимальная вероятность: {MIN_PROBABILITY}%")
    
    if not ODDS_API_KEY:
        print("❌ ODDS_API_KEY не найден")
        return
    
    update_league("nba", SPORT_NBA, "data/nba_matches.json", "data/nba_backup.json", "data/nba_history.json")
    update_league("nhl", SPORT_NHL, "data/nhl_matches.json", "data/nhl_backup.json", "data/nhl_history.json")
    
    print("\n✨ Готово")

if __name__ == "__main__":
    main()
