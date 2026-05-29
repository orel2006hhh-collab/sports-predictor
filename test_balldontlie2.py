import requests

print("Тест balldontlie API")
print("="*30)

url = "https://www.balldontlie.io/api/v1/teams"
try:
    resp = requests.get(url, timeout=10)
    print(f"Статус: {resp.status_code}")
    if resp.status_code == 200:
        teams = resp.json()
        print(f"✅ Найдено {len(teams.get('data', []))} команд")
        print("Первые 3 команды:")
        for team in teams.get('data', [])[:3]:
            print(f"  - {team['full_name']}")
    else:
        print(f"❌ Ошибка: {resp.status_code}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
