#!/usr/bin/env python3
"""
ПРОГНОЗЫ С DeepSeek (реальная статистика из интернета + травмы)
- The Odds API: список предстоящих матчей + реальные тоталы
- nbainjuries: информация о травмах игроков
- DeepSeek с web_search=True: самостоятельно ищет актуальную статистику
"""

import json
import os
import re
import requests
from datetime import datetime, timedelta, timezone

# ============================================================
# НАСТРОЙКИ
# ============================================================

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

SPORT = "basketball_nba"
REGIONS = "us,uk,eu"
MARKETS = "h2h,totals"

# Минимальная вероятность для отображения прогноза
MIN_PROBABILITY = 55

# ============================================================
# ФУНКЦИЯ ПОЛУЧЕНИЯ ТРАВМ
# ============================================================

def get_injuries_for_team(team_name: str, game_date: datetime) -> str:
    """
    Получает список травмированных игроков для конкретной команды на дату игры.
    Возвращает строку с именами и статусом травмы.
    """
    try:
        from nbainjuries import injury
        
        # Устанавливаем время отчёта на 5 PM ET (21:00 UTC)
        report_datetime = game_date.replace(hour=21, minute=0, second=0, microsecond=0)
        if report_datetime > datetime.now(timezone.utc):
            report_datetime = datetime.now(timezone.utc)
        
        injury_data = injury.get_reportdata(report_datetime, return_df=False)
        
        # Маппинг названий команд NBA для nbainjuries
        team_mapping = {
            "Oklahoma City Thunder": "Thunder",
            "San Antonio Spurs": "Spurs",
            "New York Knicks": "Knicks",
            "Los Angeles Lakers": "Lakers",
            "Golden State Warriors": "Warriors",
            "Boston Celtics": "Celtics",
            "Miami Heat": "Heat",
            "Chicago Bulls": "Bulls",
            "Dallas Mavericks": "Mavericks",
            "Denver Nuggets": "Nuggets",
            "Phoenix Suns": "Suns",
            "Philadelphia 76ers": "76ers",
            "Milwaukee Bucks": "Bucks",
            "Brooklyn Nets": "Nets",
            "Toronto Raptors": "Raptors",
            "Atlanta Hawks": "Hawks",
            "Cleveland Cavaliers": "Cavaliers",
            "Indiana Pacers": "Pacers",
            "Detroit Pistons": "Pistons",
            "Charlotte Hornets": "Hornets",
            "Orlando Magic": "Magic",
            "Washington Wizards": "Wizards",
            "Memphis Grizzlies": "Grizzlies",
            "New Orleans Pelicans": "Pelicans",
            "Utah Jazz": "Jazz",
            "Sacramento Kings": "Kings",
            "Portland Trail Blazers": "Trail Blazers",
            "Minnesota Timberwolves": "Timberwolves",
            "Houston Rockets": "Rockets",
            "LA Clippers": "Clippers",
        }
        
        short_name = team_mapping.get(team_name, team_name)
        
        team_injuries = []
        for record in injury_data:
            if record.get('Team') == short_name and record.get('Current Status') != 'Available':
                player = record.get('Player Name', 'Игрок')
                status = record.get('Current Status', 'травмирован')
                team_injuries.append(f"{player} ({status})")
        
        if team_injuries:
            return ", ".join(team_injuries[:3])  # максимум 3 травмы
        else:
            return "✅ Все игроки в строю"
    except Exception as e:
        print(f"   ⚠️ Ошибка при получении травм для {team_name}: {e}")
        return "Нет данных о травмах"

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

def get_total_line(bookmakers):
    """Получает среднюю линию тотала от букмекеров"""
    total_points = []
    for bk in bookmakers:
        for market in bk.get("markets", []):
            if market["key"] == "totals":
                for outcome in market["outcomes"]:
                    point = outcome.get("point")
                    if point and point not in total_points:
                        total_points.append(float(point))
                break
    
    if total_points:
        avg_total = round(sum(total_points) / len(total_points), 1)
        return avg_total
    return 225.5

def call_deepseek(home_team: str, away_team: str, total_line: float, home_injuries: str, away_injuries: str):
    """
    Отправляет запрос к DeepSeek с включенным веб-поиском и информацией о травмах.
    """
    if not OPENROUTER_API_KEY:
        return None, None, None, None, None
    
    prompt = f"""Ты эксперт по NBA. Сделай подробный прогноз на матч:

{home_team} vs {away_team}

Линия тотала: {total_line}

**ИНФОРМАЦИЯ О ТРАВМАХ**:
- {home_team}: {home_injuries}
- {away_team}: {away_injuries}

Найди в интернете актуальную статистику за последние 5-7 дней:
1. Форму команд (последние 5 игр: победы/поражения)
2. Средние очки за игру (PPG) за последние 5 матчей
3. Текущую серию (сколько побед или поражений подряд)
4. Процент побед за последние 5 матчей

**ВАЖНО**: Обязательно учти информацию о травмах в своём анализе! Отсутствие ключевого игрока (лидера команды) может кардинально изменить исход матча. Если травмирован важный игрок, это должно быть отражено в объяснении.

Верни ответ строго в указанном формате:

ФОРМА|{home_team}|ЧИСЛО ПОБЕД-ЧИСЛО ПОРАЖЕНИЙ
ФОРМА|{away_team}|ЧИСЛО ПОБЕД-ЧИСЛО ПОРАЖЕНИЙ
PPG|{home_team}|ЧИСЛО
PPG|{away_team}|ЧИСЛО
СТРЕЙК|{home_team}|+ЧИСЛО или -ЧИСЛО
СТРЕЙК|{away_team}|+ЧИСЛО или -ЧИСЛО
ПРОЦЕНТ|{home_team}|ЧИСЛО
ПРОЦЕНТ|{away_team}|ЧИСЛО
ВЕРОЯТНОСТЬ|ЧИСЛО 0-100|{home_team} или {away_team}
ОБЪЯСНЕНИЕ|Твой развёрнутый анализ (3-5 предложений) почему победит именно эта команда, учитывая форму, травмы и другие факторы
ТОТАЛ|БОЛЬШЕ или МЕНЬШЕ|Развёрнутое объяснение (2-3 предложения) почему такой тотал

ВАЖНО: В строках ВЕРОЯТНОСТЬ и ТОТАЛ обязательно указывай направление.
"""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 800,
        "web_search": True
    }
    
    try:
        print(f"🧠 DeepSeek (с веб-поиском + травмы): {home_team} – {away_team}...")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            full = result['choices'][0]['message']['content'].strip()
            print(f"   DeepSeek ответ получил, парсим...")
            
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
                "explanation": "",
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
                
                elif line.startswith('ОБЪЯСНЕНИЕ|'):
                    parts = line.split('|', 1)
                    if len(parts) >= 2:
                        result_dict["explanation"] = parts[1].strip()
                
                elif line.startswith('ТОТАЛ|'):
                    parts = line.split('|')
                    if len(parts) >= 2:
                        result_dict["total_direction"] = parts[1].strip()
                        if len(parts) >= 3:
                            result_dict["total_reason"] = parts[2].strip()
            
            if result_dict["home_form"] is None and result_dict["away_form"] is None:
                form_lines = [l for l in lines if l.startswith('ФОРМА|')]
                if len(form_lines) >= 2:
                    first = form_lines[0].split('|')
                    second = form_lines[1].split('|')
                    if len(first) >= 3 and len(second) >= 3:
                        result_dict["home_form"] = first[2].strip()
                        result_dict["away_form"] = second[2].strip()
            
            total_prediction = f"Тотал {result_dict['total_direction']} {total_line}"
            
            # Добавляем информацию о травмах в объяснение, если DeepSeek не упомянул
            full_explanation = result_dict["explanation"]
            if home_injuries != "✅ Все игроки в строю" and "травм" not in full_explanation.lower():
                full_explanation += f" У {home_team} травмы: {home_injuries}."
            if away_injuries != "✅ Все игроки в строю" and "травм" not in full_explanation.lower():
                full_explanation += f" У {away_team} травмы: {away_injuries}."
            
            if result_dict["total_reason"]:
                full_explanation += f" По тоталу: {result_dict['total_reason']}"
            
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
            
            print(f"   Распарсено: форма {result_dict['home_form']} vs {result_dict['away_form']}, тотал: {result_dict['total_direction']} {total_line}")
            
            return result_dict["prob"], result_dict["winner"], stats, total_prediction, full_explanation
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
    print("   DeepSeek с веб-поиском + анализ травм")
    print("   Тоталы берутся из The Odds API")
    
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
            game_date = dt
        else:
            date_str = datetime.now().strftime("%d.%m.%Y")
            time_str = "04:30 МСК"
            game_date = datetime.now()
        
        bookmakers_list = get_bookmakers_list(game.get("bookmakers", []))
        total_line = get_total_line(game.get("bookmakers", []))
        
        # Получаем травмы для обеих команд
        print(f"   🤕 Проверяем травмы: {home} vs {away}")
        home_injuries = get_injuries_for_team(home, game_date)
        away_injuries = get_injuries_for_team(away, game_date)
        print(f"      {home}: {home_injuries[:80]}...")
        print(f"      {away}: {away_injuries[:80]}...")
        
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
            if home_odds != 2.0 and away_odds != 2.0:
                break
        
        home_prob = american_to_prob(home_odds)
        away_prob = american_to_prob(away_odds)
        total = home_prob + away_prob
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100
        
        local_winner = home if home_prob > away_prob else away
        local_prob = round(max(home_prob, away_prob))
        
        # Запрашиваем DeepSeek
        ai_prob, ai_winner, ai_stats, ai_total_pred, ai_explanation = call_deepseek(
            home, away, total_line, home_injuries, away_injuries
        )
        
        if ai_prob is not None and ai_prob > 0:
            prob = round(ai_prob * 100)
            winner = ai_winner
            source = "DeepSeek AI (актуальная статистика + травмы)"
            total_prediction = ai_total_pred or f"Тотал БОЛЬШЕ {total_line}"
            
            home_form = ai_stats.get("home_form")
            away_form = ai_stats.get("away_form")
            home_ppg = ai_stats.get("home_ppg")
            away_ppg = ai_stats.get("away_ppg")
            home_streak = ai_stats.get("home_streak")
            away_streak = ai_stats.get("away_streak")
            home_win_pct = ai_stats.get("home_win_pct")
            away_win_pct = ai_stats.get("away_win_pct")
            
            reasoning = ai_explanation
        else:
            prob = local_prob
            winner = local_winner
            source = "Локальный расчёт (коэффициенты)"
            total_prediction = f"Тотал БОЛЬШЕ {total_line}"
            home_form = away_form = None
            home_ppg = away_ppg = None
            home_streak = away_streak = None
            home_win_pct = away_win_pct = None
            reasoning = f"Прогноз на основе коэффициентов букмекеров: {winner} побеждает с вероятностью {prob}%."
        
        if prob < MIN_PROBABILITY:
            print(f"⏭️ Пропущен ({prob}% < {MIN_PROBABILITY}%): {home} – {away}")
            continue
        
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
            "total_line": total_line,
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
            "away_odds": away_odds_decimal,
            "home_injuries": home_injuries,
            "away_injuries": away_injuries
        }
        matches.append(match)
        backup.append({
            "date": date_str,
            "home": home,
            "away": away,
            "prediction": winner,
            "prob": prob,
            "total_line": total_line
        })
        
        print(f"✅ {home} – {away}: {winner} ({prob}%) | тотал {total_line} | форма {home_form or '?'} vs {away_form or '?'}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    with open("data/predictions_backup.json", "w", encoding="utf-8") as f:
        json.dump({"predictions": backup}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено {len(matches)} матчей")

def main():
    print(f"🚀 ЗАПУСК (DeepSeek + веб-поиск + травмы)")
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
