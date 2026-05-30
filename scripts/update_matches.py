import sys
print("=== СКРИПТ ЗАПУСТИЛСЯ ===", file=sys.stderr)

print("1. Импортирую модули...")
try:
    import json
    print("   json - OK")
    import os
    print("   os - OK")
    import requests
    print("   requests - OK")
    from datetime import datetime, timedelta
    print("   datetime - OK")
except Exception as e:
    print(f"   ОШИБКА ИМПОРТА: {e}")
    sys.exit(1)

print("2. Проверяю API ключи...")
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

if not ODDS_API_KEY:
    print("   ❌ ODDS_API_KEY не найден в Secrets")
else:
    print(f"   ✅ ODDS_API_KEY найден (первые 5 символов: {ODDS_API_KEY[:5]})")

if not OPENROUTER_API_KEY:
    print("   ⚠️ OPENROUTER_API_KEY не найден в Secrets")
else:
    print(f"   ✅ OPENROUTER_API_KEY найден (первые 5 символов: {OPENROUTER_API_KEY[:5]})")

print("3. Пробую получить список матчей...")
SPORT = "basketball_nba"
REGIONS = "us,uk,eu"
MARKETS = "h2h,totals"

if ODDS_API_KEY:
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {"apiKey": ODDS_API_KEY, "regions": REGIONS, "markets": MARKETS, "oddsFormat": "american"}
    
    try:
        resp = requests.get(url, params=params, timeout=15)
        print(f"   Статус ответа: {resp.status_code}")
        if resp.status_code == 200:
            games = resp.json()
            print(f"   ✅ Найдено игр: {len(games)}")
        else:
            print(f"   ❌ Ошибка API: {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Ошибка запроса: {e}")
else:
    print("   ⚠️ Пропускаю, нет ключа")

print("=== СКРИПТ ЗАВЕРШИЛСЯ ===", file=sys.stderr)
