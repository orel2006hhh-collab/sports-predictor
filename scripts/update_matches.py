import json
import urllib.request
from datetime import datetime, timedelta

# ID лиги НХЛ в TheSportsDB
LEAGUE_ID = '4387'
# Бесплатный публичный API-ключ (можно получить на Patreon)
API_KEY = '3'  # тестовый ключ для разработки

url = f'https://www.thesportsdb.com/api/v1/json/{API_KEY}/eventsnextleague.php?id={LEAGUE_ID}'

try:
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode('utf-8'))
    
    events = data.get('events', [])
    matches = []
    
    for event in events:
        match = {
            'sport': 'nhl',
            'home': event.get('strHomeTeam'),
            'away': event.get('strAwayTeam'),
            'league': 'НХЛ',
            'date': event.get('dateEvent'),
            'time': event.get('strTime'),
            'series': 'Регулярный чемпионат',
            'prob': 70,
            'winner': event.get('strHomeTeam')
        }
        matches.append(match)
    
    # Сохраняем в matches.json
    with open('data/matches.json', 'w') as f:
        json.dump(matches, f)
        
except Exception as e:
    print(f'Ошибка: {e}')
