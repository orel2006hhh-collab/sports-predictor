#!/usr/bin/env python3
"""
Скрипт для получения результатов завершённых матчей и сравнения с прогнозами
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
# ФУНКЦИИ ДЛЯ ПОЛУЧЕНИЯ РЕЗУЛЬТАТОВ ИЗ ESPN API
# ============================================================

def get_completed_games_from_espn():
    """
    Получает завершённые матчи из ESPN API за последние 3 дня
    """
    completed_games = []
    
    # Проверяем несколько дат (вчера, позавчера, 3 дня назад)
    for days_ago in [1, 2, 3]:
        date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y%m%d')
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
        
        try:
            logger.info(f"Запрос результатов за {date}...")
            response = requests.get(url, headers=HEADERS, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                
                for event in events:
                    # Получаем статус матча
                    status = event.get('status', {}).get('type', {}).get('description', '')
                    
                    # Только завершённые матчи
                    if status == 'Final':
                        competition = event.get('competitions', [{}])[0]
                        competitors = competition.get('competitors', [])
                        
                        home_team = None
                        away_team = None
                        home_score = 0
                        away_score = 0
                        
                        for comp in competitors:
                            team = comp.get('team', {})
                            score = comp.get('score', 0)
                            
                            if comp.get('homeAway') == 'home':
                                home_team = team.get('displayName', 'Unknown')
                                home_score = int(score) if score else 0
                            else:
                                away_team = team.get('displayName', 'Unknown')
                                away_score = int(score) if score else 0
                        
                        if home_team and away_team:
                            event_date = event.get('date', '')
                            try:
                                dt = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
                                game_date = dt.strftime('%d.%m.%Y')
                            except:
                                game_date = (datetime.now() - timedelta(days=days_ago)).strftime('%d.%m.%Y')
                            
                            completed_games.append({
                                'home': home_team,
                                'away': away_team,
                                'home_score': home_score,
                                'away_score': away_score,
                                'date': game_date,
                                'winner': home_team if home_score > away_score else away_team,
                                'status': status
                            })
                            logger.info(f"  Найден завершённый матч: {home_team} {home_score}:{away_score} {away_team}")
                
        except Exception as e:
            logger.error(f"Ошибка получения результатов за {date}: {e}")
    
    return completed_games

def load_predictions():
    """Загружает прогнозы из matches.json"""
    try:
        with open('data/matches.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            predictions = data.get('matches', [])
            logger.info(f"📊 Загружено прогнозов: {len(predictions)}")
            return predictions
    except FileNotFoundError:
        logger.error("Файл data/matches.json не найден")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга matches.json: {e}")
        return []

def load_history():
    """Загружает историю прогнозов"""
    try:
        with open('data/history.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("Файл history.json не найден, создаю новый")
        return {"lastUpdated": "", "predictions": []}

def save_history(history):
    """Сохраняет историю прогнозов"""
    with open('data/history.json', 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    logger.info(f"💾 История сохранена, записей: {len(history.get('predictions', []))}")

def match_exists_in_history(history, match_date, home, away):
    """Проверяет, есть ли уже матч в истории"""
    for pred in history.get('predictions', []):
        if pred.get('date') == match_date and pred.get('home') == home and pred.get('away') == away:
            return True
    return False

def update_statistics():
    """Основная функция обновления статистики"""
    logger.info("=" * 60)
    logger.info("📊 ЗАПУСК ОБНОВЛЕНИЯ СТАТИСТИКИ ПРОГНОЗОВ")
    logger.info("   Источник: ESPN API")
    logger.info("=" * 60)
    
    os.makedirs('data', exist_ok=True)
    
    # 1. Загружаем прогнозы и историю
    predictions = load_predictions()
    history = load_history()
    
    if not predictions:
        logger.warning("⚠️ Нет прогнозов для проверки")
        return
    
    # 2. Получаем результаты завершённых матчей
    completed_games = get_completed_games_from_espn()
    
    if not completed_games:
        logger.info("📭 Нет завершённых матчей для обработки")
        return
    
    # 3. Сравниваем прогнозы с результатами
    new_results = []
    matched_predictions = 0
    
    for game in completed_games:
        for pred in predictions:
            # Сравниваем команды и дату
            if (pred.get('home') == game['home'] and pred.get('away') == game['away']):
                matched_predictions += 1
                
                # Проверяем, не добавлен ли уже этот результат
                if match_exists_in_history(history, game['date'], game['home'], game['away']):
                    logger.debug(f"⏭️ Пропускаем (уже в истории): {game['home']} vs {game['away']}")
                    continue
                
                # Определяем, сбылся ли прогноз
                predicted_winner = pred.get('winner', '')
                actual_winner = game['winner']
                
                # Нормализуем названия для сравнения
                is_success = predicted_winner == actual_winner
                
                history_entry = {
                    'date': game['date'],
                    'home': game['home'],
                    'away': game['away'],
                    'league': pred.get('league', 'NBA'),
                    'sport': pred.get('sport', 'nba'),
                    'prediction': f"{predicted_winner} победа",
                    'result': 'success' if is_success else 'failed',
                    'prob': pred.get('prob', 0),
                    'actual_score': f"{game['home_score']}:{game['away_score']}",
                    'checked_at': datetime.now().isoformat()
                }
                
                new_results.append(history_entry)
                
                if is_success:
                    logger.info(f"✅ УГАДАНО! {game['home']} {game['home_score']}:{game['away_score']} {game['away']} | Прогноз: {predicted_winner} ({pred.get('prob', 0)}%)")
                else:
                    logger.info(f"❌ НЕ УГАДАНО! {game['home']} {game['home_score']}:{game['away_score']} {game['away']} | Прогноз: {predicted_winner} ({pred.get('prob', 0)}%)")
                
                break
    
    # 4. Добавляем новые результаты в историю
    if new_results:
        history['predictions'].extend(new_results)
        history['lastUpdated'] = datetime.now().isoformat()
        save_history(history)
        
        # Выводим статистику
        total = len(history['predictions'])
        successes = sum(1 for p in history['predictions'] if p['result'] == 'success')
        accuracy = (successes / total * 100) if total > 0 else 0
        
        logger.info("=" * 60)
        logger.info(f"📊 ИТОГОВАЯ СТАТИСТИКА:")
        logger.info(f"   ✅ Угадано прогнозов: {successes}")
        logger.info(f"   ❌ Не угадано: {total - successes}")
        logger.info(f"   📈 Общая точность: {accuracy:.1f}%")
        logger.info(f"   🆕 Добавлено записей: {len(new_results)}")
        logger.info("=" * 60)
    else:
        logger.info("📭 Нет новых результатов для добавления")
        logger.info(f"   Найдено завершённых матчей: {len(completed_games)}")
        logger.info(f"   Из них есть в прогнозах: {matched_predictions}")

if __name__ == "__main__":
    update_statistics()
