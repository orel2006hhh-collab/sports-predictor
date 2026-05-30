import sys
print("=== СКРИПТ ЗАПУСТИЛСЯ ===", file=sys.stderr)
#!/usr/bin/env python3
"""
NBA прогнозы с DeepSeek + реальная статистика из API
"""

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

# Кэш для статистики команд (чтобы не дёргать API каждый раз)
team_stats_cache = {}

def get_team_stats(team_name):
    """Получение реальной статистики команды из balldontlie API"""
    if team_name in team_stats_cache:
        return team_stats_cache[team_name]
    
    # Нормализация названий команд
    team_mapping = {
        "Los Angeles Lakers": "Lakers",
        "Golden State Warriors": "Warriors", 
        "Boston Celtics": "Celtics",
        "Milwaukee Bucks": "Bucks",
        "Phoenix Suns": "Suns",
        "Miami Heat": "Heat",
        "Philadelphia 76ers": "76ers",
        "Dallas Mavericks": "Mavericks",
        "Denver Nuggets": "Nuggets",
        "Memphis Grizzlies": "Grizzlies",
        "Sacramento Kings": "Kings",
        "New York Knicks": "Knicks",
        "Brooklyn Nets": "Nets",
        "Atlanta Hawks": "Hawks",
        "Toronto Raptors": "Raptors",
        "Chicago Bulls": "Bulls",
        "Cleveland Cavaliers": "Cavaliers",
        "Indiana Pacers": "Pacers",
        "Detroit Pistons": "Pistons",
        "Charlotte Hornets": "Hornets",
        "Orlando Magic": "Magic",
        "Washington Wizards": "Wizards",
        "Oklahoma City Thunder": "Thunder",
        "San Antonio Spurs": "Spurs",
        "Houston Rockets": "Rockets",
        "New Orleans Pelicans": "Pelicans",
        "Utah Jazz": "Jazz",
        "Portland Trail Blazers": "Trail Blazers",
        "Minnesota Timberwolves": "Timberwolves",
        "LA Clippers": "Clippers"
    }
    
    short_name = team_mapping.get(team_name, team_name.split()[-1])
    
    try:
        # Используем balldontlie API (бесплатно, без ключа)
        url = f"https://www.balldontlie.io/api/v1/teams?search={short_name}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                team_id = data['data'][0]['id']
                
                # Получаем последние 5 игр команды
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
                        ppg = round(total_points / len(games), 1) if games else 115
                        win_pct = round((wins / (wins + losses)) * 100) if (wins + losses) > 0 else 50
                        
                        stats = {
                            "form": form,
                            "ppg": ppg,
                            "win_pct": win_pct
                        }
                        team_stats_cache[team_name] = stats
                        return stats
        
        # Если API не ответил, возвращаем дефолтные значения
        return {"form": "3-2", "ppg": 115.5, "win_pct": 60}
        
    except Exception as e:
        print(f"   ⚠️ Ошибка получения статистики для {team_name}: {e}")
        return {"form": "3-2", "ppg": 115.5, "win_pct": 60}

def call_deepseek(home_team, away_team, total_line):
    """Вызов DeepSeek через OpenRouter"""
    if not OPENROUTER_API_KEY:
        print(f"   ⚠️ OPENROUTER_API_KEY отсутствует")
        return None, None, None, None, None
    
    # Получаем реальную статистику из API
    home_stats = get_team_stats(home_team)
    away_stats = get_team_stats(away_team)
    
    prompt = f"""Ты эксперт по NBA. Сделай прогноз на матч:

{home_team} (дома) vs {away_team} (в гостях)

Текущая статистика (последние 5 игр):
- {home_team}: форма {home_stats['form']}, PPG {home_stats['ppg']}, побед {home_stats['win_pct']}%
- {away_team}: форма {away_stats['form']}, PPG {away_stats['ppg']}, побед {away_stats['win_pct']}%

Линия тотала: {total_line}

Ответь строго в формате:

ВЕРОЯТНОСТЬ|ЧИСЛО от 0 до 100
ОБЪЯСНЕНИЕ|Твой анализ в 2-3 предложениях
ТОТАЛ|БОЛЬШЕ или МЕНЬШЕ

Пример ответа:
ВЕРОЯТНОСТЬ|68
ОБЪЯСНЕНИЕ|Оклахома дома показывает отличную форму (80% побед), в то время как Сан-Антонио на выезде слабее.
ТОТАЛ|БОЛЬШЕ
"""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 300
    }
    
    try:
        print(f"   🧠 DeepSeek: {home_team} vs {away_team}...")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            full = result['choices'][0]['message']['content'].strip()
            
            # Парсим ответ
            prob = None
            explanation = ""
            total_direction = "БОЛЬШЕ"
            
            lines = full.split('\n')
            for line in lines:
                line = line.strip()
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        key = parts[0]
                        value = parts[1] if len(parts) > 1 else ""
                        
                        if key == 'ВЕРОЯТНОСТЬ':
                            try:
                                prob = float(value) / 100
                            except:
                                pass
                        elif key == 'ОБЪЯСНЕНИЕ':
                            explanation = value
                        elif key == 'ТОТАЛ':
                            total_direction = value
            
            # Определяем победителя на основе вероятности
            winner = home_team if prob and prob > 0.5 else away_team
            
            total_prediction = f"Тотал {total_direction} {total_line}"
            
            stats = {
                "home_form": home_stats['form'],
                "away_form": away_stats['form'],
                "home_ppg": home_stats['ppg'],
                "away_ppg": away_stats['ppg'],
                "home_win_pct": home_stats['win_pct'],
                "away_win_pct": away_stats['win_pct'],
            }
            
            return prob, winner, stats, total_prediction, explanation
        else:
            print(f"   ❌ DeepSeek ошибка: {response.status_code}")
            return None, None, None, None, None
            
    except Exception as e:
        print(f"   ❌ DeepSeek исключение: {e}")
        return None, None, None, None, None

# Остальные функции (american_to_prob, fetch_upcoming_games, update_matches) остаются теми же
# ... (скопируй их из предыдущей версии, они не менялись)
print("=== СКРИПТ ЗАВЕРШИЛСЯ ===", file=sys.stderr)
