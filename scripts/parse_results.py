import json
import requests
from datetime import datetime, timedelta
import re

# ID лиг в TheSportsDB
LEAGUE_IDS = {
    'nhl': {'id': '4387', 'name': 'НХЛ', 'sport': 'hockey'},
    'nba': {'id': '4387', 'name': 'НБА', 'sport': 'basketball'},
}

def fetch_from_thesportsdb(league_id, date):
    """Получение результатов с TheSportsDB"""
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?l={league_id}&d={date}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data.get('events', [])
    except Exception as e:
        print(f"Ошибка TheSportsDB: {e}")
    return []

def parse_khl_results(date):
    """Парсинг результатов КХЛ (имитация, для реального нужен API)"""
    # Временно возвращаем тестовые данные
    # В реальности нужно подключиться к API КХЛ или парсить сайт
    return []

def parse_vhl_results(date):
    """Парсинг результатов ВХЛ"""
    return []

def parse_mhl_results(date):
    """Парсинг результатов МХЛ"""
    return []

def parse_vtb_results(date):
    """Парсинг результатов Единой лиги ВТБ"""
    return []

def parse_ipl_results(date):
    """Парсинг результатов IPL"""
    return []

def determine_winner(home_score, away_score):
    """Определяет победителя по счёту"""
    if home_score > away_score:
        return 'home'
    elif away_score > home_score:
        return 'away'
    else:
        return 'draw'

def load_predictions():
    """Загружает текущие прогнозы из matches.json"""
    try:
        with open('data/matches.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('matches', [])
    except FileNotFoundError:
        return []

def load_history():
    """Загружает историю прогнозов"""
    try:
        with open('data/history.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'predictions': [], 'lastUpdated': ''}

def save_history(history):
    """Сохраняет историю прогнозов"""
    with open('data/history.json', 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def match_exists_in_history(history, match_date, home, away):
    """Проверяет, есть ли уже матч в истории"""
    for pred in history.get('predictions', []):
        if pred['date'] == match_date and pred['home'] == home and pred['away'] == away:
            return True
    return False

def update_history():
    """Обновляет историю прогнозов"""
    print("🚀 Запуск обновления результатов матчей...")
    
    # Загружаем текущие данные
    predictions = load_predictions()
    history = load_history()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    new_results = []
    
    # Обрабатываем каждую лигу
    for sport, config in LEAGUE_IDS.items():
        print(f"Обработка {config['name']}...")
        events = fetch_from_thesportsdb(config['id'], yesterday)
        
        for event in events:
            home_team = event.get('strHomeTeam', '')
            away_team = event.get('strAwayTeam', '')
            match_date = event.get('dateEvent', '')
            home_score = event.get('intHomeScore', 0) or 0
            away_score = event.get('intAwayScore', 0) or 0
            
            if home_score == 0 and away_score == 0:
                continue
                
            winner = determine_winner(home_score, away_score)
            
            # Ищем соответствующий прогноз
            for pred in predictions:
                if (pred.get('home') == home_team and 
                    pred.get('away') == away_team and
                    pred.get('date') == match_date.replace('-', '.')[::-1].replace('.', '.', 1)[::-1]):
                    
                    if not match_exists_in_history(history, match_date, home_team, away_team):
                        predicted_winner = pred.get('winner', '')
                        actual_winner_name = home_team if winner == 'home' else (away_team if winner == 'away' else 'ничья')
                        
                        is_success = False
                        if winner != 'draw':
                            if (winner == 'home' and predicted_winner == home_team) or \
                               (winner == 'away' and predicted_winner == away_team):
                                is_success = True
                        
                        new_results.append({
                            'date': match_date.replace('-', '.')[::-1].replace('.', '.', 1)[::-1],
                            'home': home_team,
                            'away': away_team,
                            'league': pred.get('league', config['name']),
                            'sport': sport,
                            'prediction': predicted_winner,
                            'result': 'success' if is_success else 'failed',
                            'prob': pred.get('prob', 65),
                            'actual_score': f"{home_score}:{away_score}"
                        })
                        print(f"  📊 {home_team} {home_score}:{away_score} {away_team} → {'✅' if is_success else '❌'}")
    
    # Добавляем результаты
    if new_results:
        history['predictions'].extend(new_results)
        history['lastUpdated'] = datetime.now().isoformat()
        save_history(history)
        print(f"\n✅ Добавлено новых результатов в историю: {len(new_results)}")
        
        # Выводим общую точность
        total = len(history['predictions'])
        successes = sum(1 for p in history['predictions'] if p['result'] == 'success')
        accuracy = (successes / total * 100) if total > 0 else 0
        print(f"📈 Общая точность прогнозов: {accuracy:.1f}% ({successes}/{total})")
    else:
        print("📭 Новых результатов не найдено")

if __name__ == "__main__":
    update_history()
