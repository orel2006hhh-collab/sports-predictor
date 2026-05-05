import json
import re
from datetime import datetime

def update_index_with_data():
    """Обновляет файл index.html с новыми данными о матчах"""
    
    # Загружаем свежие матчи
    with open('data/matches.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    matches = data.get('matches', [])
    today = data.get('dateInfo', {}).get('today', '')
    tomorrow = data.get('dateInfo', {}).get('tomorrow', '')
    
    # Читаем текущий index.html
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("⚠️ index.html не найден, будет создан новый")
        content = ""
    
    # Находим и заменяем секцию с матчами в JavaScript
    matches_js = json.dumps(matches, ensure_ascii=False, indent=12)
    
    # Паттерн для замены массива ALL_MATCHES
    pattern = r'(const ALL_MATCHES = )\[[\s\S]*?\];'
    replacement = r'\1' + matches_js + ';'
    
    new_content = re.sub(pattern, replacement, content)
    
    # Обновляем даты в кнопках и футере
    new_content = re.sub(r'(Сегодня \()\d{2}\.\d{2}\.\d{4}(\))', rf'\1{today}\2', new_content)
    new_content = re.sub(r'(Завтра \()\d{2}\.\d{2}\.\d{4}(\))', rf'\1{tomorrow}\2', new_content)
    
    # Сохраняем обновлённый index.html
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ index.html обновлён. Матчей: {len(matches)}")
    print(f"   Сегодня: {today}")
    print(f"   Завтра: {tomorrow}")

if __name__ == "__main__":
    update_index_with_data()
