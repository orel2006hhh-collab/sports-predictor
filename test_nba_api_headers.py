import os
import requests
from nba_api.stats.endpoints import leaguegamefinder
from datetime import datetime, timedelta

# Устанавливаем заголовки прямо в настройках библиотеки
from nba_api.stats.library.http import NBAStatsHTTP
NBAStatsHTTP.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nba.com/',
    'Origin': 'https://www.nba.com',
    'Connection': 'keep-alive',
}

try:
    gamefinder = leaguegamefinder.LeagueGameFinder(
        date_from_nullable=(datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
        date_to_nullable=datetime.now().strftime('%Y-%m-%d')
    )
    games = gamefinder.get_data_frames()[0]
    print(f"✅ Данные получены! Найдено игр: {len(games)}")
    print(games[['GAME_DATE', 'MATCHUP', 'WL', 'PTS']].head())
except Exception as e:
    print(f"❌ Ошибка: {e}")
