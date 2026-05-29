#!/usr/bin/env python3
"""
ПРОГНОЗЫ С ИИ (DeepSeek V4) - NBA и NHL
- Реальная статистика из ESPN API (с заголовками браузера)
- Если данных нет -> честное "нет данных"
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
# РЕАЛЬНАЯ СТАТИСТИКА ИЗ ESPN API (с заголовками браузера)
# ============================================================

def get_nba_stats_from_espn(team_name: str) -> Optional[Dict]:
    """Получает статистику команды из ESPN API с правильными заголовками (обходит 403)"""
    
    # Маппинг названий команд для ESPN
    team_slugs = {
        "Los Angeles Lakers": "lal",
        "Boston Celtics": "bos",
        "Golden State Warriors": "gs",
        "San Antonio Spurs": "sa",
        "Oklahoma City Thunder": "okc",
        "New York Knicks": "ny",
        "Denver Nuggets": "den",
        "Miami Heat": "mia",
        "Philadelphia 76ers": "phi",
        "Chicago Bulls": "chi",
        "Milwaukee Bucks": "mil",
        "Cleveland Cavaliers": "cle",
        "Houston Rockets": "hou",
        "Phoenix Suns": "phx",
        "Dallas Mavericks": "dal",
        "LA Clippers": "lac",
        "Detroit Pistons": "det",
        "Minnesota Timberwolves": "min",
        "Memphis Grizzlies": "mem",
        "Atlanta Hawks": "atl",
        "Toronto Raptors": "tor",
        "Portland Trail Blazers": "por",
        "Sacramento Kings": "sac"
    }
    
    slug = team_slugs.get(team_name)
    if not slug:
        return None
    
    # КРИТИЧЕСКИ ВАЖНО: заголовки как в браузере
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.espn.com/",
        "Origin": "https://www.espn.com",
        "Connection": "keep-alive"
    }
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{slug}/statistics"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 403:
            print(f"    ⚠️ ESPN блокирует запрос для {team_name} (403). Будут использованы данные из Odds API.")
            return None
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        splits = data.get('splits', {})
        
        # Находим сезонную статистику
        season_stats = None
        for split_type in splits:
            if split_type.get('type') == 'season':
                season_stats = split_type.get('stats', [])
                break
        
        if not season_stats:
            return None
        
        # Преобразуем в словарь
        stats_dict = {}
        for stat in season_stats:
            name = stat.get('name')
            value = stat.get('value')
            if name and value is not None:
                stats_dict[name] = value
        
        ppg = stats_dict.get('avgPoints', 0)
        opp_ppg = stats_dict.get('avgPointsAllowed', 0)
        home_win_pct = stats_dict.get('homeWinPercent', 0) * 100
        away_win_pct = stats_dict.get('awayWinPercent', 0) * 100
        
        # Получаем расписание для формы и серии
        schedule_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{slug}/schedule"
        schedule_resp = requests.get(schedule_url, headers=headers, timeout=10)
        
        form = "нет данных"
        streak = "нет данных"
        
        if schedule_resp.status_code == 200:
            schedule_data = schedule_resp.json()
            events = schedule_data.get('events', [])
            last_10 = events[:10]
            wins = 0
            losses = 0
            
            for event in last_10:
                competitions = event.get('competitions', [])
                if competitions:
                    competitors = competitions[0].get('competitors', [])
                    for comp in competitors:
                        if comp.get('team', {}).get('slug') == slug:
                            if comp.get('winner') == True:
                                wins += 1
                            else:
                                losses += 1
                            break
            
            total_games = wins + losses
            if total_games > 0:
                form = f"{wins}-{losses}"
                if wins > losses:
                    streak = f"W{wins}"
                elif losses > wins:
                    streak = f"L{losses}"
                else:
                    streak = "N/A"
        
        # Возвращаем статистику (числа или "нет данных")
        return {
            "ppg": round(ppg, 1) if ppg > 0 else "нет данных",
            "opp_ppg": round(opp_ppg, 1) if opp_ppg > 0 else "нет данных",
            "home_win_pct": round(home_win_pct) if home_win_pct > 0 else "нет данных",
            "away_win_pct": round(away_win_pct) if away_win_pct > 0 else "нет данных",
            "form": form,
            "streak": streak,
            "source": "ESPN API"
        }
        
    except Exception as e:
        print(f"    ESPN ошибка для {team_name}: {e}")
        return None

def get_team_stats_from_odds_api(team_name: str, all_completed_games: List[Dict]) -> Optional[Dict]:
    """Рассчитывает статистику из завершённых матчей The Odds API (резерв)"""
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
    
    if len(last_10) < 3:
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
    """Загружает статистику из ESPN (NBA) или The Odds API (NHL)"""
    
    if league == "nba":
        # Пробуем ESPN API
        stats = get_nba_stats_from_espn(team_name)
        if stats:
            return stats
        
        # Пробуем рассчитать из завершённых матчей The Odds API
        stats = get_team_stats_from_odds_api(team_name, all_completed_games)
        if stats:
            return stats
    
    elif league == "nhl":
        # Для NHL пробуем рассчитать из завершённых матчей
        stats = get_team_stats_from_odds_api(team_name, all_completed_games)
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
    return f"Последние 5 встреч: {home} победил {home_wins} раз, {away} — {away_wins} раз. Средний тотал: {avg_total}"

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

{home} (дома): PPG {stats['home_ppg']}, побед дома {stats['home_win_pct']}%
{away} (в гостях): PPG {stats['away_ppg']}, побед в гостях {stats['away_win_pct']}%
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
    params = {"apiKey": ODDS_API_KEY, "daysFrom": 30}
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
        
        # ПОЛУЧАЕМ СТАТИСТИКУ
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
            'away_ppg': away_stats['ppg'], 'away_win_pct': away_stats['away_win_pct'],
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
        
        match = {
            "date": date_str, "time": time_str,
            "home": home, "away": away,
            "winner": winner, "prob": prob,
            "total_prediction": total_prediction,
            "bookmakers_list": ", ".join([bk.get("title", "") for bk in game.get("bookmakers", [])[:5]]),
            "ai_reasoning": f"{'🏀' if league == 'nba' else '🏒'} ПОБЕДА: {final_reason}\n\n📊 ТОТАЛ: {final_total_reason}",
            "home_ppg": home_stats['ppg'],
            "away_ppg": away_stats['ppg'],
            "home_win_pct": home_stats['home_win_pct'],
            "away_win_pct": away_stats['away_win_pct'],
            "home_form": home_stats['form'],
            "away_form": away_stats['form'],
            "home_streak": home_stats['streak'],
            "away_streak": away_stats['streak'],
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
    print(f"🚀 ЗАПУСК (реальная статистика из ESPN API с заголовками)")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not ODDS_API_KEY:
        print("❌ ODDS_API_KEY не найден")
        return
    
    update_league("nba", SPORT_NBA, "data/nba_matches.json", "data/nba_backup.json", "data/nba_history.json")
    update_league("nhl", SPORT_NHL, "data/nhl_matches.json", "data/nhl_backup.json", "data/nhl_history.json")
    
    print("\n✨ Готово")

if __name__ == "__main__":
    main()
