#!/usr/bin/env python3
"""
Парсер реальных данных с ESPN API + расчёт вероятностей на основе Power Index и статистики
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
# ПОЛУЧЕНИЕ МАТЧЕЙ ИЗ ESPN API
# ============================================================

def get_nba_games():
    """Получает матчи НБА и ID событий из ESPN API"""
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        games = []
        for event in data.get('events', []):
            event_id = event.get('id')
            competition = event.get('competitions', [{}])[0]
            competition_id = competition.get('id')
            competitors = competition.get('competitors', [])
            
            home_team = None
            away_team = None
            home_id = None
            away_id = None
            
            for comp in competitors:
                team = comp.get('team', {})
                if comp.get('homeAway') == 'home':
                    home_team = team.get('displayName', 'Unknown')
                    home_id = team.get('id')
                else:
                    away_team = team.get('displayName', 'Unknown')
                    away_id = team.get('id')
            
            if home_team and away_team:
                event_date = event.get('date', '')
                try:
                    dt = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                    msk_time = dt + timedelta(hours=3)
                    game_time = msk_time.strftime('%H:%M МСК')
                except:
                    game_time = '19:00 МСК'
                
                games.append({
                    'event_id': event_id,
                    'competition_id': competition_id,
                    'home': home_team,
                    'away': away_team,
                    'home_id': home_id,
                    'away_id': away_id,
                    'time': game_time
                })
                
                logger.info(f"  Найден матч: {home_team} vs {away_team} (Event ID: {event_id})")
        
        return games
        
    except Exception as e:
        logger.error(f"Ошибка получения расписания: {e}")
        return []

# ============================================================
# ПОЛУЧЕНИЕ ПРОГНОЗОВ ИЗ ESPN (РЕАЛЬНЫЕ ВЕРОЯТНОСТИ)
# ============================================================

def get_espn_win_probabilities(event_id, home_team, away_team):
    """
    Получает реальные вероятности победы из ESPN через эндпоинт summary
    Документация: https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={id}
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
    
    try:
        logger.info(f"  Запрос вероятностей через summary...")
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Ищем winProbability в ответе
            win_prob = data.get('winprobability', [])
            if win_prob:
                # win_prob содержит массив с вероятностями для каждого периода
                # Последняя запись — финальная вероятность
                if len(win_prob) > 0:
                    last_prob = win_prob[-1]
                    home_prob = last_prob.get('homeWinPercentage')
                    away_prob = last_prob.get('awayWinPercentage')
                    if home_prob and away_prob:
                        logger.info(f"    ✅ WinProbability из summary: {home_team} {home_prob}% — {away_team} {away_prob}%")
                        return home_prob, away_prob
            
            # Пробуем найти в pickcenter (прогнозы аналитиков)
            pick_center = data.get('pickcenter', {})
            if pick_center:
                home_pct = pick_center.get('homeWinPercentage')
                away_pct = pick_center.get('awayWinPercentage')
                if home_pct and away_pct:
                    logger.info(f"    ✅ WinProbability из pickcenter: {home_team} {home_pct}% — {away_team} {away_pct}%")
                    return home_pct, away_pct
            
            logger.warning(f"    ⚠️ Вероятности не найдены в summary")
    except Exception as e:
        logger.warning(f"    Ошибка получения summary: {e}")
    
    return None, None

def get_espn_power_index(event_id, home_team, away_team):
    """
    Получает ESPN Power Index (рейтинг силы команд)
    Документация: https://site.api.espn.com/apis/v2/sports/basketball/nba/powerindex
    """
    # Power Index — голосование ESPN аналитиков, учитывающее форму, травмы, силу соперников
    url = f"https://site.api.espn.com/apis/v2/sports/basketball/nba/powerindex"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            teams = data.get('teams', [])
            
            home_rating = None
            away_rating = None
            
            for team in teams:
                team_name = team.get('team', {}).get('displayName', '')
                rating = team.get('powerIndex', {}).get('value')
                
                if team_name == home_team and rating:
                    home_rating = rating
                elif team_name == away_team and rating:
                    away_rating = rating
            
            if home_rating and away_rating:
                logger.info(f"    📊 Power Index: {home_team} {home_rating} — {away_team} {away_rating}")
                return home_rating, away_rating
    except Exception as e:
        logger.warning(f"    Ошибка получения Power Index: {e}")
    
    return None, None

def get_espn_standings():
    """
    Получает турнирную таблицу НБА через официальный эндпоинт
    ⚠️ Важно: использовать /apis/v2/ вместо /apis/site/v2/ [citation:4]
    """
    url = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
    
    standings = {}
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            for entry in data.get('children', []):
                team_data = entry.get('team', {})
                team_name = team_data.get('displayName', '')
                stats = entry.get('stats', [])
                
                wins = 0
                losses = 0
                win_pct = 0
                
                for stat in stats:
                    stat_name = stat.get('name', '')
                    stat_value = stat.get('value', 0)
                    if stat_name == 'wins':
                        wins = stat_value
                    elif stat_name == 'losses':
                        losses = stat_value
                    elif stat_name == 'winPercent':
                        win_pct = stat_value
                
                if team_name:
                    standings[team_name] = {
                        'wins': wins,
                        'losses': losses,
                        'win_pct': win_pct
                    }
                    logger.debug(f"    📊 Standings: {team_name} — {wins}-{losses}")
    except Exception as e:
        logger.warning(f"    Ошибка получения таблицы: {e}")
    
    return standings

# ============================================================
# ПОЛУЧЕНИЕ СТАТИСТИКИ КОМАНД (PPG, OPP PPG)
# ============================================================

def get_team_stats(team_id):
    """Получает статистику команды через ESPN API"""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/stats"
    
    stats = {
        'ppg': 0,
        'opp_ppg': 0,
        'wins': 0,
        'losses': 0,
        'win_pct': 0
    }
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            splits = data.get('splits', [])
            
            for split in splits:
                if split.get('type') == 'season':
                    season_stats = split.get('stats', {})
                    
                    if 'pointsPerGame' in season_stats:
                        stats['ppg'] = round(season_stats['pointsPerGame'], 1)
                    if 'opponentPointsPerGame' in season_stats:
                        stats['opp_ppg'] = round(season_stats['opponentPointsPerGame'], 1)
                    if 'wins' in season_stats:
                        stats['wins'] = season_stats['wins']
                    if 'losses' in season_stats:
                        stats['losses'] = season_stats['losses']
                    if 'winPercent' in season_stats:
                        stats['win_pct'] = round(season_stats['winPercent'] * 100)
            
            logger.info(f"    📊 {stats['ppg']} PPG | {stats['opp_ppg']} OPP PPG | {stats['wins']}-{stats['losses']}")
    except Exception as e:
        logger.warning(f"    Ошибка получения статистики: {e}")
    
    return stats

# ============================================================
# УПРОЩЁННАЯ ФУНКЦИЯ ДЛЯ H2H
# ============================================================

def get_h2h_record(team1_name, team2_name, team1_id, team2_id):
    """Получает историю личных встреч через ESPN API"""
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team1_id}/matchups/{team2_id}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            matchups = data.get('matchups', [])
            
            team1_wins = 0
            team2_wins = 0
            
            for matchup in matchups[:10]:
                winner = matchup.get('winner', {})
                winner_name = winner.get('displayName', '')
                if winner_name == team1_name:
                    team1_wins += 1
                elif winner_name == team2_name:
                    team2_wins += 1
            
            if team1_wins > 0 or team2_wins > 0:
                logger.info(f"    📊 H2H: {team1_name} {team1_wins} — {team2_name} {team2_wins}")
                return f"{team1_wins}-{team2_wins}"
    except Exception as e:
        logger.debug(f"    H2H API не ответил: {e}")
    
    return None

# ============================================================
# РАСЧЁТ ВЕРОЯТНОСТИ (ЕСЛИ ESPN НЕ ДАЛ)
# ============================================================

def calculate_probability_from_stats(home_stats, away_stats, power_index_home, power_index_away, standings):
    """
    Рассчитывает вероятность победы на основе:
    - Power Index [citation:4]
    - Процента побед в сезоне
    - Разницы в PPG
    """
    base_prob = 50
    reasons = []
    
    # 1. Power Index (если есть)
    if power_index_home and power_index_away:
        pi_ratio = power_index_home / (power_index_home + power_index_away)
        pi_adjust = (pi_ratio - 0.5) * 15
        base_prob += pi_adjust
        reasons.append(f"Power Index: {pi_adjust:+.1f}%")
    
    # 2. Процент побед в сезоне
    home_win_pct = standings.get(home_stats.get('wins') and home_stats.get('losses') 
                                   and home_stats['wins'] / (home_stats['wins'] + home_stats['losses']) * 100
                                   if home_stats.get('wins') is not None and home_stats.get('losses') is not None
                                   else 50)
    away_win_pct = standings.get(away_stats.get('wins') and away_stats.get('losses')
                                   and away_stats['wins'] / (away_stats['wins'] + away_stats['losses']) * 100
                                   if away_stats.get('wins') is not None and away_stats.get('losses') is not None
                                   else 50)
    
    win_pct_diff = (home_win_pct - away_win_pct) / 4
    base_prob += win_pct_diff
    reasons.append(f"Win% сезона: {win_pct_diff:+.1f}%")
    
    # 3. Разница в PPG (очках за игру)
    if home_stats.get('ppg') and away_stats.get('ppg'):
        ppg_diff = (home_stats['ppg'] - away_stats['ppg']) * 0.3
        base_prob += ppg_diff
        reasons.append(f"Разница PPG: {ppg_diff:+.1f}%")
    
    # 4. Разница в защите (OPP PPG)
    if home_stats.get('opp_ppg') and away_stats.get('opp_ppg'):
        opp_diff = (away_stats['opp_ppg'] - home_stats['opp_ppg']) * 0.3
        base_prob += opp_diff
        reasons.append(f"Разница защиты: {opp_diff:+.1f}%")
    
    # 5. Домашнее поле (+3%)
    base_prob += 3
    reasons.append(f"Домашнее поле: +3%")
    
    # Ограничиваем диапазон
    final_prob = max(30, min(85, base_prob))
    
    logger.info(f"    🎯 Расчётная вероятность: {final_prob:.1f}% ({' + '.join(reasons)})")
    
    return round(final_prob, 1)

# ============================================================
# РАСЧЁТ ТОТАЛА С ВЕРОЯТНОСТЬЮ
# ============================================================

def calculate_total_with_probability(home_stats, away_stats):
    """Рассчитывает тотал и возвращает только прогнозы с вероятностью >73%"""
    
    home_ppg = home_stats.get('ppg', 0)
    away_ppg = away_stats.get('ppg', 0)
    home_opp = home_stats.get('opp_ppg', 0)
    away_opp = away_stats.get('opp_ppg', 0)
    
    if home_ppg == 0 or away_ppg == 0:
        return None
    
    expected_home = (home_ppg + away_opp) / 2
    expected_away = (away_ppg + home_opp) / 2
    expected_total = expected_home + expected_away
    
    std_dev = 11.5  # стандартное отклонение для НБА
    
    total_lines = [215.5, 220.5, 225.5, 230.5]
    
    best_prediction = None
    best_probability = 0
    
    for line in total_lines:
        # Вероятность того, что тотал будет БОЛЬШЕ
        z_score_over = (expected_total - line) / std_dev
        from math import erf
        prob_over = 0.5 * (1 + erf(z_score_over / (2 ** 0.5)))
        prob_over = round(prob_over * 100)
        
        prob_under = 100 - prob_over
        
        if prob_over > 73 and prob_over > best_probability:
            best_probability = prob_over
            best_prediction = f"Тотал БОЛЬШЕ {line} (вер. {prob_over}%)"
        
        if prob_under > 73 and prob_under > best_probability:
            best_probability = prob_under
            best_prediction = f"Тотал МЕНЬШЕ {line} (вер. {prob_under}%)"
    
    if best_prediction:
        logger.info(f"    🎯 {best_prediction}")
    else:
        logger.info(f"    ⚠️ Нет тоталов с вероятностью >73% (макс: {best_probability}%)")
    
    return best_prediction

# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ МАТЧЕЙ (ESPN API)")
    logger.info("   Источник: summary, powerindex, standings")
    logger.info("=" * 60)
    
    os.makedirs('data', exist_ok=True)
    
    # 1. Получаем матчи
    games = get_nba_games()
    
    if not games:
        logger.error("Матчи не найдены!")
        return
    
    # 2. Получаем турнирную таблицу (для резервного расчёта)
    standings = get_espn_standings()
    
    today = datetime.now().strftime('%d.%m.%Y')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
    
    all_matches = []
    
    for game in games:
        home = game['home']
        away = game['away']
        event_id = game['event_id']
        home_id = game['home_id']
        away_id = game['away_id']
        
        logger.info(f"\n📋 Обработка матча: {home} vs {away}")
        
        # 3. Получаем вероятности из ESPN
        home_prob, away_prob = get_espn_win_probabilities(event_id, home, away)
        
        # 4. Если вероятности не получены — используем Power Index
        if home_prob is None:
            power_home, power_away = get_espn_power_index(event_id, home, away)
        else:
            power_home, power_away = None, None
        
        # 5. Получаем статистику команд
        home_stats = get_team_stats(home_id)
        away_stats = get_team_stats(away_id)
        
        # 6. Получаем H2H
        h2h = get_h2h_record(home, away, home_id, away_id)
        
        # 7. Определяем итоговую вероятность
        if home_prob is not None:
            prob = home_prob
            winner = home if prob >= 50 else away
            logger.info(f"  ✅ Вероятность из ESPN: {home} {prob}% — {away} {100-prob}%")
        else:
            prob = calculate_probability_from_stats(home_stats, away_stats, power_home, power_away, standings)
            winner = home if prob >= 50 else away
        
        # 8. Рассчитываем тотал
        total_prediction = calculate_total_with_probability(home_stats, away_stats)
        
        match_data = {
            'sport': 'nba',
            'home': home,
            'away': away,
            'league': 'NBA',
            'prob': prob,
            'winner': winner,
            'date': today,
            'time': game['time'],
            'total_prediction': total_prediction if total_prediction else "Нет уверенного прогноза (>73%)",
            'data_source': 'ESPN_API (summary/powerindex)',
            'h2h': h2h,
            'home_ppg': home_stats.get('ppg', 0),
            'away_ppg': away_stats.get('ppg', 0),
            'home_win_pct': home_stats.get('win_pct', 0),
            'away_win_pct': away_stats.get('win_pct', 0)
        }
        
        all_matches.append(match_data)
        logger.info(f"  ✅ ИТОГО: {winner} победа ({prob}%)")
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": today,
            "tomorrow": tomorrow
        },
        "note": "Вероятности из ESPN API, тоталы с вероятностью >73%"
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n✅ ГОТОВО! Сохранено матчей: {len(all_matches)}")

if __name__ == "__main__":
    main()
