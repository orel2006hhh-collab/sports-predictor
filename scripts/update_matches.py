import json
from datetime import datetime, timedelta

today = datetime.now()
tomorrow = today + timedelta(days=1)

today_str = today.strftime('%d.%m.%Y')
tomorrow_str = tomorrow.strftime('%d.%m.%Y')

matches = [
    {'sport': 'nhl', 'home': 'Philadelphia Flyers', 'away': 'Carolina Hurricanes', 'league': 'НХЛ', 'prob': 72, 'winner': 'Carolina Hurricanes', 'date': today_str, 'time': '02:00 МСК'},
    {'sport': 'vhl', 'home': 'Югра', 'away': 'Нефтяник', 'league': 'ВХЛ', 'prob': 78, 'winner': 'Югра', 'date': today_str, 'time': '19:00 МСК'},
    {'sport': 'nba', 'home': 'Oklahoma City Thunder', 'away': 'Los Angeles Lakers', 'league': 'НБА', 'prob': 72, 'winner': 'Oklahoma City Thunder', 'date': today_str, 'time': '05:30 МСК'},
    {'sport': 'cricket', 'home': 'Gujarat Titans', 'away': 'Mumbai Indians', 'league': 'IPL', 'prob': 68, 'winner': 'Gujarat Titans', 'date': today_str, 'time': '21:30 МСК'},
    {'sport': 'cricket', 'home': 'Kolkata Knight Riders', 'away': 'Chennai Super Kings', 'league': 'IPL', 'prob': 72, 'winner': 'Kolkata Knight Riders', 'date': tomorrow_str, 'time': '21:30 МСК'}
]

output = {
    "lastUpdated": datetime.now().isoformat(),
    "matches": matches,
    "dateInfo": {"today": today_str, "tomorrow": tomorrow_str}
}

with open('data/matches.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✅ Обновлено! Матчей: {len(matches)}")
