#!/usr/bin/env python3
"""
ПРОГНОЗЫ С ИИ (DeepSeek V4) - NBA и NHL
- Реальная статистика ТОЛЬКО из внешних API
- Если данные не загрузились -> "Нет данных"
"""

import json
import os
import re
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
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

TOTAL_LINE_NBA = 225.5
TOTAL_LINE_NHL = 6.5

# ============================================================
# ПОПЫТКА ЗАГРУЗИТЬ NBA API (РЕАЛЬНЫЕ ДАННЫЕ)
# ============================================================

try:
    from nba_api.stats.endpoints import leaguegamefinder
    NBA_API_AVAILABLE = True
    print("✅ NBA API доступен")
except ImportError:
    NBA_API_AVAILABLE = False
    print("⚠️ NBA API не установлен. Установка: pip install nba-api")
    print("   Без него статистика NBA будет недоступна")

_stats_cache = {}

def get_nba_stats_from_api(team_name: str) -> Optional[Dict]:
    """Загружает реальную статистику NBA из официального API"""
    if not NBA_API_AVAILABLE:
        return None
    
    # Маппинг названий для NBA API
    team_mapping = {
        "Los Angeles Lakers": "Lakers",
        "Boston Celtics": "Celtics",
        "Golden State Warriors": "Warriors",
        "San Antonio Spurs": "Spurs",
        "Oklahoma City Thunder": "Thunder",
        "New York Knicks": "Knicks",
        "Denver Nuggets": "Nuggets",
        "Miami Heat": "Heat",
        "Philadelphia 76ers": "76ers",
        "Chicago Bulls": "Bulls",
        "Milwaukee Bucks": "Bucks",
        "Cleveland Cavaliers": "Cavaliers",
        "Houston Rockets": "Rockets",
        "Phoenix Suns": "Suns",
        "Dallas Mavericks": "Mavericks",
        "LA Clippers": "Clippers",
        "Detroit Pistons": "Pistons",
        "Minnesota Timberwolves": "Timberwolves",
        "Memphis Grizzlies": "Grizzlies",
        "Atlanta Hawks": "Hawks",
        "Toronto Raptors": "Raptors",
    }
    
    api_name = team_mapping.get(team_name, team_name.split()[-1])
    
    try:
        game_finder = leaguegamefinder.LeagueGameFinder(
            team_id_nullable=None,
            league_id_nullable='00',
            season_nullable='2025-26',
            season_type_nullable='Regular Season'
        )
        games_df = game_finder.get_data_frames()[0]
        
        team_games = games_df[
            (games_df['TEAM_NAME'].str.contains(api_name, case=False, na=False)) |
            (games_df['TEAM_ABBREVIATION'].str.contains(api_name[:3], case=False, na=False))
        ].head(20)
        
        if len(team_games) < 5:
            return None
        
        # Рассчитываем показатели
        ppg = round(team_games['PTS'].mean(), 1)
        
        last_10 = team_games.head(10)
        wins = len(last_10[last_10['WL'] == 'W'])
        losses = 10 - wins
        form = f"{wins}-{losses}"
        
        streak = "N/A"
        if len(last_10) > 0:
            current_streak = 1
            last_result = last_10.iloc[0]['WL']
            for i in range(1, len(last_10)):
                if last_10.iloc[i]['WL'] == last_result:
                    current_streak += 1
                else:
                    break
            streak = f"{last_result}{current_streak}"
        
        home_games = team_games[team_games['MATCHUP'].str.contains('vs.', na=False)]
        away_games = team_games[team_games['MATCHUP'].str.contains('@', na=False)]
        home_win_pct = round((len(home_games[home_games['WL'] == 'W']) / len(home_games)) * 100) if len(home_games) > 0 else 0
        away_win_pct = round((len(away_games[away_games['WL'] == 'W']) / len(away_games)) * 100) if len(away_games) > 0 else 0
        
        return {
            "ppg": ppg,
            "opp_ppg": round(ppg - (team_games['PLUS_MINUS'].mean() if 'PLUS_MINUS' in team_games else 0), 1),
            "home_win_pct": home_win_pct,
            "away_win_pct": away_win_pct,
            "form": form,
            "streak": streak,
            "source": "NBA API"
        }
    except Exception as e:
        print(f"    NBA API ошибка для {team_name}: {e}")
        return None

def get_nba_stats_from_odds_api(team_name: str, all_completed_games: List[Dict]) -> Optional[Dict]:
    """Пытается рассчитать статистику из завершённых матчей The Odds API"""
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
                team_games.append({
                    "date": game.get("commence_time", ""),
                    "is_home": is_home,
                    "team_score": home_score if is_home else away_score,
                    "opp_score": away_score if is_home else home_score,
                    "won": (home_score > away_score) if is_home else (away_score > home_score)
                })
    
    team_games.sort(key=lambda x: x["date"], reverse=True)
    last_10 = team_games[:10]
    
    if len(last_10) < 5:
        return None
    
    ppg = round(mean([g["team_score"] for g in last_10]), 1)
    opp_ppg = round(mean([g["opp_score"] for g in last_10]), 1)
    wins = sum(1 for g in last_10 if g["won"])
    losses = len(last_10) - wins
    form = f"{wins}-{losses}"
    
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
    
    home_games = [g for g in last_10 if g["is_home"]]
    away_games = [g for g in last_10 if not g["is_home"]]
    home_win_pct = round((sum(1 for g in home_games if g["won"]) / len(home_games)) * 100) if home_games else 0
    away_win_pct = round((sum(1 for g in away_games if g["won"]) / len(away_games)) * 100) if away_games else 0
    
    return {
        "ppg": ppg, "opp_ppg": opp_ppg,
        "home_win_pct": home_win_pct, "away_win_pct": away_win_pct,
        "form": form, "streak": streak,
        "source": "Odds API (история)"
    }

def get_team_stats(league: str, team_name: str, all_completed_games: List[Dict]) -> Dict:
    """Загружает статистику из доступных источников, если ничего нет -> заглушка 'нет данных'"""
    
    if league == "nba":
        # Пробуем NBA API
        stats = get_nba_stats_from_api(team_name)
        if stats:
            return stats
        
        # Пробуем Odds API
        stats = get_nba_stats_from_odds_api(team_name, all_completed_games)
        if stats:
            return stats
    
    elif league == "nhl":
        # Для NHL пробуем Odds API
        stats = get_nhl_stats_from_odds_api(team_name, all_completed_games)
        if stats:
            return stats
    
    # Если ничего не загрузилось - честная заглушка "нет данных"
    return {
        "ppg": "нет данных",
        "opp_ppg": "нет данных",
        "home_win_pct": "нет данных",
        "away_win_pct": "нет данных",
        "form": "нет данных",
        "streak": "нет данных",
        "source": "нет данных"
    }

def get_nhl_stats_from_odds_api(team_name: str, all_completed_games: List[Dict]) -> Optional[Dict]:
    """Рассчитывает NHL статистику из завершённых матчей"""
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
                team_games.append({
                    "date": game.get("commence_time", ""),
                    "is_home": is_home,
                    "team_score": home_score if is_home else away_score,
                    "opp_score": away_score if is_home else home_score,
                    "won": (home_score > away_score) if is_home else (away_score > home_score)
                })
    
    team_games.sort(key=lambda x: x["date"], reverse=True)
    last_10 = team_games[:10]
    
    if len(last_10) < 5:
        return None
    
    ppg = round(mean([g["team_score"] for g in last_10]), 1)
    opp_ppg = round(mean([g["opp_score"] for g in last_10]), 1)
    wins = sum(1 for g in last_10 if g["won"])
    losses = len(last_10) - wins
    form = f"{wins}-{losses}"
    
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
    
    home_games = [g for g in last_10 if g["is_home"]]
    away_games = [g for g in last_10 if not g["is_home"]]
    home_win_pct = round((sum(1 for g in home_games if g["won"]) / len(home_games)) * 100) if home_games else 0
    away_win_pct = round((sum(1 for g in away_games if g["won"]) / len(away_games)) * 100) if away_games else 0
    
    return {
        "ppg": ppg, "opp_ppg": opp_ppg,
        "home_win_pct": home_win_pct, "away_win_pct": away_win_pct,
        "form": form, "streak": streak,
        "source": "Odds API (история)"
    }

def get_h2h_info(league: str, home: str, away: str, all_completed_games: List[Dict]) -> str:
    """Анализирует последние личные встречи"""
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
                    "home": game_home, "away": game_away,
                    "home_score": home_score, "away_score": away_score
                })
    
    if len(h2h_games) < 2:
        return "Нет данных о личных встречах"
    
    home_wins = 0
    away_wins = 0
    totals = []
    for g in h2h_games[-5:]:
        totals.append(g["home_score"] + g["away_score"])
        if g["home_score"] > g["away_score"]:
            if g["home"] == home:
                home_wins += 1
            else:
                away_wins += 1
        else:
            if g["home"] == home:
                away_wins += 1
            else:
                home_wins += 1
    
    avg_total = round(mean(totals), 1) if totals else 0
    return f"Последние 5 встреч: {home} победил {home_wins} раз, {away} — {away_wins} раз. Средний тотал: {avg_total} очков."

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
    
    prompt = f"""Ты эксперт {league_name}. Дай краткий прогноз на матч.

{home} (дома): {stats['home_ppg']} PPG, {stats['home_win_pct']}% побед дома
{away} (в гостях): {stats['away_ppg']} PPG, {stats['away_win_pct']}% побед в гостях
H2H: {stats['h2h']}

Ответь в формате:
ПОБЕДА: (1 предложение)
ТОТАЛ: (1 предложение)"""
    
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
        print(f"    DeepSeek ошибка: {e}")
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
    if not ODDS_API_KEY:
        return []
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores"
    params = {"apiKey": ODDS_API_KEY, "daysFrom": 14}
    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code == 200:
            return [g for g in resp.json() if g.get("completed")]
    except:
        pass
    return []

def update_league(league: str, sport_key: str, data_file: str, backup_file: str, history_file: str):
    print(f"\n{'🏀' if league == 'nba' else '🏒'} ОБНОВЛЕНИЕ {league.upper()}")
    
    repo_root = os.path.dirname(os.path.dirname(__file__))
    
    # Загружаем завершённые матчи
    completed_games = fetch_completed_games(sport_key)
    print(f"📊 Загружено завершённых матчей: {len(completed_games)}")
    
    # ОБНОВЛЕНИЕ ИСТОРИИ
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
        print(f"  ✨ Добавлено {len(new_entries)} записей")
    
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
        
        # ПОЛУЧАЕМ СТАТИСТИКУ (только из API, без локальной базы)
        home_stats = get_team_stats(league, home, completed_games)
        away_stats = get_team_stats(league, away, completed_games)
        h2h_info = get_h2h_info(league, home, away, completed_games)
        
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
        
        print(f"  🤖 [{idx}/{total_games}] DeepSeek: {home} – {away}")
        
        stats_for_ai = {
            'home_ppg': home_stats['ppg'], 'home_win_pct': home_stats['home_win_pct'],
            'home_form': home_stats['form'], 'away_ppg': away_stats['ppg'],
            'away_win_pct': away_stats['away_win_pct'], 'away_form': away_stats['form'],
            'h2h': h2h_info
        }
        ai_winner_reason, ai_total_reason = call_deepseek_ai(league, home, away, stats_for_ai)
        
        if ai_winner_reason:
            final_reason = ai_winner_reason
        else:
            final_reason = f"{winner} побеждает с вероятностью {prob}%"
        
        if ai_total_reason:
            final_total_reason = ai_total_reason
        else:
            final_total_reason = total_prediction
        
        time.sleep(1)
        
        # Преобразуем значения "нет данных" в строку для JSON
        def clean_value(v):
            if isinstance(v, (int, float)) and v == 0:
                return "нет данных"
            return v
        
        match = {
            "date": date_str, "time": time_str,
            "home": home, "away": away,
            "winner": winner, "prob": prob,
            "total_prediction": total_prediction,
            "bookmakers_list": ", ".join([bk.get("title", "") for bk in game.get("bookmakers", [])[:5]]),
            "ai_reasoning": f"{'🏀' if league == 'nba' else '🏒'} ПОБЕДА: {final_reason}\n\n📊 ТОТАЛ: {final_total_reason}",
            "home_ppg": home_stats['ppg'] if isinstance(home_stats.get('ppg'), (int, float)) else "нет данных",
            "away_ppg": away_stats['ppg'] if isinstance(away_stats.get('ppg'), (int, float)) else "нет данных",
            "home_win_pct": home_stats['home_win_pct'] if isinstance(home_stats.get('home_win_pct'), (int, float)) else "нет данных",
            "away_win_pct": away_stats['away_win_pct'] if isinstance(away_stats.get('away_win_pct'), (int, float)) else "нет данных",
            "home_form": home_stats['form'] if home_stats.get('form') != "нет данных" else "нет данных",
            "away_form": away_stats['form'] if away_stats.get('form') != "нет данных" else "нет данных",
            "home_streak": home_stats['streak'] if home_stats.get('streak') != "нет данных" else "нет данных",
            "away_streak": away_stats['streak'] if away_stats.get('streak') != "нет данных" else "нет данных",
            "h2h": h2h_info,
            "injuries": "данные о травмах не загружены",
            "data_source": f"Статистика: {home_stats.get('source', 'нет данных')} / {away_stats.get('source', 'нет данных')}"
        }
        matches.append(match)
        new_backup.append({
            "date": date_str, "home": home, "away": away,
            "prediction": winner, "total_prediction": total_direction, "prob": prob
        })
        print(f"  ✅ {home} – {away}: {winner} ({prob}%) | {total_prediction}")
    
    with open(os.path.join(repo_root, data_file), "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "league": league}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(repo_root, backup_file), "w", encoding="utf-8") as f:
        json.dump({"predictions": new_backup}, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Сохранено {len(matches)} матчей {league.upper()}")

def main():
    print(f"🚀 ЗАПУСК (только реальная статистика из API)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not ODDS_API_KEY:
        print("❌ ODDS_API_KEY не найден")
        return
    
    update_league("nba", SPORT_NBA, "data/nba_matches.json", "data/nba_backup.json", "data/nba_history.json")
    update_league("nhl", SPORT_NHL, "data/nhl_matches.json", "data/nhl_backup.json", "data/nhl_history.json")
    
    print("\n✨ Готово")

if __name__ == "__main__":
    main()
