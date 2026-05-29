import requests

print("🔍 ПОИСК РАБОТАЮЩЕГО API ДЛЯ NBA СТАТИСТИКИ")
print("="*50)

# Список потенциально работающих API для теста
apis_to_test = {
    "balldontlie (основной)": "https://www.balldontlie.io/api/v1/teams",
    "balldontlie (альтернативный)": "https://api.balldontlie.io/v1/teams",
    "nba.com (прямой)": "https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/2024/league/00_team_stats.json",
    "sportsdata.io (демо)": "https://fly.sportsdata.io/v3/nba/scores/json/teams?key=demo",
    "odds-api (счета)": f"https://api.the-odds-api.com/v4/sports/basketball_nba/scores?daysFrom=3&apiKey={os.environ.get('ODDS_API_KEY', 'no_key')}"
}

for name, url in apis_to_test.items():
    try:
        print(f"\n📡 Тестируем: {name}")
        print(f"   URL: {url[:80]}...")
        
        # Для nba.com нужны заголовки
        headers = {"User-Agent": "Mozilla/5.0"} if "nba.com" in url else {}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            print(f"   ✅ ДОСТУПЕН (статус 200)")
            # Показываем первые 100 символов ответа
            data = resp.text[:200]
            print(f"   📦 Ответ: {data[:100]}...")
        else:
            print(f"   ❌ Ошибка {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Недоступен: {e}")

print("\n" + "="*50)
print("💡 Если ни один API не сработал, варианты решения:")
print("1. Получать статистику из счетов завершённых матчей The Odds API")
print("2. Использовать статические данные (но вы против этого)")
print("3. Найти другой источник")
