from nba_api.stats.endpoints import leaguegamefinder
from datetime import datetime, timedelta

print("📊 ТЕСТ NBA API")
print("="*40)

# Получаем игры за последние 3 дня
gamefinder = leaguegamefinder.LeagueGameFinder(
    date_from_nullable=(datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
    date_to_nullable=datetime.now().strftime('%Y-%m-%d')
)

games = gamefinder.get_data_frames()[0]

if len(games) > 0:
    print(f"✅ Найдено {len(games)} записей")
    print("\nПоследние игры:")
    print(games[['GAME_DATE', 'MATCHUP', 'WL', 'PTS']].head(10))
else:
    print("❌ Нет данных за последние 3 дня")
