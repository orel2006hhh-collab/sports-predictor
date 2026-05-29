# Добавьте этот словарь в начало скрипта после импортов

FALLBACK_STATS = {
    "Oklahoma City Thunder": {"ppg": 119.4, "form": "6-4", "streak": -2, "win_pct": 60},
    "San Antonio Spurs": {"ppg": 119.6, "form": "8-2", "streak": 4, "win_pct": 80},
    "Los Angeles Lakers": {"ppg": 116.4, "form": "7-3", "streak": 2, "win_pct": 70},
    "Golden State Warriors": {"ppg": 114.6, "form": "6-4", "streak": -1, "win_pct": 60},
    "Boston Celtics": {"ppg": 114.5, "form": "9-1", "streak": 5, "win_pct": 90},
    "Denver Nuggets": {"ppg": 121.9, "form": "8-2", "streak": 3, "win_pct": 80},
    "New York Knicks": {"ppg": 116.8, "form": "7-3", "streak": 1, "win_pct": 70},
    "Phoenix Suns": {"ppg": 113.2, "form": "5-5", "streak": -1, "win_pct": 50},
    "Dallas Mavericks": {"ppg": 113.6, "form": "5-5", "streak": 1, "win_pct": 50},
    "Milwaukee Bucks": {"ppg": 119.8, "form": "7-3", "streak": 1, "win_pct": 70},
    "Miami Heat": {"ppg": 120.4, "form": "5-5", "streak": -2, "win_pct": 50},
    "Philadelphia 76ers": {"ppg": 115.9, "form": "6-4", "streak": 1, "win_pct": 60},
    "LA Clippers": {"ppg": 114.0, "form": "6-4", "streak": 2, "win_pct": 60},
    "Minnesota Timberwolves": {"ppg": 115.8, "form": "5-5", "streak": 0, "win_pct": 50},
    "Sacramento Kings": {"ppg": 118.2, "form": "4-6", "streak": -1, "win_pct": 40},
    "New Orleans Pelicans": {"ppg": 115.1, "form": "4-6", "streak": -2, "win_pct": 40},
    "Houston Rockets": {"ppg": 114.3, "form": "3-7", "streak": -3, "win_pct": 30},
    "Utah Jazz": {"ppg": 115.7, "form": "3-7", "streak": -4, "win_pct": 30},
}

def get_team_stats_fallback(team_name):
    """Получить статистику из встроенного словаря"""
    if team_name in FALLBACK_STATS:
        return FALLBACK_STATS[team_name]
    return {"ppg": 110.0, "form": "5-5", "streak": 0, "win_pct": 50}
