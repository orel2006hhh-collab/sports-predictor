"""
Модуль расчёта прогнозов на основе реальной статистики ESPN
"""

def calculate_home_advantage(home_team, away_team, league):
    """Фактор домашнего поля (+3% к вероятности хозяев)"""
    return 3

def calculate_form_advantage(home_stats, away_stats):
    """Преимущество на основе формы (последние 10 матчей)"""
    home_form = home_stats.get('form', 50)
    away_form = away_stats.get('form', 50)
    diff = home_form - away_form
    return diff * 0.3  # каждые 10% разницы дают ±3% вероятности

def calculate_h2h_advantage(h2h_data):
    """Преимущество на основе истории личных встреч"""
    if not h2h_data:
        return 0
    home_wins = h2h_data.get('home_wins', 0)
    away_wins = h2h_data.get('away_wins', 0)
    total = home_wins + away_wins
    if total == 0:
        return 0
    win_rate = home_wins / total
    return (win_rate - 0.5) * 10  # от -5% до +5%

def calculate_offense_defense_advantage(home_stats, away_stats):
    """Преимущество на основе атаки и защиты"""
    home_offense = home_stats.get('ppg', 110)
    home_defense = home_stats.get('opp_ppg', 108)
    away_offense = away_stats.get('ppg', 110)
    away_defense = away_stats.get('opp_ppg', 108)
    
    # Ожидаемая разница очков
    expected_diff = (home_offense - away_defense) - (away_offense - home_defense)
    return expected_diff * 0.2  # каждые 5 очков дают ±1%

def calculate_injury_impact(injuries):
    """Влияние травм ключевых игроков"""
    if not injuries:
        return 0
    # Каждая травма звезды снижает вероятность на 5-10%
    impact = -len(injuries) * 3
    return max(-15, min(0, impact))

def predict_match(home_team, away_team, league, home_stats, away_stats, h2h_data, injuries):
    """
    Расчёт вероятности победы на основе всех факторов
    """
    base_prob = 50
    
    factors = {
        'home_advantage': calculate_home_advantage(home_team, away_team, league),
        'form_advantage': calculate_form_advantage(home_stats, away_stats),
        'h2h_advantage': calculate_h2h_advantage(h2h_data),
        'offense_defense_advantage': calculate_offense_defense_advantage(home_stats, away_stats),
        'injury_impact': calculate_injury_impact(injuries.get(home_team, [])) - 
                         calculate_injury_impact(injuries.get(away_team, []))
    }
    
    total_adjustment = sum(factors.values())
    home_prob = base_prob + total_adjustment
    away_prob = 100 - home_prob
    
    # Ограничиваем диапазон
    home_prob = max(35, min(85, home_prob))
    away_prob = 100 - home_prob
    
    return {
        'home_prob': round(home_prob, 1),
        'away_prob': round(away_prob, 1),
        'winner': home_team if home_prob > away_prob else away_team,
        'factors': factors,
        'home_ppg': home_stats.get('ppg', 110),
        'away_ppg': away_stats.get('ppg', 110)
    }

def calculate_total(home_stats, away_stats):
    """Расчёт ожидаемого тотала"""
    home_avg = home_stats.get('ppg', 110)
    away_avg = away_stats.get('ppg', 110)
    home_defense = home_stats.get('opp_ppg', 108)
    away_defense = away_stats.get('opp_ppg', 108)
    
    expected_total = (home_avg + away_defense) / 2 + (away_avg + home_defense) / 2
    line = round(expected_total / 5) * 5
    verdict = 'БОЛЬШЕ' if expected_total > line else 'МЕНЬШЕ'
    
    return f"Тотал {verdict} {line}.5"
