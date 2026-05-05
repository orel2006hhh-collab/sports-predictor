import json
from datetime import datetime, timedelta

def get_today_tomorrow():
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    return today.strftime('%d.%m.%Y'), tomorrow.strftime('%d.%m.%Y')

def create_sample_matches():
    today, tomorrow = get_today_tomorrow()
    
    matches = [
        {'sport': 'nhl', 'home': 'Philadelphia Flyers', 'away': 'Carolina Hurricanes', 'league': 'НХЛ', 'prob': 72, 'winner': 'Carolina Hurricanes', 'date': today, 'time': '02:00 МСК', 'series': 'Плей-офф', 'weather': 'Ясно, 12°C', 'motivation': 'Филадельфия обязана выигрывать'},
        {'sport': 'vhl', 'home': 'Югра', 'away': 'Нефтяник', 'league': 'ВХЛ', 'prob': 78, 'winner': 'Югра', 'date': today, 'time': '19:00 МСК', 'series': 'Финал', 'weather': 'Ясно, -5°C', 'motivation': 'Югра ведёт 3-0 в серии'},
        {'sport': 'nba', 'home': 'Oklahoma City Thunder', 'away': 'Los Angeles Lakers', 'league': 'НБА', 'prob': 72, 'winner': 'Oklahoma City Thunder', 'date': today, 'time': '05:30 МСК', 'series': 'Плей-офф', 'weather': 'Крытая арена', 'motivation': 'Лейкерс без Джеймса'},
        {'sport': 'cricket', 'home': 'Gujarat Titans', 'away': 'Mumbai Indians', 'league': 'IPL', 'prob': 68, 'winner': 'Gujarat Titans', 'date': today, 'time': '21:30 МСК', 'series': 'Тур 2026', 'weather': '40°C, ясно', 'motivation': 'Титаны в топ-4'},
        {'sport': 'cricket', 'home': 'Kolkata Knight Riders', 'away': 'Chennai Super Kings', 'league': 'IPL', 'prob': 72, 'winner': 'Kolkata Knight Riders', 'date': tomorrow, 'time': '21:30 МСК', 'series': 'Тур 2026', 'weather': '35°C, влажно', 'motivation': 'KKR борется за 1 место'}
    ]
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": matches,
        "dateInfo": {"today": today, "tomorrow": tomorrow}
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Обновлено! Матчей: {len(matches)}")

if __name__ == "__main__":
    create_sample_matches()
