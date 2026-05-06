#!/usr/bin/env python3
"""
Парсер реальных данных с ESPN API для НБА (плей-офф)
Получает будущие матчи на 7 дней вперёд с корректным временем и тоталами
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
# БАЗА ДАННЫХ КОМАНД (полная)
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
# ФУНКЦИИ
# ============================================================

def convert_time_to_msk(et_time_str):
    """
    Конвертирует время из Eastern Time (ET) в Московское (MSK)
    ET UTC-4, MSK UTC+3 → разница +7 часов
    Пример: 7:00 PM ET → 12:00 AM MSK (следующий день)
    """
    try:
        time_str = et_time_str.lower().strip()
        is_pm = 'pm' in time_str or 'p.m.' in time_str
        is_am = 'am' in time_str or 'a.m.' in time_str
        
        # Извлекаем часы и минуты
        import re
        match = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
        else:
            match = re.search(r'(\d{1,2})\s*(?:am|pm|AM|PM)?', time_str)
            if match:
                hour = int(match.group(1))
                minute = 0
            else:
                return '04:30 МСК'
        
        # Конвертируем в 24-часовой формат
        if is_pm and hour != 12:
            hour += 12
        if is_am and hour == 12:
            hour = 0
        
        # Добавляем 7 часов (ET → MSK)
        hour = hour + 7
        
        # Если перешли через сутки
        day_offset = 0
        if hour >= 24:
            hour -= 24
            day_offset = 1
        
        # Форматируем
        if hour == 0:
            result = '12:00 AM'
        elif hour < 12:
            result = f'{hour}:{minute:02d} AM'
        elif hour == 12:
            result = f'12:{minute:02d} PM'
        else:
            result = f'{hour-12}:{minute:02d} PM'
        
        return f"{result} МСК", day_offset
        
    except Exception as e:
        logger.warning(f"Ошибка конвертации времени {et_time_str}: {e}")
        return '04:30 МСК', 0

def get_future_matches():
    """
    Получает реальные матчи из ESPN API на ближайшие 5 дней
    """
    games = []
    today = datetime.now()
    
    # Проверяем даты на 5 дней вперёд
    for offset in range(0, 6):
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
                        # Получаем статус матча
                        status = competition.get('status', {}).get('type', {}).get('description', '')
                        
                        # Пропускаем завершённые матчи
                        if status == 'Final':
                            logger.info(f"  Пропускаем завершённый матч: {home_team} vs {away_team}")
                            continue
                        
                        # Получаем время матча
                        event_date = event.get('date', '')
                        game_time = '19:00 ET'
                        if event_date:
                            try:
                                dt = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                game_time = dt.strftime('%I:%M %p ET').lstrip('0')
                            except:
                                pass
                        
                        msk_time, day_offset = convert_time_to_msk(game_time)
                        
                        # Корректируем дату, если матч перешёл на следующий день по МСК
                        match_date = check_date
                        if day_offset > 0:
                            match_date = check_date + timedelta(days=day_offset)
                        
                        date_str_msk = match_date.strftime('%d.%m.%Y')
                        
                        games.append({
                            'home': home_team,
                            'away': away_team,
                            'date': date_str_msk,
                            'time': msk_time,
                            'raw_time': game_time,
                            'status': status
                        })
                        logger.info(f"  Найден матч: {home_team} vs {away_team} | {date_str_msk} {msk_time}")
                        
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
    
    # PPG разница
    home_ppg = home_stats.get('ppg', 0)
    away_ppg = away_stats.get('ppg', 0)
    if home_ppg > 0 and away_ppg > 0:
        ppg_effect = (home_ppg - away_ppg) * 0.4
        base += ppg_effect
        reasons.append(f"PPG {ppg_effect:+.1f}")
    
    # Разница в защите
    home_opp = home_stats.get('opp_ppg', 0)
    away_opp = away_stats.get('opp_ppg', 0)
    if home_opp > 0 and away_opp > 0:
        def_effect = (away_opp - home_opp) * 0.3
        base += def_effect
        reasons.append(f"Защита {def_effect:+.1f}")
    
    # Процент побед
    home_pct = home_stats.get('win_pct', 50)
    away_pct = away_stats.get('win_pct', 50)
    pct_effect = (home_pct - away_pct) / 2.5
    base += pct_effect
    reasons.append(f"Win% {pct_effect:+.1f}")
    
    # H2H
    if h2h != '0-0':
        parts = h2h.split('-')
        home_h2h = int(parts[0])
        away_h2h = int(parts[1])
        total = home_h2h + away_h2h
        if total > 0:
            h2h_effect = (home_h2h / total - 0.5) * 10
            base += h2h_effect
            reasons.append(f"H2H {h2h_effect:+.1f}")
    
    # Травмы
    base += home_injury_impact
    base -= away_injury_impact
    if home_injury_impact != 0:
        reasons.append(f"Травмы дома {home_injury_impact:+.1f}")
    if away_injury_impact != 0:
        reasons.append(f"Травмы гостей {-away_injury_impact:+.1f}")
    
    # Домашнее поле
    base += 4
    reasons.append(f"Дом +4")
    
    prob = max(35, min(85, base))
    logger.info(f"    🎯 {home}: {prob:.1f}%")
    
    return round(prob, 1)

def calculate_total_prediction(home_stats, away_stats):
    """
    Рассчитывает тотал для матча (разный для разных команд)
    """
    home_ppg = home_stats.get('ppg', 0)
    away_ppg = away_stats.get('ppg', 0)
    home_opp = home_stats.get('opp_ppg', 0)
    away_opp = away_stats.get('opp_ppg', 0)
    
    if home_ppg == 0 or away_ppg == 0:
        return None
    
    # Ожидаемый тотал
    expected_total = (home_ppg + away_opp) / 2 + (away_ppg + home_opp) / 2
    
    # Стандартное отклонение для НБА
    std_dev = 11.5
    
    from math import erf
    
    # Линии тотала
    lines = [215.5, 220.5, 225.5, 230.5]
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
    logger.info("   Получение реальных матчей из ESPN API")
    logger.info("   Только будущие матчи, тоталы разные для каждой пары")
    logger.info("=" * 60)
    
    os.makedirs('data', exist_ok=True)
    
    # Получаем будущие матчи из ESPN API
    games = get_future_matches()
    
    if not games:
        logger.warning("Матчи не найдены в API, возможно нет игр в ближайшие дни")
        # Создаём пустой файл
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
        logger.info("Создан пустой файл matches.json")
        return
    
    all_matches = []
    
    for game in games:
        home = game['home']
        away = game['away']
        
        logger.info(f"\n📋 Обработка матча: {home} vs {away}")
        
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
            'data_source': 'ESPN_API_Live',
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
        logger.info(f"  ✅ {winner} победа ({prob}%) | {total_pred if total_pred else 'Нет тотала >73%'}")
    
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
    logger.info(f"   Все матчи на дату >= {datetime.now().strftime('%d.%m.%Y')}")

if __name__ == "__main__":
    main()
