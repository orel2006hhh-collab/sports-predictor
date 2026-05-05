import json
import requests
from datetime import datetime, timedelta
import re

def get_thesportsdb_results(league_id, date_from, date_to):
    """Получает результаты матчей из TheSportsDB за указанный период"""
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?l={league_id}&d={date_from}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            results = []
            for event in events:
                if event.get('strStatus') == 'Match Finished':
                    home_score = int(event.get('intHomeScore', 0) or 0)
                    away_score = int(event.get('intAwayScore', 0) or 0)
                    results.append({
                        'home': event.get('strHomeTeam'),
                        'away': event.get('strAwayTeam'),
                        'date': event.get('dateEvent'),
                        'home_score': home_score,
                        'away_score': away_score,
                        'winner': 'home' if home_score > away_score else ('away' if away_score > home_score else 'draw')
                    })
            return results
    except Exception as e:
        print(f"Ошибка получения результатов: {e}")
    return []

def find_match_in_predictions(match_result, predictions):
    """Ищет матч в наших прогнозах по командам и дате"""
    for pred in predictions:
        if (pred.get('home') == match_result['home'] and 
            pred.get('away') == match_result['away'] and
            pred.get('date') == match_result['date']):
            return pred
    return None

def update_history():
    """Основная функция обновления истории прогнозов"""
    
    # Загружаем текущую историю
    try:
        with open('data/history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
    except FileNotFoundError:
        history = {'predictions': [], 'lastUpdated': ''}
    
    # Загружаем текущие прогнозы
    try:
        with open('data/matches.json', 'r', encoding='utf-8') as f:
            matches_data = json.load(f)
            predictions = matches_data.get('matches', [])
    except FileNotFoundError:
        print("Файл с прогнозами не найден")
        return
    
    # Получаем дату вчерашнего дня для поиска результатов
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # ID лиг в TheSportsDB (нужно подобрать правильные)
    LEAGUE_IDS = {
        'nhl': '4387',      # НХЛ
        'nba': '4387',      # НБА (возможно другой ID)
        'khl': '4387'       # КХЛ (возможно другой ID)
    }
    
    new_results = []
    
    # Для каждой лиги получаем результаты
    for sport, league_id in LEAGUE_IDS.items():
        results = get_thesportsdb_results(league_id, yesterday, yesterday)
        
        for result in results:
            # Ищем соответствующий прогноз
            prediction = find_match_in_predictions(result, predictions)
            
            if prediction:
                # Проверяем, не добавлен ли уже этот результат
                already_exists = False
                for existing in history['predictions']:
                    if (existing['home'] == result['home'] and 
                        existing['away'] == result['away'] and
                        existing['date'] == result['date']):
                        already_exists = True
                        break
                
                if not already_exists:
                    # Определяем, сбылся ли прогноз
                    predicted_winner = prediction.get('winner', '')
                    actual_winner = result['winner']
                    
                    is_success = False
                    if actual_winner != 'draw':
                        if actual_winner == 'home' and predicted_winner == prediction.get('home', ''):
                            is_success = True
                        elif actual_winner == 'away' and predicted_winner == prediction.get('away', ''):
                            is_success = True
                    
                    new_results.append({
                        'date': result['date'],
                        'home': result['home'],
                        'away': result['away'],
                        'league': prediction.get('league', ''),
                        'prediction': f"{predicted_winner} победа",
                        'result': 'success' if is_success else 'failed',
                        'prob': prediction.get('prob', 0),
                        'actual_score': f"{result['home_score']}:{result['away_score']}"
                    })
    
    # Добавляем новые результаты в историю
    if new_results:
        history['predictions'].extend(new_results)
        history['lastUpdated'] = datetime.now().isoformat()
        
        # Сохраняем обновлённую историю
        with open('data/history.json', 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Добавлено новых результатов: {len(new_results)}")
    else:
        print("Новых результатов не найдено")

if __name__ == "__main__":
    update_history()
