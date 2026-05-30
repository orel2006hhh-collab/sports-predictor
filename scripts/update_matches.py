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
MIN_PROBABILITY = 0

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

def call_deepseek(home_team, away_team, total_line, home_odds, away_odds, home_stats, away_stats):
    """DeepSeek анализирует статистику, стимул и делает симуляции"""
    if not OPENROUTER_API_KEY:
        return None, None, None, None, None
    
    prompt = f"""Ты эксперт по NBA. Сделай прогноз на матч:

{home_team} (дома) vs {away_team} (гости)

**Статистика команд (последние 5 игр):**
- {home_team}: форма {home_stats['form']}, PPG {home_stats['ppg']}, % побед {home_stats['win_pct']}%
- {away_team}: форма {away_stats['form']}, PPG {away_stats['ppg']}, % побед {away_stats['win_pct']}%

**Коэффициенты букмекеров (средние):**
- Победа {home_team}: {home_odds:.2f}
- Победа {away_team}: {away_odds:.2f}
- Тотал: {total_line}

**ВАЖНО — проанализируй турнирное положение (стимул):**
Найди в интернете, в каком положении находятся команды в турнирной таблице NBA. Это плей-офф? Регулярный сезон? Команды борются за место в плей-офф? Учитывай мотивацию.

**Найди историю личных встреч (H2H):**
Найди результаты последних 3-5 личных встреч между этими командами.

**Сделай мысленную симуляцию матча 15 раз:**
Проиграй этот матч в уме 15 раз, используя статистику, коэффициенты и H2H. Запиши, сколько раз победил {home_team}, сколько раз {away_team}. А также сколько раз тотал был БОЛЬШЕ {total_line} и сколько раз МЕНЬШЕ.

**Верни ответ строго в формате (ничего лишнего):**

H2H|Краткий результат последних личных встреч (например: "Лейкерс выиграли 3 из 5")
СИМУЛЯЦИЯ_ПОБЕД_ХОЗЯЕВА|ЧИСЛО_ИЗ_15
СИМУЛЯЦИЯ_ПОБЕД_ГОСТИ|ЧИСЛО_ИЗ_15
СИМУЛЯЦИЯ_ТОТАЛ_БОЛЬШЕ|ЧИСЛО_ИЗ_15
СИМУЛЯЦИЯ_ТОТАЛ_МЕНЬШЕ|ЧИСЛО_ИЗ_15
СТИМУЛ|Краткий анализ мотивации команд (1 предложение)
ВЕРОЯТНОСТЬ|ЧИСЛО от 0 до 100
ОБЪЯСНЕНИЕ|Твой итоговый прогноз с учётом симуляции и стимула (2-3 предложения)
ТОТАЛ|БОЛЬШЕ или МЕНЬШЕ

Пример ответа:
H2H|Тандер выиграли 4 из 5 последних встреч
СИМУЛЯЦИЯ_ПОБЕД_ХОЗЯЕВА|10
СИМУЛЯЦИЯ_ПОБЕД_ГОСТИ|5
СИМУЛЯЦИЯ_ТОТАЛ_БОЛЬШЕ|11
СИМУЛЯЦИЯ_ТОТАЛ_МЕНЬШЕ|4
СТИМУЛ|Оклахома борется за 1-е место на Западе, Сан-Антонио уже вылетел из плей-офф.
ВЕРОЯТНОСТЬ|67
ОБЪЯСНЕНИЕ|Симуляция показала 10 побед Оклахомы из 15. Учитывая мотивацию и форму дома, прогноз уверенный.
ТОТАЛ|БОЛЬШЕ"""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 800,
        "web_search": True
    }
    
    try:
        print(f"   🧠 DeepSeek анализирует стимул, H2H и симулирует 15 матчей...")
        response = requests.post(url, headers=headers, json=payload, timeout=90)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"   📝 Ответ DeepSeek получен")
            
            # Парсим ответ
            h2h = ""
            sim_home = None
            sim_away = None
            sim_over = None
            sim_under = None
            stimulation = ""
            prob = None
            explanation = ""
            total_dir = "БОЛЬШЕ"
            
            for line in content.split('\n'):
                if '|' not in line:
                    continue
                parts = line.split('|')
                if len(parts) < 2:
                    continue
                key = parts[0].strip()
                value = parts[1].strip()
                
                if key == 'H2H':
                    h2h = value
                elif key == 'СИМУЛЯЦИЯ_ПОБЕД_ХОЗЯЕВА':
                    try:
                        sim_home = int(value)
                    except:
                        pass
                elif key == 'СИМУЛЯЦИЯ_ПОБЕД_ГОСТИ':
                    try:
                        sim_away = int(value)
                    except:
                        pass
                elif key == 'СИМУЛЯЦИЯ_ТОТАЛ_БОЛЬШЕ':
                    try:
                        sim_over = int(value)
                    except:
                        pass
                elif key == 'СИМУЛЯЦИЯ_ТОТАЛ_МЕНЬШЕ':
                    try:
                        sim_under = int(value)
                    except:
                        pass
                elif key == 'СТИМУЛ':
                    stimulation = value
                elif key == 'ВЕРОЯТНОСТЬ':
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
            
            # Если симуляция есть, используем её для вероятности
            if sim_home is not None and sim_away is not None:
                total_sim = sim_home + sim_away
                if total_sim > 0:
                    prob = round(sim_home / total_sim * 100)
            
            winner = home_team if prob > 50 else away_team
            total_pred = f"Тотал {total_dir} {total_line}"
            
            # Добавляем H2H, стимул и симуляцию в объяснение
            full_explanation = f"📊 Личные встречи: {h2h}\n🎯 Стимул: {stimulation}\n🎲 Симуляция 15 игр: хозяева {sim_home if sim_home else '?'} - {sim_away if sim_away else '?'} гости\n💡 {explanation}"
            
            stats = {
                "home_form": home_stats['form'],
                "away_form": away_stats['form'],
                "home_ppg": home_stats['ppg'],
                "away_ppg": away_stats['ppg'],
                "home_win_pct": home_stats['win_pct'],
                "away_win_pct": away_stats['win_pct'],
            }
            
            return prob, winner, total_pred, full_explanation, stats
        else:
            print(f"   ❌ DeepSeek ошибка: {response.status_code}")
            return None, None, None, None, None
    except Exception as e:
        print(f"   ❌ DeepSeek исключение: {e}")
        return None, None, None, None, None

def update_matches():
    print("=== ЗАПУСК ОБНОВЛЕНИЯ ===")
    print("Получаем матчи из The Odds API...")
    
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
        
        home_prob_bm = american_to_prob(home_odds)
        away_prob_bm = american_to_prob(away_odds)
        total_prob = home_prob_bm + away_prob_bm
        home_prob_bm = home_prob_bm / total_prob * 100
        away_prob_bm = away_prob_bm / total_prob * 100
        
        home_odds_decimal = round(1 / (home_prob_bm / 100), 2)
        away_odds_decimal = round(1 / (away_prob_bm / 100), 2)
        
        # DeepSeek сам найдёт статистику в интернете
        # Пока используем временные значения для статистики (DeepSeek перезапишет их своим анализом)
        temp_stats = {"form": "?", "ppg": "?", "win_pct": "?"}
        
        result = call_deepseek(home, away, total_line, home_odds_decimal, away_odds_decimal, temp_stats, temp_stats)
        
        if result[0] is not None:
            prob, winner, total_prediction, explanation, stats = result
            prob = round(prob)
            home_form = stats.get("home_form")
            away_form = stats.get("away_form")
            home_ppg = stats.get("home_ppg")
            away_ppg = stats.get("away_ppg")
            home_win_pct = stats.get("home_win_pct")
            away_win_pct = stats.get("away_win_pct")
            reasoning = explanation
            print(f"   🎯 DeepSeek прогноз: {winner} ({prob}%)")
            print(f"   📊 Форма: {home_form} vs {away_form}")
            print(f"   📊 PPG: {home_ppg} vs {away_ppg}")
        else:
            # Запасной вариант — только если DeepSeek не ответил
            prob = round(max(home_prob_bm, away_prob_bm))
            winner = home if home_prob_bm > away_prob_bm else away
            total_prediction = f"Тотал БОЛЬШЕ {total_line}"
            reasoning = f"Прогноз на основе коэффициентов: {winner} ({prob}%)"
            home_form = away_form = "данные не загружены"
            home_ppg = away_ppg = None
            home_win_pct = away_win_pct = None
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
            "home_form": home_form,
            "away_form": away_form,
            "home_ppg": home_ppg,
            "away_ppg": away_ppg,
            "home_win_pct": home_win_pct,
            "away_win_pct": away_win_pct,
            "home_odds": home_odds_decimal,
            "away_odds": away_odds_decimal
        }
        matches.append(match)
        print(f"   ✅ Добавлен в прогнозы")
    
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w", encoding="utf-8") as f:
        json.dump({"matches": matches, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено {len(matches)} матчей в data/matches.json")
    print(f"📁 Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def main():
    print("=" * 50)
    print("🚀 NBA PREDICTOR (DeepSeek + стимул + симуляции)")
    print("=" * 50)
    update_matches()
    print("\n✨ ГОТОВО!")

if __name__ == "__main__":
    main()
