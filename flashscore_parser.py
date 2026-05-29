import asyncio
import json
import os
from datetime import datetime, timedelta

from playwright.async_api import async_playwright

BASE_URL = "https://www.flashscorekz.com/basketball/usa/nba/results/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

async def get_todays_games():
    """Получить список матчей на сегодня (или за последние дни)"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Устанавливаем заголовки
        await page.set_extra_http_headers(HEADERS)
        
        # Переходим на страницу результатов (можно расширить под даты)
        await page.goto(BASE_URL)
        
        # Ждём загрузки таблицы
        await page.wait_for_selector(".section__content .event__match", timeout=10000)
        
        games = []
        rows = await page.query_selector_all(".section__content .event__match")
        
        for row in rows[:10]:  # берём первые 10 матчей
            home = await row.query_selector(".event__homeParticipant")
            away = await row.query_selector(".event__awayParticipant")
            score = await row.query_selector(".event__score")
            
            home_name = await home.inner_text() if home else "N/A"
            away_name = await away.inner_text() if away else "N/A"
            score_text = await score.inner_text() if score else "N/A"
            
            games.append({
                "home": home_name,
                "away": away_name,
                "score": score_text,
                "date": datetime.now().strftime("%Y-%m-%d")
            })
        
        await browser.close()
        return games

async def get_team_form(team_name: str, days_back: int = 14):
    """Получить последние 5 результатов команды и рассчитать форму"""
    # Здесь должна быть логика парсинга страницы конкретной команды или
    # агрегация из результатов всех матчей.
    # Пока упрощённо: собираем все матчи за последние days_back дней и фильтруем.
    all_games = await get_todays_games()  # замените на более широкую выборку
    team_games = [g for g in all_games if team_name in (g["home"], g["away"])]
    
    # Сортируем по дате (предполагаем, что уже отсортировано)
    last_5 = team_games[:5]
    wins = sum(1 for g in last_5 if (g["home"] == team_name and g["score"].split(":")[0] > g["score"].split(":")[1]) or
                                    (g["away"] == team_name and g["score"].split(":")[1] > g["score"].split(":")[0]))
    form = f"{wins}-{5-wins}"
    
    return {"form": form, "last_games": last_5}

def save_stats(games):
    """Сохранить данные в JSON для сайта"""
    os.makedirs("data", exist_ok=True)
    with open("data/matches.json", "w") as f:
        json.dump({"matches": games, "updated": datetime.now().isoformat()}, f, indent=2)

async def main():
    print("🚀 Запуск парсера Flashscore...")
    games = await get_todays_games()
    print(f"Найдено матчей: {len(games)}")
    
    # Пример: добавим форму для первых двух команд
    for game in games[:2]:
        home_form = await get_team_form(game["home"])
        away_form = await get_team_form(game["away"])
        game["home_form"] = home_form["form"]
        game["away_form"] = away_form["form"]
    
    save_stats(games)
    print("✅ Данные сохранены")

if __name__ == "__main__":
    asyncio.run(main())
