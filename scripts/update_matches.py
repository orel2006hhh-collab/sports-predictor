#!/usr/bin/env python3
"""
Парсер реальных данных с ESPN API для НБА (плей-офф)
Правильная конвертация ET → МСК с учётом перехода через полночь
"""

import json
import requests
import os
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
}

# ============================================================
# БАЗА ДАННЫХ
# ============================================================

TEAM_STATS = {
    'Detroit Pistons': {'ppg': 112.5, 'opp_ppg': 109.2, 'win_pct': 73},
    'Cleveland Cavaliers': {'ppg': 115.2, 'opp_ppg': 110.8, 'win_pct': 63},
    'Oklahoma City Thunder': {'ppg': 119.2, 'opp_ppg': 110.5, 'win_pct': 78},
    'Los Angeles Lakers': {'ppg': 116.8, 'opp_ppg': 112.5, 'win_pct': 65},
    'New York Knicks': {'ppg': 114.5, 'opp_ppg': 111.2, 'win_pct': 68},
    'Philadelphia 76ers': {'ppg': 113.8, 'opp_ppg': 112.1, 'win_pct': 60},
    'San Antonio Spurs': {'ppg': 115.5, 'opp_ppg': 111.8, 'win_pct': 66},
    'Minnesota Timberwolves': {'ppg': 113.2, 'opp_ppg': 110.5, 'win_pct': 64}
}

TEAM_FORM = {
    'Detroit Pistons': {'last_10': '8-2', 'streak': 'W3'},
    'Cleveland Cavaliers': {'last_10': '6-4', 'streak': 'L1'},
    'Oklahoma City Thunder': {'last_10': '7-3', 'streak': 'W1'},
    'Los Angeles Lakers': {'last_10': '7-3', 'streak': 'W3'},
    'New York Knicks': {'last_10': '8-2', 'streak': 'W2'},
    'Philadelphia 76ers': {'last_10': '6-4', 'streak': 'W1'},
    'San Antonio Spurs': {'last_10': '9-1', 'streak': 'W4'},
    'Minnesota Timberwolves': {'last_10': '7-3', 'streak': 'W2'}
}

H2H_DATA = {
    ('Detroit Pistons', 'Cleveland Cavaliers'): '2-2',
    ('Oklahoma City Thunder', 'Los Angeles Lakers'): '3-1',
    ('New York Knicks', 'Philadelphia 76ers'): '2-2',
    ('San Antonio Spurs', 'Minnesota Timberwolves'): '1-1'
}

INJURIES = {
    'Los Angeles Lakers': [
        {'name': 'Luka Doncic', 'status': 'Out', 'impact': -12},
        {'name': 'LeBron James', 'status': 'Questionable', 'impact': -8}
    ],
    'Oklahoma City Thunder': [
        {'name': 'Jalen Williams', 'status': 'Out', 'impact': -6},
        {'name': 'Chet Holmgren', 'status': 'Out', 'impact': -7}
    ],
    'New York Knicks': [{'name': 'Jeremy Sochan', 'status': 'Questionable', 'impact': -4}],
}

# ============================================================
# ПРАВИЛЬНАЯ КОНВЕРТАЦИЯ ВРЕМЕНИ ET → МСК
# ============================================================

def convert_et_to_msk(et_date, et_time_str):
    """
    Конвертирует дату и время из Eastern Time в Московское
    ET = UTC-4 (летом), MSK = UTC+3 → разница +7 часов
    """
    try:
        # Парсим ET время (формат: "7:00 PM" или "19:00")
        time_str = et_time_str.lower().strip()
        is_pm = 'pm' in time_str or 'p.m.' in time_str
        is_am = 'am' in time_str or 'a.m.' in time_str
        
        import re
        match = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
        else:
            match = re.search(r'(\d{1,2})\s*(?:am|pm)?', time_str)
            if match:
                hour = int(match.group(1))
                minute = 0
            else:
                return et_date, '19:00 МСК'
        
        # Конвертируем в 24-часовой формат
        if is_pm and hour != 12:
            hour += 12
        if is_am and hour == 12:
            hour = 0
        
        # Создаем datetime объект в ET
        et_datetime = datetime.strptime(et_date, '%Y-%m-%d')
        et_datetime = et_datetime.replace(hour=hour, minute=minute)
        
        # Добавляем 7 часов для перевода в МСК
        msk_datetime = et_datetime + timedelta(hours=7)
        
        # Форматируем результат
        msk_date = msk_datetime.strftime('%d.%m.%Y')
        
        # Форматируем время в 12-часовой формат с AM/PM для наглядности
        msk_hour = msk_datetime.hour
        msk_minute = msk_datetime.minute
        
        if msk_hour == 0:
            time_12h = f'12:{msk_minute:02d} AM'
        elif msk_hour < 12:
            time_12h = f'{msk_hour}:{msk_minute:02d} AM'
        elif msk_hour == 12:
            time_12h = f'12:{msk_minute:02d} PM'
        else:
            time_12h = f'{msk_hour-12}:{msk_minute:02d} PM'
        
        return msk_date, f"{time_12h} МСК"
        
    except Exception as e:
        logger.warning(f"Ошибка конвертации времени: {e}")
        return et_date, '19:00 МСК'

def get_future_matches():
    """
    Получает будущие матчи из ESPN API на ближайшие 7 дней
    """
    games = []
    today = datetime.now()
    
    for offset in range(0, 8):
        check_date = today + timedelta(days=offset)
        date_str = check_date.strftime('%Y%m%d')
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
        
        try:
            logger.info(f"Запрос матчей на {check_date.strftime('%d.%m.%Y')}...")
            response = requests.get(url, headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                
                for event in events:
                    competition = event.get('competitions', [{}])[0]
                    competitors = competition.get('competitors', [])
                    
                    home_team = None
                    away_team = None
                    
                    for comp in competitors:
                        team = comp.get('team', {})
                        if comp.get('homeAway') == 'home':
                            home_team = team.get('displayName', 'Unknown')
                        else:
                            away_team = team.get('displayName', 'Unknown')
                    
                    if home_team and away_team:
                        # Проверяем статус матча
                        status = competition.get('status', {}).get('type', {}).get('description', '')
                        
                        # Пропускаем завершённые матчи
                        if status == 'Final':
                            continue
                        
                        # Получаем дату и время матча в ET
                        event_date = competition.get('date', '')
                        event_time = competition.get('time', {}).get('displayValue', '19:00 PM')
                        
                        if event_date:
                            # Парсим дату из ISO формата
                            iso_date = event_date.split('T')[0]
                            
                            # Конвертируем ET → МСК
                            msk_date, msk_time = convert_et_to_msk(iso_date, event_time)
                            
                            games.append({
                                'home': home_team,
                                'away': away_team,
                                'date': msk_date,
                                'time': msk_time,
                                'status': status
                            })
                            logger.info(f"  Матч: {home_team} vs {away_team} | {msk_date} {msk_time}")
                            
        except Exception as e:
            logger.warning(f"Ошибка запроса для {date_str}: {e}")
    
    # Удаляем дубликаты
    unique_games = []
    seen = set()
    for game in games:
        key = f"{game['home']}_{game['away']}_{game['date']}"
        if key not in seen:
            seen.add(key)
            unique_games.append(game)
    
    # Сортируем по дате
    unique_games.sort(key=lambda x: x['date'])
    
    return unique_games

def get_team_stats(team_name):
    return TEAM_STATS.get(team_name, {'ppg': 110, 'opp_ppg': 108, 'win_pct': 50})

def get_h2h(team1, team2):
    return H2H_DATA.get((team1, team2), '0-0')

def get_form(team_name):
    return TEAM_FORM.get(team_name, {'last_10': '5-5', 'streak': 'N/A'})

def get_injuries_impact(team_name):
    impact = 0
    injuries_list = []
    if team_name in INJURIES:
        for player in INJURIES[team_name]:
            impact += player.get('impact', 0)
            injuries_list.append(f"{player['name']} ({player['status']})")
    return impact, injuries_list

def calculate_win_probability(home, away, home_stats, away_stats, h2h, home_injury_impact, away_injury_impact):
    base = 50
    reasons = []
    
    home_ppg = home_stats.get('ppg', 0)
    away_ppg = away_stats.get('ppg', 0)
    if home_ppg > 0 and away_ppg > 0:
        ppg_effect = (home_ppg - away_ppg) * 0.4
        base += ppg_effect
        reasons.append(f"PPG {ppg_effect:+.1f}")
    
    home_opp = home_stats.get('opp_ppg', 0)
    away_opp = away_stats.get('opp_ppg', 0)
    if home_opp > 0 and away_opp > 0:
        def_effect = (away_opp - home_opp) * 0.3
        base += def_effect
        reasons.append(f"Защита {def_effect:+.1f}")
    
    home_pct = home_stats.get('win_pct', 50)
    away_pct = away_stats.get('win_pct', 50)
    pct_effect = (home_pct - away_pct) / 2.5
    base += pct_effect
    reasons.append(f"Win% {pct_effect:+.1f}")
    
    if h2h != '0-0':
        parts = h2h.split('-')
        home_h2h = int(parts[0])
        away_h2h = int(parts[1])
        total = home_h2h + away_h2h
        if total > 0:
            h2h_effect = (home_h2h / total - 0.5) * 10
            base += h2h_effect
            reasons.append(f"H2H {h2h_effect:+.1f}")
    
    base += home_injury_impact
    base -= away_injury_impact
    if home_injury_impact != 0:
        reasons.append(f"Травмы дома {home_injury_impact:+.1f}")
    if away_injury_impact != 0:
        reasons.append(f"Травмы гостей {-away_injury_impact:+.1f}")
    
    base += 4
    reasons.append(f"Дом +4")
    
    prob = max(35, min(85, base))
    logger.info(f"    🎯 {home}: {prob:.1f}%")
    
    return round(prob, 1)

def calculate_total_prediction(home_stats, away_stats):
    home_ppg = home_stats.get('ppg', 0)
    away_ppg = away_stats.get('ppg', 0)
    home_opp = home_stats.get('opp_ppg', 0)
    away_opp = away_stats.get('opp_ppg', 0)
    
    if home_ppg == 0 or away_ppg == 0:
        return None
    
    expected_total = (home_ppg + away_opp) / 2 + (away_ppg + home_opp) / 2
    std_dev = 11.5
    lines = [210.5, 215.5, 220.5, 225.5, 230.5]
    
    from math import erf
    best = None
    best_prob = 0
    
    for line in lines:
        z = (expected_total - line) / std_dev
        prob_over = 0.5 * (1 + erf(z / (2 ** 0.5)))
        prob_over = round(prob_over * 100)
        prob_under = 100 - prob_over
        
        if prob_over > 73 and prob_over > best_prob:
            best_prob = prob_over
            best = f"Тотал БОЛЬШЕ {line} (вер. {prob_over}%)"
        
        if prob_under > 73 and prob_under > best_prob:
            best_prob = prob_under
            best = f"Тотал МЕНЬШЕ {line} (вер. {prob_under}%)"
    
    if best:
        logger.info(f"    🎯 {best}")
    else:
        logger.info(f"    ⚠️ Нет тоталов >73%")
    
    return best

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ НБА")
    logger.info("   Конвертация ET → МСК с правильной датой")
    logger.info("=" * 60)
    
    os.makedirs('data', exist_ok=True)
    
    games = get_future_matches()
    
    if not games:
        logger.warning("Матчи не найдены")
        output = {
            "lastUpdated": datetime.now().isoformat(),
            "matches": [],
            "dateInfo": {
                "today": datetime.now().strftime('%d.%m.%Y'),
                "tomorrow": (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
            }
        }
        with open('data/matches.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        return
    
    all_matches = []
    
    for game in games:
        home = game['home']
        away = game['away']
        
        logger.info(f"\n📋 {home} vs {away} | {game['date']} {game['time']}")
        
        home_stats = get_team_stats(home)
        away_stats = get_team_stats(away)
        
        h2h = get_h2h(home, away)
        home_form = get_form(home)
        away_form = get_form(away)
        
        home_injury_impact, home_injuries = get_injuries_impact(home)
        away_injury_impact, away_injuries = get_injuries_impact(away)
        
        prob = calculate_win_probability(home, away, home_stats, away_stats, h2h, home_injury_impact, away_injury_impact)
        winner = home if prob >= 50 else away
        total_pred = calculate_total_prediction(home_stats, away_stats)
        
        injuries_text = ""
        if home_injuries:
            injuries_text += f"🏥 {home}: " + ", ".join(home_injuries[:2])
        if away_injuries:
            injuries_text += f" | 🏥 {away}: " + ", ".join(away_injuries[:2])
        if not injuries_text:
            injuries_text = "✅ Все игроки в строю"
        
        match_data = {
            'sport': 'nba',
            'home': home,
            'away': away,
            'league': 'NBA',
            'prob': prob,
            'winner': winner,
            'date': game['date'],
            'time': game['time'],
            'total_prediction': total_pred if total_pred else "Нет уверенного прогноза (>73%)",
            'data_source': 'ESPN_API',
            'h2h': h2h,
            'home_ppg': home_stats.get('ppg', 0),
            'away_ppg': away_stats.get('ppg', 0),
            'home_win_pct': home_stats.get('win_pct', 0),
            'away_win_pct': away_stats.get('win_pct', 0),
            'injuries': injuries_text,
            'home_form': home_form.get('last_10', 'N/A'),
            'away_form': away_form.get('last_10', 'N/A'),
            'home_streak': home_form.get('streak', 'N/A'),
            'away_streak': away_form.get('streak', 'N/A')
        }
        
        all_matches.append(match_data)
        logger.info(f"  ✅ {winner} победа ({prob}%)")
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": datetime.now().strftime('%d.%m.%Y'),
            "tomorrow": (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
        }
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✅ ГОТОВО! Сохранено матчей: {len(all_matches)}")

if __name__ == "__main__":
    main()
