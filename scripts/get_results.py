#!/usr/bin/env python3
"""
Скрипт для получения результатов матчей через fs-football-fork.
Сравнивает с прогнозами из matches.json и обновляет history.json.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Пытаемся импортировать библиотеку
try:
    from flashscore import FlashscoreApi
    FLASHSCORE_AVAILABLE = True
    logger.info("✅ fs-football-fork успешно загружена")
except ImportError as e:
    FLASHSCORE_AVAILABLE = False
    logger.warning(f"⚠️ fs-football-fork не установлена: {e}")
    logger.warning("   Установите: pip install fs-football-fork")

def load_predictions() -> List[Dict]:
    """Загружает текущие прогнозы из matches.json"""
    try:
        with open('data/matches.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            matches = data.get('matches', [])
            logger.info(f"📊 Загружено прогнозов: {len(matches)}")
            return matches
    except FileNotFoundError:
        logger.error("❌ Файл data/matches.json не найден")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка парсинга matches.json: {e}")
        return []

def load_history() -> Dict:
    """Загружает историю прогнозов"""
    try:
        with open('data/history.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("📭 Файл history.json не найден, создаю новый")
        return {"lastUpdated": "", "predictions": []}

def save_history(history: Dict) -> None:
    """Сохраняет историю прогнозов"""
    with open('data/history.json', 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    logger.info(f"💾 История сохранена, записей: {len(history.get('predictions', []))}")

def match_exists_in_history(history: Dict, match_date: str, home: str, away: str) -> bool:
    """Проверяет, есть ли уже матч в истории"""
    for pred in history.get('predictions', []):
        if pred.get('date') == match_date and pred.get('home') == home and pred.get('away') == away:
            return True
    return False

def fetch_today_results() -> List[Dict]:
    """
    Получает результаты сегодняшних матчей через fs-football-fork.
    Возвращает список словарей с данными о завершённых матчах.
    """
    if not FLASHSCORE_AVAILABLE:
        logger.error("❌ fs-football-fork не доступна")
        return []
    
    results = []
    
    try:
        logger.info("🔄 Подключение к Flashscore API...")
        api = FlashscoreApi()
        
        logger.info("📋 Получение матчей на сегодня...")
        today_matches = api.get_today_matches()
        
        if not today_matches:
            logger.warning("⚠️ Матчи на сегодня не найдены")
            return []
        
        logger.info(f"📊 Найдено матчей на сегодня: {len(today_matches)}")
        
        for match in today_matches:
            try:
                # Загружаем полную информацию о матче
                match.load_content()
                
                # Проверяем, завершён ли матч
                status = getattr(match, 'status', '')
                if status != 'Finished' and not (hasattr(match, 'home_team_score') and hasattr(match, 'away_team_score')):
                    continue
                
                home_score = getattr(match, 'home_team_score', None)
                away_score = getattr(match, 'away_team_score', None)
                
                # Пропускаем матчи без счёта
                if home_score is None or away_score is None:
                    continue
                
                home_team = getattr(match, 'home_team_name', '')
                away_team = getattr(match, 'away_team_name', '')
                match_date = getattr(match, 'date', '')
                
                if not home_team or not away_team:
                    continue
                
                # Определяем победителя
                if int(home_score) > int(away_score):
                    winner = home_team
                    winner_type = 'home'
                elif int(away_score) > int(home_score):
                    winner = away_team
                    winner_type = 'away'
                else:
                    winner = 'draw'
                    winner_type = 'draw'
                
                results.append({
                    'home': home_team,
                    'away': away_team,
                    'home_score': int(home_score),
                    'away_score': int(away_score),
                    'winner': winner,
                    'winner_type': winner_type,
                    'date': match_date,
                    'status': status
                })
                
                logger.debug(f"  📊 {home_team} {home_score}:{away_score} {away_team}")
                
            except Exception as e:
                logger.warning(f"  ⚠️ Ошибка обработки матча: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Ошибка при работе с Flashscore API: {e}")
        return []
    
    logger.info(f"✅ Найдено завершённых матчей: {len(results)}")
    return results

def update_statistics():
    """Основная функция обновления статистики"""
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ОБНОВЛЕНИЯ СТАТИСТИКИ ПРОГНОЗОВ")
    logger.info("=" * 60)
    
    # Загружаем прогнозы и историю
    predictions = load_predictions()
    history = load_history()
    
    if not predictions:
        logger.warning("⚠️ Нет прогнозов для проверки")
        return
    
    # Получаем результаты сегодняшних матчей
    results = fetch_today_results()
    
    if not results:
        logger.info("📭 Нет завершённых матчей для обработки")
        return
    
    # Сравниваем прогнозы с результатами
    new_results = []
    matches_checked = 0
    
    for result in results:
        # Ищем соответствующий прогноз
        for pred in predictions:
            # Сравниваем по командам и дате (приблизительно)
            if (pred.get('home') == result['home'] and pred.get('away') == result['away']):
                
                # Проверяем, не добавлен ли уже этот результат
                if match_exists_in_history(history, result['date'], result['home'], result['away']):
                    logger.debug(f"⏭️ Пропускаем (уже в истории): {result['home']} vs {result['away']}")
                    continue
                
                matches_checked += 1
                
                # Определяем, сбылся ли прогноз
                predicted_winner = pred.get('winner', '')
                actual_winner = result['winner']
                
                is_success = False
                if actual_winner != 'draw' and predicted_winner == actual_winner:
                    is_success = True
                elif actual_winner == 'draw' and predicted_winner == 'draw':
                    is_success = True
                
                # Формируем запись для истории
                history_entry = {
                    'date': result['date'],
                    'home': result['home'],
                    'away': result['away'],
                    'league': pred.get('league', 'Unknown'),
                    'sport': pred.get('sport', 'football'),
                    'prediction': f"{predicted_winner} победа",
                    'result': 'success' if is_success else 'failed',
                    'prob': pred.get('prob', 0),
                    'actual_score': f"{result['home_score']}:{result['away_score']}",
                    'checked_at': datetime.now().isoformat()
                }
                
                new_results.append(history_entry)
                logger.info(f"{'✅' if is_success else '❌'} {result['home']} {result['home_score']}:{result['away_score']} {result['away']} | Прогноз: {predicted_winner} ({pred.get('prob', 0)}%)")
                
                break
    
    # Добавляем новые результаты в историю
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
        logger.info(f"   ✅ Успешных прогнозов: {successes}")
        logger.info(f"   ❌ Неудачных: {total - successes}")
        logger.info(f"   📈 Общая точность: {accuracy:.1f}%")
        logger.info(f"   🆕 Добавлено записей: {len(new_results)}")
        logger.info("=" * 60)
    else:
        logger.info("📭 Нет новых результатов для добавления")

if __name__ == "__main__":
    update_statistics()
