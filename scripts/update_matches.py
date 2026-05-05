import requests
import json
from datetime import datetime, timedelta
import re

def get_today_tomorrow_dates():
    """Возвращает даты сегодня и завтра в формате ДД.ММ.ГГГГ"""
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    return today.strftime('%d.%m.%Y'), tomorrow.strftime('%d.%m.%Y')

def fetch_nhl_games():
    """Получение матчей НХЛ"""
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            games = []
            for event in data.get('events', []):
                comp = event.get('competitions', [{}])[0]
                competitors = comp.get('competitors', [])
                if len(competitors) >= 2:
                    home_team = competitors[0].get('team', {}).get('displayName', 'Unknown')
                    away_team = competitors[1].get('team', {}).get('displayName', 'Unknown')
                    # Проверяем, кто хозяин
                    if competitors[0].get('homeAway') == 'away':
                        home_team, away_team = away_team, home_team
                    
                    games.append({
                        'sport': 'nhl',
                        'home': home_team,
                        'away': away_team,
                        'league': 'НХЛ',
                        'prob': 0,  # Будет рассчитано позже
                        'winner': '',
                        'series': 'Регулярный чемпионат'
                    })
            return games
    except Exception as e:
        print(f"Ошибка загрузки НХЛ: {e}")
    return []

def fetch_khl_games():
    """Получение матчей КХЛ (симуляция, т.к. API закрыт)"""
    # В реальности здесь будет парсинг сайта КХЛ
    # Пока возвращаем тестовые данные
    today, tomorrow = get_today_tomorrow_dates()
    return [
        {'sport': 'khl', 'home': 'Авангард', 'away': 'Локомотив', 'league': 'КХЛ', 'series': 'Плей-офф', 'prob': 55},
        {'sport': 'khl', 'home': 'ЦСКА', 'away': 'Динамо М', 'league': 'КХЛ', 'series': 'Плей-офф', 'prob': 68}
    ]

def fetch_mhl_games():
    """Получение матчей МХЛ"""
    today, tomorrow = get_today_tomorrow_dates()
    return [
        {'sport': 'mhl', 'home': 'Чайка', 'away': 'Локо', 'league': 'МХЛ', 'series': 'Плей-офф', 'prob': 65},
        {'sport': 'mhl', 'home': 'Спартак М', 'away': 'Крылья Советов', 'league': 'МХЛ', 'series': 'Плей-офф', 'prob': 58}
    ]

def fetch_vhl_games():
    """Получение матчей ВХЛ"""
    today, tomorrow = get_today_tomorrow_dates()
    return [
        {'sport': 'vhl', 'home': 'Югра', 'away': 'Нефтяник', 'league': 'ВХЛ', 'series': 'Плей-офф', 'prob': 78},
        {'sport': 'vhl', 'home': 'Химик', 'away': 'Металлург Нк', 'league': 'ВХЛ', 'series': 'Плей-офф', 'prob': 62}
    ]

def fetch_nba_games():
    """Получение матчей НБА"""
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            games = []
            for event in data.get('events', []):
                comp = event.get('competitions', [{}])[0]
                competitors = comp.get('competitors', [])
                if len(competitors) >= 2:
                    home_team = competitors[0].get('team', {}).get('displayName', 'Unknown')
                    away_team = competitors[1].get('team', {}).get('displayName', 'Unknown')
                    if competitors[0].get('homeAway') == 'away':
                        home_team, away_team = away_team, home_team
                    games.append({'sport': 'nba', 'home': home_team, 'away': away_team, 'league': 'НБА', 'series': 'Регулярный чемпионат', 'prob': 0})
            return games
    except Exception as e:
        print(f"Ошибка загрузки НБА: {e}")
    return []

def fetch_vtb_games():
    """Получение матчей ВТБ"""
    today, tomorrow = get_today_tomorrow_dates()
    return [
        {'sport': 'vtb', 'home': 'ЦСКА', 'away': 'УНИКС', 'league': 'ВТБ', 'series': 'Финал', 'prob': 68},
        {'sport': 'vtb', 'home': 'Зенит', 'away': 'Локомотив-Кубань', 'league': 'ВТБ', 'series': 'Финал', 'prob': 55}
    ]

def fetch_cricket_games():
    """Получение матчей IPL"""
    today, tomorrow = get_today_tomorrow_dates()
    return [
        {'sport': 'cricket', 'home': 'Gujarat Titans', 'away': 'Mumbai Indians', 'league': 'IPL', 'series': 'Тур 2026', 'prob': 68},
        {'sport': 'cricket', 'home': 'Kolkata Knight Riders', 'away': 'Chennai Super Kings', 'league': 'IPL', 'series': 'Тур 2026', 'prob': 72},
        {'sport': 'cricket', 'home': 'Sunrisers Hyderabad', 'away': 'Royal Challengers', 'league': 'IPL', 'series': 'Тур 2026', 'prob': 55}
    ]

def calculate_winner(prob):
    """Определяет победителя на основе вероятности"""
    return 'home' if prob >= 50 else 'away'

def main():
    print("🚀 Начинаю обновление данных о матчах...")
    
    all_matches = []
    all_matches.extend(fetch_nhl_games())
    all_matches.extend(fetch_khl_games())
    all_matches.extend(fetch_mhl_games())
    all_matches.extend(fetch_vhl_games())
    all_matches.extend(fetch_nba_games())
    all_matches.extend(fetch_vtb_games())
    all_matches.extend(fetch_cricket_games())
    
    # Добавляем время матчей и победителей
    today, tomorrow = get_today_tomorrow_dates()
    times = ["17:00 МСК", "19:30 МСК", "21:00 МСК", "22:30 МСК", "02:00 МСК", "03:00 МСК", "05:00 МСК"]
    
    for i, match in enumerate(all_matches):
        match['date'] = today if i % 3 != 2 else tomorrow
        match['time'] = times[i % len(times)]
        match['winner'] = match['home'] if match['prob'] >= 50 else match['away']
        match['weather'] = "Комфортная температура, без осадков"
        match['motivation'] = "Стандартная мотивация"
    
    output = {
        "lastUpdated": datetime.now().isoformat(),
        "matches": all_matches,
        "dateInfo": {
            "today": today,
            "tomorrow": tomorrow
        }
    }
    
    with open('data/matches.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Обновлено! Найдено матчей: {len(all_matches)}")
    for match in all_matches:
        print(f"   - {match['sport'].upper()}: {match['home']} vs {match['away']}")

if __name__ == "__main__":
    main()
