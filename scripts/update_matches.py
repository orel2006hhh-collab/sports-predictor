#!/usr/bin/env python3
import json
import os
import requests
from datetime import datetime, timedelta

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

SPORT = "basketball_nba"
REGIONS = "us,uk,eu"
MARKETS = "h2h,totals"
MIN_PROBABILITY = 55

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
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

def get_bookmakers_list(bookmakers):
    if not bookmakers:
        return "Нет данных"
    names = [bk.get("title", "") for bk in bookmakers[:5] if bk.get("title")]
    return ", ".join(names) if names else "Букмекеры"

def get_total_line(bookmakers):
    for bk in bookmakers:
        for market in bk.get("markets", []):
            if market["key"] == "totals":
                for outcome in market["outcomes"]:
                    if outcome.get("point"):
                        return outcome["point"]
    return 225.5

def get_team_stats_from_api(team_name):
    """Получает статистику команды из balldontlie API (форма, PPG)"""
    team_mapping = {
        "Oklahoma City Thunder": "Thunder",
        "San Antonio Spurs": "Spurs",
        "New York Knicks": "Knicks",
        "Los Angeles Lakers": "Lakers",
        "Golden State Warriors": "Warriors",
        "Boston Celtics": "Celtics",
        "Miami Heat": "Heat",
        "Milwaukee Bucks": "Bucks",
        "Denver Nuggets": "Nuggets",
        "Phoenix Suns": "Suns",
    }
    
    short_name = team_mapping.get(team_name, team_name.split()[-1])
    
    try:
        url = f"https://www.balldontlie.io/api/v1/teams?search={short_name}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                team_id = data['data'][0]['id']
                games_url = f"https://www.balldontlie.io/api/v1/games?team_ids[]={team_id}&per_page=5&seasons[]=2024"
                games_response = requests.get(games_url, timeout=5)
                
                if games_response.status_code == 200:
                    games_data = games_response.json()
                    games = games_data.get('data', [])
                    
                    if games:
                        wins = 0
                        losses = 0
                        total_points = 0
                        
                        for game in games:
                            if game['home_team']['id'] == team_id:
                                points = game['home_team_score']
                                opp_points = game['visitor_team_score']
                            else:
                                points = game['visitor_team_score']
                                opp_points = game['home_team_score']
                            
                            total_points += points
                            if points > opp_points:
                                wins += 1
                            else:
                                losses += 1
                        
                        form = f"{wins}-{losses}"
                        ppg = round(total_points / len(games), 1)
                        win_pct = round((wins / (wins + losses)) * 100)
                        
                        return {"form": form, "ppg": ppg, "win_pct": win_pct}
        
        return {"form": "3-2", "ppg": 115.5, "win_pct": 60}
        
    except Exception as e:
        print(f"   Ошибка статистики для {team_name}: {e}")
        return {"form": "3-2", "ppg": 115.5, "win_pct": 60}

def call_deepseek(home_team, away_team, total_line, home_stats, away_stats):
    """Отправляет данные в DeepSeek и получает прогноз"""
    if not OPENROUTER_API_KEY:
        return None, None, None, None
    
    prompt = f"""Ты эксперт по NBA. Сделай прогноз на матч:

{home_team} (дома) vs {away_team} (в гостях)

Статистика за последние 5 игр:
- {home_team}: форма {home_stats['form']}, PPG {home_stats['ppg']}, процент побед {home_stats['win_pct']}%
- {away_team}: форма {away_stats['form']}, PPG {away_stats['ppg']}, процент побед {away_stats['win_pct']}%

Линия тотала: {total_line}

Ответь строго в формате (ничего лишнего):
ВЕРОЯТНОСТЬ|ЧИСЛО от 0 до 100
ОБЪЯСНЕНИЕ|Твой анализ в 2-3 предложениях
ТОТАЛ|БОЛЬШЕ или МЕНЬШЕ

Пример ответа:
ВЕРОЯТНОСТЬ|68
ОБЪЯСНЕНИЕ|Оклахома дома показывает отличную форму, в то время как Сан-Антонио на выезде слабее.
ТОТАЛ|БОЛЬШЕ"""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 300
    }
    
    try:
        print(f"   🧠 Запрос к DeepSeek...")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"   📝 Ответ DeepSeek получен")
            
            prob = None
            explanation = ""
            total_dir = "БОЛЬШЕ"
            
            for line in content.split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key == 'ВЕРОЯТНОСТЬ':
                            try:
                                prob = float(value)
                            except:
                                pass
                        elif key == 'ОБЪЯСНЕНИЕ':
                            explanation = value
                        elif key == 'ТОТАЛ':
                            total_dir = value
            
            if prob is None:
                prob = 50
            
            winner = home_team if prob > 50 else away_team
            total_pred = f"Тотал {total_dir} {total_line}"
            
            return prob, winner, total_pred, explanation
        else:
            print(f"   ❌ DeepSeek ошибка: {response.status_code}")
            return None, None, None, None
    except Exception as e:
        print(f"   ❌ DeepSeek исключение: {e}")
        return None, None, None, None

def update_matches():
    print("=== ЗАПУСК ОБНОВЛЕНИЯ ===")
    print("Получаем матчи...")
    
    games = fetch_upcoming_games()
    if not games:
        print("Нет данных от API")
        return
    
    matches = []
    
    for game in games:
        home = game.get("home_team")
        away = game.get("away_team")
        if not home or not away:
            continue
        
        print(f"\n📋 {home} vs {away}")
        
        # Получаем статистику команд
        print("   Получаем статистику...")
        home_stats = get_team_stats_from_api(home)
        away_stats = get_team_stats_from_api(away)
        print(f"   {home}: форма {home_stats['form']}, PPG {home_stats['ppg']}")
        print(f"   {away}: форма {away_stats['form']}, PPG {away_stats['ppg']}")
        
        commence = game.get("commence_time")
        if commence:
            dt = datetime.fromisoformat(commence.replace("Z", "+00:00")) + timedelta(hours=3)
            date_str = dt.strftime("%d.%m.%Y")
            time_str = dt.strftime("%H:%M")
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "04:30"
        
        bookmakers_list = get_bookmakers_list(game.get("bookmakers", []))
        total_line = get_total_line(game.get("bookmakers", []))
        
        # Получаем коэффициенты
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
        
        # Букмекерская вероятность (запасной вариант)
        home_prob_bm = american_to_prob(home_odds)
        away_prob_bm = american_to_prob(away_odds)
        total_prob = home_prob_bm + away_prob_bm
        home_prob_bm = home_prob_bm / total_prob * 100
        away_prob_bm = away_prob_bm / total_prob * 100
        
        # Запрашиваем прогноз у DeepSeek
        ai_prob, ai_winner, ai_total, ai_explanation = call_deepseek(
            home, away, total_line, home_stats, away_stats
        )
        
        # Используем DeepSeek, если он ответил
        if ai_prob is not None:
            prob = ai_prob
            winner = ai_winner
            total_prediction = ai_total
            reasoning = ai_explanation
            print(f"   🎯 DeepSeek прогноз: {winner} ({prob}%)")
        else:
            prob = round(max(home_prob_bm, away_prob_bm))
            winner = home if home_prob_bm > away_prob_bm else away
            total_prediction = f"Тотал БОЛЬШЕ {total_line}"
            reasoning = f"Прогноз на основе коэффициентов: {winner} ({prob}%)"
            print(f"   ⚠️ Локальный прогноз: {winner} ({prob}%)")
        
        if prob < MIN_PROBABILITY:
            print(f"   ⏭️ Пропущен (вероятность {prob}% < {MIN_PROBABILITY}%)")
            continue
        
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
            "home_form": home_stats['form'],
            "away_form": away_stats['form'],
            "home_ppg": home_stats['ppg'],
            "away_ppg": away_stats['ppg'],
            "home_win_pct": home_stats['win_pct'],
            "away_win_pct": away_stats['win_pct'],
            "home_odds": round(1 / (home_prob_bm / 100), 2),
            "away_odds": round(1 / (away_prob_bm / 100), 2)
        }
        matches.append(match)
        print(f"   ✅ Добавлен в прогнозы")
    
    # Сохраняем результаты
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено {len(matches)} матчей в data/matches.json")

def main():
    update_matches()
    print("=== ГОТОВО ===")

if __name__ == "__main__":
    main()
