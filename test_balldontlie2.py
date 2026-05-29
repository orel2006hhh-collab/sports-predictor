import requests

url = "https://www.balldontlie.io/api/v1/teams"
resp = requests.get(url, timeout=10)
print(f"Статус: {resp.status_code}")
if resp.status_code == 200:
    teams = resp.json()
    print(f"Найдено {len(teams.get('data', []))} команд")
