import requests
import os

print("🔍 ПОИСК РАБОТАЮЩЕГО API ДЛЯ NBA СТАТИСТИКИ")
print("="*50)

# Тестируем balldontlie
print("\n📡 Тестируем balldontlie...")
try:
    resp = requests.get("https://www.balldontlie.io/api/v1/teams", timeout=10)
    print(f"   Статус: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ РАБОТАЕТ! Найдено {len(data.get('data', []))} команд")
    else:
        print(f"   ❌ Не работает (статус {resp.status_code})")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Тестируем The Odds API (счета)
print("\n📡 Тестируем The Odds API (счета)...")
try:
    api_key = os.environ.get("ODDS_API_KEY")
    if api_key:
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/scores"
        params = {"apiKey": api_key, "daysFrom": 3}
        resp = requests.get(url, params=params, timeout=10)
        print(f"   Статус: {resp.status_code}")
        if resp.status_code == 200:
            games = resp.json()
            print(f"   ✅ РАБОТАЕТ! Найдено {len(games)} завершённых матчей")
        else:
            print(f"   ❌ Не работает")
    else:
        print("   ⚠️ ODDS_API_KEY не найден в секретах")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

print("\n" + "="*50)
